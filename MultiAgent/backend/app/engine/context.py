"""Runtime context passed through agents, teams, workflows and tools."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select

from ..db import SessionLocal
from ..models import Organization, Project, Secret
from ..security import decrypt
from .events import bus
from .net import NetPolicy


@dataclass
class OrgSnap:
    id: str
    name: str
    context: str
    settings: dict[str, Any]

    @classmethod
    def of(cls, org: Organization) -> "OrgSnap":
        return cls(id=org.id, name=org.name, context=org.context or "", settings=dict(org.settings or {}))


@dataclass
class ProjectSnap:
    id: str
    name: str
    description: str
    context: str
    variables: dict[str, Any]
    settings: dict[str, Any]

    @classmethod
    def of(cls, p: Project) -> "ProjectSnap":
        return cls(
            id=p.id,
            name=p.name,
            description=p.description or "",
            context=p.context or "",
            variables=dict(p.variables or {}),
            settings=dict(p.settings or {}),
        )


class BudgetExceeded(Exception):
    pass


@dataclass
class RunContext:
    run_id: str
    org: OrgSnap
    project: ProjectSnap
    user_id: str | None = None
    trigger: str = "manual"
    depth: int = 0
    token_budget: int | None = None  # remaining tokens allowed for this run (org daily budget)
    usage: dict[str, int] = field(default_factory=lambda: {"input_tokens": 0, "output_tokens": 0, "llm_calls": 0, "tool_calls": 0})
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)
    _secrets: dict[str, str] | None = None
    current_agent_id: str | None = None
    extra_skill_ids: list[str] = field(default_factory=list)  # from /commands and conversation skills

    async def emit(self, type: str, data: dict[str, Any] | None = None, *, agent: str = "", node_id: str = "", persist: bool = True) -> None:
        await bus.publish(self.run_id, type, data, agent=agent, node_id=node_id, persist=persist)

    def child(self, agent_id: str | None = None) -> "RunContext":
        """Context for a nested agent (shares usage/budget/cancel with the parent run)."""
        c = RunContext(
            run_id=self.run_id,
            org=self.org,
            project=self.project,
            user_id=self.user_id,
            trigger=self.trigger,
            depth=self.depth + 1,
            token_budget=self.token_budget,
            usage=self.usage,
            cancel_event=self.cancel_event,
            _secrets=self._secrets,
            current_agent_id=agent_id,
            extra_skill_ids=self.extra_skill_ids,
        )
        return c

    def add_usage(self, input_tokens: int, output_tokens: int) -> None:
        self.usage["input_tokens"] += input_tokens
        self.usage["output_tokens"] += output_tokens
        self.usage["llm_calls"] += 1

    @property
    def total_tokens(self) -> int:
        return self.usage["input_tokens"] + self.usage["output_tokens"]

    def check(self) -> None:
        if self.cancel_event.is_set():
            raise asyncio.CancelledError()
        if self.token_budget is not None and self.total_tokens > self.token_budget:
            raise BudgetExceeded("Organization daily token budget exhausted during this run")

    async def secrets(self) -> dict[str, str]:
        if self._secrets is None:
            async with SessionLocal() as s:
                rows = (await s.execute(select(Secret).where(Secret.org_id == self.org.id))).scalars().all()
                self._secrets = {r.name: decrypt(r.value_enc) for r in rows}
        return self._secrets

    def net_policy(self) -> NetPolicy:
        ps = self.project.settings
        return NetPolicy(
            allow_private=False,
            allowed_domains=[d for d in (ps.get("allowed_domains") or []) if d],
            blocked_domains=[d for d in (ps.get("blocked_domains") or []) if d],
        )

    @property
    def web_access(self) -> bool:
        return self.project.settings.get("web_access", True) is not False
