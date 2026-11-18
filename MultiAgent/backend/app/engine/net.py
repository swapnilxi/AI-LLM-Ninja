"""SSRF-hardened outbound HTTP used by every tool and connector.

* only http/https, no credentials in URLs
* DNS is resolved up-front and every address must be public (unless allowed)
* the connection is pinned to the validated IP (defeats DNS rebinding) while TLS
  still verifies the original hostname via SNI
* redirects are followed manually and re-validated hop by hop
* response bodies are size-capped and requests time out
* optional per-project allow/deny domain lists
"""
from __future__ import annotations

import asyncio
import ipaddress
import socket
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx

from ..config import settings

BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0 Safari/537.36 AgentForge/1.0"
)
_ALLOWED_PORTS = {80, 443, 8080, 8443}


class BlockedURL(Exception):
    pass


@dataclass
class NetPolicy:
    allow_private: bool = False
    allowed_domains: list[str] = field(default_factory=list)
    blocked_domains: list[str] = field(default_factory=list)


@dataclass
class SafeResponse:
    status_code: int
    headers: dict[str, str]
    url: str
    content: bytes
    truncated: bool = False

    @property
    def text(self) -> str:
        enc = "utf-8"
        ctype = self.headers.get("content-type", "")
        if "charset=" in ctype:
            enc = ctype.split("charset=")[-1].split(";")[0].strip() or "utf-8"
        try:
            return self.content.decode(enc, errors="replace")
        except LookupError:
            return self.content.decode("utf-8", errors="replace")

    def json(self) -> Any:
        import json

        return json.loads(self.content or b"null")


def host_matches(host: str, domains: list[str]) -> bool:
    host = host.lower().rstrip(".")
    for d in domains:
        d = d.lower().strip().lstrip("*.").rstrip(".")
        if d and (host == d or host.endswith("." + d)):
            return True
    return False


def _is_public(ip_str: str) -> bool:
    ip = ipaddress.ip_address(ip_str)
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return ip.is_global and not ip.is_multicast and not ip.is_reserved


async def resolve_host(host: str, port: int) -> list[str]:
    loop = asyncio.get_running_loop()
    try:
        infos = await asyncio.wait_for(loop.getaddrinfo(host, port, type=socket.SOCK_STREAM), timeout=10)
    except (socket.gaierror, asyncio.TimeoutError) as exc:
        raise BlockedURL(f"Could not resolve host '{host}'") from exc
    return list(dict.fromkeys(info[4][0] for info in infos))


async def validate_url(url: str, policy: NetPolicy | None = None) -> tuple[str, int, str]:
    """Validate a URL; returns (host, port, pinned_ip)."""
    policy = policy or NetPolicy(allow_private=settings.allow_private_network)
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise BlockedURL("Only http(s) URLs are allowed")
    if parts.username or parts.password:
        raise BlockedURL("Credentials in URLs are not allowed")
    host = (parts.hostname or "").lower()
    if not host:
        raise BlockedURL("URL has no host")
    port = parts.port or (443 if parts.scheme == "https" else 80)
    if policy.blocked_domains and host_matches(host, policy.blocked_domains):
        raise BlockedURL(f"Domain '{host}' is blocked by project policy")
    if policy.allowed_domains and not host_matches(host, policy.allowed_domains):
        raise BlockedURL(f"Domain '{host}' is not in the project's allowed domains")
    allow_private = policy.allow_private or settings.allow_private_network
    if not allow_private and port not in _ALLOWED_PORTS:
        raise BlockedURL(f"Port {port} is not allowed")
    if host in ("localhost",) or host.endswith((".localhost", ".local", ".internal")):
        if not allow_private:
            raise BlockedURL("Local hostnames are not allowed")
    ips = await resolve_host(host, port)
    if not ips:
        raise BlockedURL(f"Could not resolve host '{host}'")
    if not allow_private:
        bad = [ip for ip in ips if not _is_public(ip)]
        if bad:
            raise BlockedURL("Requests to private, loopback or link-local addresses are blocked")
    return host, port, ips[0]


def _pinned_url(url: str, ip: str) -> str:
    parts = urlsplit(url)
    host_part = f"[{ip}]" if ":" in ip else ip
    netloc = host_part if parts.port is None else f"{host_part}:{parts.port}"
    return urlunsplit((parts.scheme, netloc, parts.path or "/", parts.query, ""))


async def safe_request(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
    json: Any = None,
    data: Any = None,
    content: bytes | str | None = None,
    timeout: float = 20.0,
    max_bytes: int = 5 * 1024 * 1024,
    max_redirects: int = 5,
    policy: NetPolicy | None = None,
) -> SafeResponse:
    method = method.upper()
    req_headers = {"user-agent": BROWSER_UA, "accept": "*/*"}
    req_headers.update({k.lower(): v for k, v in (headers or {}).items()})
    current = str(httpx.URL(url, params=params)) if params else url

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False, verify=True) as client:
        for _ in range(max_redirects + 1):
            host, _port, ip = await validate_url(current, policy)
            parts = urlsplit(current)
            hdrs = dict(req_headers)
            hdrs["host"] = parts.netloc.split("@")[-1]
            extensions = {"sni_hostname": host} if parts.scheme == "https" else {}
            request = client.build_request(
                method,
                _pinned_url(current, ip),
                headers=hdrs,
                json=json,
                data=data,
                content=content,
                extensions=extensions,
            )
            resp = await client.send(request, stream=True)
            try:
                if resp.status_code in (301, 302, 303, 307, 308) and "location" in resp.headers:
                    current = urljoin(current, resp.headers["location"])
                    if resp.status_code == 303 or (resp.status_code in (301, 302) and method == "POST"):
                        method, json, data, content = "GET", None, None, None
                    continue
                body = bytearray()
                truncated = False
                async for chunk in resp.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > max_bytes:
                        truncated = True
                        del body[max_bytes:]
                        break
                return SafeResponse(
                    status_code=resp.status_code,
                    headers={k.lower(): v for k, v in resp.headers.items()},
                    url=current,
                    content=bytes(body),
                    truncated=truncated,
                )
            finally:
                await resp.aclose()
    raise BlockedURL("Too many redirects")
