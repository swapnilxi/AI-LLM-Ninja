"""Request/response schemas for the agents module (with input limits as a safeguard)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.core.schemas import ORM, Effort


class AgentIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=4000)
    avatar: str = Field(default="bot", max_length=40, pattern=r"^[a-z0-9-]+$")
    color: str = Field(default="indigo", max_length=20)
    provider: str = Field(default="default", max_length=40)
    model: str = Field(default="", max_length=120)
    system_prompt: str = Field(default="", max_length=50000)
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int = Field(default=8000, ge=256, le=128000)
    max_steps: int = Field(default=8, ge=1, le=30)
    effort: Effort = "medium"
    tool_ids: list[str] = Field(default_factory=list, max_length=100)
    skill_ids: list[str] = Field(default_factory=list, max_length=50)
    connection_ids: list[str] = Field(default_factory=list, max_length=50)
    settings: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list, max_length=20)
    scope: Literal["org", "global"] = "org"


class AgentOut(ORM):
    id: str
    org_id: str | None
    name: str
    description: str
    avatar: str
    color: str
    provider: str
    model: str
    system_prompt: str
    temperature: float | None
    max_tokens: int
    max_steps: int
    effort: str
    tool_ids: list[str]
    skill_ids: list[str]
    connection_ids: list[str]
    settings: dict[str, Any]
    tags: list[str]
    created_at: datetime
    updated_at: datetime
