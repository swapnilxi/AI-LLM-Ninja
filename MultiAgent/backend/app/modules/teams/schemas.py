"""Request/response schemas for the teams module (with input limits as a safeguard)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.core.schemas import ORM, Style


class TeamMember(BaseModel):
    agent_id: str
    role: str = Field(default="", max_length=200)
    instructions: str = Field(default="", max_length=4000)


class TeamIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=4000)
    style: Style = "sequential"
    members: list[TeamMember] = Field(default_factory=list, max_length=20)
    manager_agent_id: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    scope: Literal["org", "global"] = "org"


class TeamOut(ORM):
    id: str
    org_id: str | None
    name: str
    description: str
    style: str
    members: list[dict[str, Any]]
    manager_agent_id: str | None
    config: dict[str, Any]
    created_at: datetime
    updated_at: datetime
