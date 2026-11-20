"""Pure-ASGI security middleware: request ids, security headers, body limits, IP rate limiting."""
from __future__ import annotations

import json
import logging
import secrets
import time

from starlette.datastructures import Headers
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import settings
from app.core.ratelimit import limiter_backend

log = logging.getLogger("agentforge.http")

_SECURITY_HEADERS = [
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"strict-origin-when-cross-origin"),
    (b"permissions-policy", b"camera=(), microphone=(), geolocation=(), payment=()"),
    (b"cross-origin-opener-policy", b"same-origin"),
    (b"cross-origin-resource-policy", b"same-site"),
]
_API_CSP = b"default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
_SPA_CSP = (
    b"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    b"font-src 'self' data: https://fonts.gstatic.com; img-src 'self' data: blob: https:; connect-src 'self'; "
    b"frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'"
)
_HSTS = (b"strict-transport-security", b"max-age=31536000; includeSubDomains")
_DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")


async def _send_json(send: Send, status: int, body: dict, headers: list[tuple[bytes, bytes]] | None = None) -> None:
    payload = json.dumps(body).encode()
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(payload)).encode())]
            + (headers or []),
        }
    )
    await send({"type": "http.response.body", "body": payload})


def _scope_ip(scope: Scope) -> str:
    if settings.trust_proxy_headers:
        h = Headers(scope=scope)
        fwd = h.get("x-forwarded-for")
        if fwd:
            return fwd.split(",")[0].strip()
    client = scope.get("client")
    return client[0] if client else "unknown"


class SecurityMiddleware:
    """Adds request ids + security headers, enforces body size and a global per-IP rate limit."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path: str = scope.get("path", "")
        request_id = secrets.token_hex(8)
        started = time.perf_counter()
        ip = _scope_ip(scope)
        status_holder = {"status": 0}

        # ---- global per-IP rate limit (health checks exempt)
        if path.startswith("/api") and path != "/api/health":
            res = await limiter_backend.hit(f"ip:{ip}", settings.rate_limit_global_per_minute, 60)
            if not res.allowed:
                await _send_json(
                    send,
                    429,
                    {"detail": "Too many requests"},
                    [(b"retry-after", str(res.retry_after).encode())],
                )
                return

        # ---- body size limit
        is_upload = path.startswith("/api/documents/upload")
        max_bytes = (settings.max_upload_mb if is_upload else settings.max_request_mb) * 1024 * 1024
        headers = Headers(scope=scope)
        cl = headers.get("content-length")
        if cl and cl.isdigit() and int(cl) > max_bytes:
            await _send_json(send, 413, {"detail": "Request body too large"})
            return

        received = {"n": 0}

        async def limited_receive() -> Message:
            message = await receive()
            if message["type"] == "http.request":
                received["n"] += len(message.get("body", b""))
                if received["n"] > max_bytes:
                    raise _BodyTooLarge()
            return message

        is_https = scope.get("scheme") == "https" or headers.get("x-forwarded-proto") == "https"

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                status_holder["status"] = message["status"]
                hdrs = list(message.get("headers", []))
                existing = {k.lower() for k, _ in hdrs}
                for k, v in _SECURITY_HEADERS:
                    if k not in existing:
                        hdrs.append((k, v))
                if b"content-security-policy" not in existing and not path.startswith(_DOCS_PATHS):
                    hdrs.append((b"content-security-policy", _API_CSP if path.startswith("/api") else _SPA_CSP))
                if is_https:
                    hdrs.append(_HSTS)
                hdrs.append((b"x-request-id", request_id.encode()))
                message["headers"] = hdrs
            await send(message)

        try:
            await self.app(scope, limited_receive, send_wrapper)
        except _BodyTooLarge:
            await _send_json(send, 413, {"detail": "Request body too large"})
        finally:
            if path.startswith("/api") and not path.endswith("/stream"):
                log.info(
                    "%s %s %s %.0fms ip=%s rid=%s",
                    scope.get("method"),
                    path,
                    status_holder["status"],
                    (time.perf_counter() - started) * 1000,
                    ip,
                    request_id,
                )


class _BodyTooLarge(Exception):
    pass
