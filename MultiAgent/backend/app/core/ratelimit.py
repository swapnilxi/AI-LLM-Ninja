"""Sliding-window rate limiter with an in-memory backend and an optional Redis backend.

The in-memory backend is per-process; set REDIS_URL to share limits across
multiple API instances.
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass

from fastapi import HTTPException, Request

from .config import settings

log = logging.getLogger("agentforge.ratelimit")


@dataclass
class LimitResult:
    allowed: bool
    limit: int
    remaining: int
    retry_after: int


class MemoryBackend:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = {}
        self._lock = asyncio.Lock()
        self._last_sweep = time.monotonic()

    async def hit(self, key: str, limit: int, window: int) -> LimitResult:
        now = time.monotonic()
        async with self._lock:
            q = self._hits.setdefault(key, deque())
            cutoff = now - window
            while q and q[0] <= cutoff:
                q.popleft()
            if len(q) >= limit:
                retry = int(q[0] + window - now) + 1
                return LimitResult(False, limit, 0, max(retry, 1))
            q.append(now)
            if now - self._last_sweep > 60:
                self._sweep(now, window)
            return LimitResult(True, limit, limit - len(q), 0)

    def _sweep(self, now: float, window: int) -> None:
        self._last_sweep = now
        for k in [k for k, q in self._hits.items() if not q or q[-1] < now - max(window, 3600)]:
            self._hits.pop(k, None)


class RedisBackend:
    def __init__(self, url: str) -> None:
        import redis.asyncio as redis  # optional dependency

        self._r = redis.from_url(url)

    async def hit(self, key: str, limit: int, window: int) -> LimitResult:
        now = time.time()
        rkey = f"rl:{key}"
        pipe = self._r.pipeline()
        pipe.zremrangebyscore(rkey, 0, now - window)
        pipe.zcard(rkey)
        _, count = await pipe.execute()
        if count >= limit:
            oldest = await self._r.zrange(rkey, 0, 0, withscores=True)
            retry = int(oldest[0][1] + window - now) + 1 if oldest else window
            return LimitResult(False, limit, 0, max(retry, 1))
        pipe = self._r.pipeline()
        pipe.zadd(rkey, {f"{now}:{id(pipe)}": now})
        pipe.expire(rkey, window + 1)
        await pipe.execute()
        return LimitResult(True, limit, limit - count - 1, 0)


def _make_backend():
    if settings.redis_url:
        try:
            return RedisBackend(settings.redis_url)
        except Exception as exc:  # pragma: no cover
            log.warning("Redis rate limiter unavailable (%s); using in-memory backend", exc)
    return MemoryBackend()


limiter_backend = _make_backend()


def client_ip(request: Request) -> str:
    if settings.trust_proxy_headers:
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            return fwd.split(",")[0].strip()
        real = request.headers.get("x-real-ip")
        if real:
            return real.strip()
    return request.client.host if request.client else "unknown"


async def enforce(key: str, limit: int, window: int = 60) -> LimitResult:
    """Raise 429 if `key` exceeded `limit` hits within `window` seconds."""
    if limit <= 0:
        return LimitResult(True, 0, 0, 0)
    res = await limiter_backend.hit(key, limit, window)
    if not res.allowed:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please slow down.",
            headers={"Retry-After": str(res.retry_after), "X-RateLimit-Limit": str(limit), "X-RateLimit-Remaining": "0"},
        )
    return res
