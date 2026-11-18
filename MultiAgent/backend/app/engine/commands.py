"""Skill slash commands: `/command args` at the start of a task applies that skill to the run."""
from __future__ import annotations

import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..deps import visible
from ..models import Skill
from .templating import TemplateRenderError, render

COMMAND_RE = re.compile(r"^\s*/([A-Za-z0-9][A-Za-z0-9_-]{0,39})(?:[ \t]+|\n|$)(.*)$", re.S)
COMMAND_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,39}$")
RESERVED = {"new", "clear", "help", "skills", "stop"}


async def find_command_skill(session: AsyncSession, org_id: str, command: str) -> Skill | None:
    rows = (
        (await session.execute(select(Skill).where(Skill.command == command.lower(), visible(Skill, org_id))))
        .scalars()
        .all()
    )
    # an org's own skill wins over a global one with the same command
    rows.sort(key=lambda s: s.org_id is None)
    return rows[0] if rows else None


async def apply_command(session: AsyncSession, org_id: str, task: str, project: Any) -> tuple[str, list[str], dict[str, Any] | None]:
    """Returns (task, extra_skill_ids, info). Leaves the task untouched if no known command."""
    m = COMMAND_RE.match(task or "")
    if not m:
        return task, [], None
    name, args = m.group(1).lower(), (m.group(2) or "").strip()
    skill = await find_command_skill(session, org_id, name)
    if not skill:
        return task, [], None
    if skill.command_template:
        try:
            new_task = render(
                skill.command_template,
                {"args": args, "vars": getattr(project, "variables", {}), "project": {"name": getattr(project, "name", "")}},
            ).strip()
        except TemplateRenderError:
            new_task = args
    else:
        new_task = args
    if not new_task:
        new_task = f"Apply the '{skill.name}' skill to the current context."
    return new_task, [skill.id], {"command": name, "skill_id": skill.id, "skill": skill.name, "args": args[:500]}
