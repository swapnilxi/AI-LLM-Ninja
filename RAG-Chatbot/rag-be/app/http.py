"""Small httpx helpers shared by every HTTP-based provider."""
from __future__ import annotations

import json
import time
from typing import Any, Iterator

import httpx

RETRY_STATUS = {429, 500, 502, 503, 504}
TIMEOUT = httpx.Timeout(120.0, connect=10.0)


class ProviderError(RuntimeError):
    """A user-presentable failure talking to an LLM / embedding / DB backend."""


def _explain(resp: httpx.Response) -> str:
    try:
        body = resp.json()
        msg = body.get("error", body)
        if isinstance(msg, dict):
            msg = msg.get("message") or json.dumps(msg)
    except ValueError:
        msg = resp.text
    return f"HTTP {resp.status_code}: {str(msg)[:400]}"


def _wrap(e: Exception, url: str) -> ProviderError:
    if isinstance(e, httpx.ConnectError):
        return ProviderError(f"Cannot connect to {url.split('?')[0]} - is the service running / reachable?")
    if isinstance(e, httpx.TimeoutException):
        return ProviderError(f"Timed out talking to {url.split('?')[0]}")
    return ProviderError(str(e))


def request_json(method: str, url: str, *, retries: int = 3, **kw: Any) -> Any:
    delay = 1.0
    for attempt in range(retries + 1):
        try:
            resp = httpx.request(method, url, timeout=TIMEOUT, **kw)
        except httpx.HTTPError as e:
            raise _wrap(e, url) from e
        if resp.status_code in RETRY_STATUS and attempt < retries:
            wait = resp.headers.get("retry-after")
            time.sleep(min(float(wait), 30) if wait and wait.replace(".", "").isdigit() else delay)
            delay *= 2
            continue
        if resp.is_error:
            raise ProviderError(_explain(resp))
        return resp.json()
    raise ProviderError("unreachable")  # pragma: no cover


def _retry_wait(resp: httpx.Response, delay: float) -> float:
    wait = resp.headers.get("retry-after", "")
    return min(float(wait), 20.0) if wait.replace(".", "", 1).isdigit() else delay


def stream_lines(method: str, url: str, *, retries: int = 2, **kw: Any) -> Iterator[str]:
    """Yield decoded text lines of a streaming response; raises ProviderError on failure.

    Transient failures (429 rate limit, 500/502/503/504 "model overloaded") are retried with backoff, but only
    BEFORE the first line is delivered - once tokens are flowing a retry would repeat text."""
    delay = 1.0
    for attempt in range(retries + 1):
        try:
            with httpx.stream(method, url, timeout=TIMEOUT, **kw) as resp:
                if resp.status_code in RETRY_STATUS and attempt < retries:
                    resp.read()
                    time.sleep(_retry_wait(resp, delay))
                    delay *= 2
                    continue
                if resp.is_error:
                    resp.read()
                    raise ProviderError(_explain(resp))
                for line in resp.iter_lines():
                    if line:
                        yield line
                return
        except httpx.HTTPError as e:
            raise _wrap(e, url) from e
