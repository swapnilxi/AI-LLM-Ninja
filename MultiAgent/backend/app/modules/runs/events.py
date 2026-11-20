"""In-process run event bus: persists trace events and fans them out to live SSE subscribers."""
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from app.core.db import SessionLocal
from app.modules.runs.models import RunEvent

log = logging.getLogger("agentforge.events")

TERMINAL = "run_end"


class EventBus:
    def __init__(self) -> None:
        self._subs: dict[str, set[asyncio.Queue]] = defaultdict(set)
        self._seq: dict[str, int] = defaultdict(int)
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    def subscribe(self, run_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=5000)
        self._subs[run_id].add(q)
        return q

    def unsubscribe(self, run_id: str, q: asyncio.Queue) -> None:
        self._subs.get(run_id, set()).discard(q)
        if not self._subs.get(run_id):
            self._subs.pop(run_id, None)

    async def publish(
        self,
        run_id: str,
        type: str,
        data: dict[str, Any] | None = None,
        *,
        agent: str = "",
        node_id: str = "",
        persist: bool = True,
    ) -> None:
        event: dict[str, Any] = {
            "type": type,
            "agent": agent,
            "node_id": node_id,
            "data": data or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        if persist:
            async with self._locks[run_id]:
                self._seq[run_id] += 1
                event["seq"] = self._seq[run_id]
                try:
                    async with SessionLocal() as s:
                        s.add(RunEvent(run_id=run_id, seq=event["seq"], type=type, agent=agent, node_id=node_id, data=data or {}))
                        await s.commit()
                except Exception:  # never let tracing break a run
                    log.exception("failed to persist run event")
        for q in list(self._subs.get(run_id, ())):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass
        if type == TERMINAL:
            self._seq.pop(run_id, None)
            self._locks.pop(run_id, None)


bus = EventBus()
