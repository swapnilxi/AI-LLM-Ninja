"""Run lifecycle: guardrails, background execution, cancellation, persistence."""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import SessionLocal
from app.core.ratelimit import limiter_backend
from app.engine.context import BudgetExceeded, OrgSnap, ProjectSnap, RunContext
from app.engine.llm.base import LLMError
from app.engine.templating import TemplateRenderError
from app.modules.agents.models import Agent
from app.modules.chat.models import Conversation, Message
from app.modules.orgs.models import Organization
from app.modules.projects.models import Project
from app.modules.runs.models import Run
from app.modules.scheduler.models import Automation
from app.modules.skills.commands import apply_command
from app.modules.teams.models import Team
from app.modules.workflows.models import Workflow

log = logging.getLogger("agentforge.runs")

TARGETS = {"agent": Agent, "team": Team, "workflow": Workflow}
_tasks: dict[str, asyncio.Task] = {}
_contexts: dict[str, RunContext] = {}


def _today_start() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


async def tokens_used_today(session: AsyncSession, org_id: str) -> int:
    val = (
        await session.execute(select(func.coalesce(func.sum(Run.total_tokens), 0)).where(Run.org_id == org_id, Run.created_at >= _today_start()))
    ).scalar_one()
    return int(val or 0)


def daily_limit(org: Organization) -> int:
    lim = (org.settings or {}).get("daily_token_limit")
    return int(lim) if lim is not None else settings.default_daily_token_limit


def task_from_input(data: dict[str, Any]) -> str:
    for k in ("message", "task", "prompt", "query", "input", "topic", "question"):
        if isinstance(data.get(k), str) and data[k].strip():
            return data[k]
    return json.dumps(data, ensure_ascii=False) if data else "Hello"


async def start_run(
    session: AsyncSession,
    *,
    org: Organization,
    project: Project,
    target_type: str,
    target_id: str,
    input: dict[str, Any],
    trigger: str = "manual",
    user_id: str | None = None,
    conversation_id: str | None = None,
    automation_id: str | None = None,
) -> Run:
    if target_type not in TARGETS:
        raise HTTPException(400, "target_type must be agent, team or workflow")
    if project.org_id != org.id:
        raise HTTPException(404, "Project not found")
    target = await session.get(TARGETS[target_type], target_id)
    if not target or (target.org_id is not None and target.org_id != org.id):
        raise HTTPException(404, f"{target_type.title()} not found")
    if len(json.dumps(input, default=str)) > 200_000:
        raise HTTPException(413, "Run input too large")

    # ---- guardrails: per-org rate, concurrency and daily token budget
    rl = await limiter_backend.hit(f"runs:{org.id}", settings.rate_limit_runs_per_minute, 60)
    if not rl.allowed:
        raise HTTPException(429, "Too many runs started - slow down", headers={"Retry-After": str(rl.retry_after)})
    max_conc = int((org.settings or {}).get("max_concurrent_runs") or settings.max_concurrent_runs_per_org)
    active = (
        await session.execute(select(func.count()).select_from(Run).where(Run.org_id == org.id, Run.status.in_(["queued", "running"])))
    ).scalar_one()
    if active >= max_conc:
        raise HTTPException(429, f"Concurrent run limit reached ({max_conc}). Wait for running jobs to finish.")
    limit = daily_limit(org)
    if limit > 0 and await tokens_used_today(session, org.id) >= limit:
        raise HTTPException(429, "Daily token budget exhausted for this organization")

    run = Run(
        org_id=org.id,
        project_id=project.id,
        target_type=target_type,
        target_id=target_id,
        target_name=target.name,
        status="queued",
        input=input,
        trigger=trigger,
        user_id=user_id,
        conversation_id=conversation_id,
        automation_id=automation_id,
    )
    session.add(run)
    await session.commit()
    _tasks[run.id] = asyncio.create_task(_execute(run.id))
    return run


async def _execute(run_id: str) -> None:
    async with SessionLocal() as s:
        run = await s.get(Run, run_id)
        org = await s.get(Organization, run.org_id)
        project = await s.get(Project, run.project_id)
        limit = daily_limit(org)
        used = await tokens_used_today(s, org.id)
        run.status = "running"
        run.started_at = datetime.now(timezone.utc)
        await s.commit()
        history: list[dict[str, Any]] = []
        if run.conversation_id:
            msgs = (
                (await s.execute(select(Message).where(Message.conversation_id == run.conversation_id).order_by(Message.created_at)))
                .scalars()
                .all()
            )
            msgs = msgs[:-1] if msgs and msgs[-1].role == "user" else msgs  # current message is the task
            history = [{"role": m.role, "content": m.content} for m in msgs[-30:] if m.content]
        target = await s.get(TARGETS[run.target_type], run.target_id)
        # skills: conversation-level skills + a leading /command in the task
        extra_skills: list[str] = []
        command_info = None
        if run.conversation_id:
            conv = await s.get(Conversation, run.conversation_id)
            extra_skills += list(conv.skill_ids or []) if conv else []
        task = task_from_input(run.input or {})
        if run.target_type in ("agent", "team"):
            task, cmd_skills, command_info = await apply_command(s, org.id, task, project)
            extra_skills += cmd_skills

    ctx = RunContext(
        run_id=run_id,
        org=OrgSnap.of(org),
        project=ProjectSnap.of(project),
        user_id=run.user_id,
        trigger=run.trigger,
        token_budget=(limit - used) if limit > 0 else None,
        extra_skill_ids=list(dict.fromkeys(extra_skills)),
    )
    _contexts[run_id] = ctx
    await ctx.emit("run_start", {"target_type": run.target_type, "target_id": run.target_id, "target_name": run.target_name, "input": run.input})
    if command_info:
        await ctx.emit("skill_command", command_info)

    status, output, error = "succeeded", "", ""
    try:
        coro = _dispatch(ctx, run.target_type, target, run.input or {}, history, task)
        output = await asyncio.wait_for(coro, timeout=settings.run_timeout_seconds)
    except asyncio.CancelledError:
        status, error = "cancelled", "Cancelled by user"
    except asyncio.TimeoutError:
        status, error = "failed", f"Run timed out after {settings.run_timeout_seconds}s"
    except (LLMError, BudgetExceeded, TemplateRenderError, HTTPException) as exc:
        status, error = "failed", str(getattr(exc, "detail", exc))
    except Exception as exc:  # workflow errors and unexpected failures
        log.exception("run %s failed", run_id)
        status, error = "failed", str(exc)[:2000] or exc.__class__.__name__
    finally:
        _contexts.pop(run_id, None)
        _tasks.pop(run_id, None)

    try:
        async with SessionLocal() as s:
            run = await s.get(Run, run_id)
            run.status = status
            run.output = output or ""
            run.error = error
            run.usage = dict(ctx.usage)
            run.total_tokens = ctx.total_tokens
            run.finished_at = datetime.now(timezone.utc)
            if run.conversation_id:
                s.add(
                    Message(
                        conversation_id=run.conversation_id,
                        role="assistant",
                        content=output if status == "succeeded" else f"**Run {status}:** {error}",
                        run_id=run_id,
                        meta={"status": status, "usage": dict(ctx.usage)},
                    )
                )
                conv = await s.get(Conversation, run.conversation_id)
                if conv:
                    conv.updated_at = datetime.now(timezone.utc)
            if run.automation_id:
                auto = await s.get(Automation, run.automation_id)
                if auto:
                    auto.last_status = status
            await s.commit()
    finally:
        if status == "succeeded":
            from app.modules.training.learning import schedule_auto_learn

            schedule_auto_learn(run_id)
        await ctx.emit("run_end", {"status": status, "output": output[:8000], "error": error, "usage": dict(ctx.usage)})


async def _dispatch(ctx: RunContext, target_type: str, target: Any, data: dict[str, Any], history: list[dict[str, Any]], task: str) -> str:
    if target_type == "agent":
        from app.modules.agents.runner import run_agent

        return (await run_agent(ctx, target, task, history=history)).text
    if target_type == "team":
        from app.modules.teams.orchestrator import run_team

        return await run_team(ctx, target, task, history)
    from app.modules.workflows.engine import run_workflow

    return await run_workflow(ctx, target, data)


async def cancel_run(run_id: str) -> bool:
    task = _tasks.get(run_id)
    ctx = _contexts.get(run_id)
    if ctx:
        ctx.cancel_event.set()
    if task and not task.done():
        task.cancel()
        return True
    return False


async def wait_for_run(run_id: str, timeout: float) -> None:
    task = _tasks.get(run_id)
    if task:
        await asyncio.wait({task}, timeout=timeout)


async def recover_interrupted_runs() -> None:
    async with SessionLocal() as s:
        await s.execute(
            update(Run)
            .where(Run.status.in_(["queued", "running"]))
            .values(status="failed", error="Interrupted by server restart", finished_at=datetime.now(timezone.utc))
        )
        await s.commit()


async def shutdown() -> None:
    for task in list(_tasks.values()):
        task.cancel()
    if _tasks:
        await asyncio.wait(list(_tasks.values()), timeout=5)


def prune_cutoff(days: int = 30) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)
