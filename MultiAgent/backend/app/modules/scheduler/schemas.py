"""Request/response schemas for the scheduler module (with input limits as a safeguard)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.core.schemas import ORM, TargetType


class AutomationIn(BaseModel):
    project_id: str
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    target_type: TargetType
    target_id: str
    input: dict[str, Any] = Field(default_factory=dict)
    trigger_type: Literal["schedule", "interval", "once", "webhook", "manual"] = "manual"
    cron: str = Field(default="", max_length=120)
    interval_minutes: int = Field(default=0, ge=0, le=60 * 24 * 31)
    timezone: str = Field(default="UTC", max_length=64)
    run_at: datetime | None = None
    source: Literal["form", "chat"] = "form"
    enabled: bool = True


class AutomationUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    target_type: TargetType | None = None
    target_id: str | None = None
    input: dict[str, Any] | None = None
    trigger_type: Literal["schedule", "interval", "once", "webhook", "manual"] | None = None
    cron: str | None = Field(default=None, max_length=120)
    interval_minutes: int | None = Field(default=None, ge=0, le=60 * 24 * 31)
    timezone: str | None = Field(default=None, max_length=64)
    run_at: datetime | None = None
    enabled: bool | None = None


class AutomationOut(ORM):
    id: str
    project_id: str
    name: str
    description: str
    target_type: str
    target_id: str
    input: dict[str, Any]
    trigger_type: str
    cron: str
    interval_minutes: int
    timezone: str
    run_at: datetime | None = None
    source: str = "form"
    enabled: bool
    next_run_at: datetime | None
    last_run_at: datetime | None
    last_status: str
    run_count: int
    created_at: datetime
    webhook_url: str | None = None


class ScheduleDraftIn(BaseModel):
    project_id: str
    text: str = Field(min_length=3, max_length=2000)
    timezone: str = Field(default="", max_length=64)
    agent_id: str | None = None


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class ScheduleChatIn(BaseModel):
    """One turn of the scheduling assistant. The client keeps the conversation and the current draft and sends both back."""

    project_id: str
    messages: list[ChatTurn] = Field(min_length=1, max_length=40)
    draft: dict[str, Any] | None = None
    timezone: str = Field(default="", max_length=64)


class UpcomingRun(BaseModel):
    automation_id: str
    name: str
    at: datetime
    trigger_type: str
    target_type: str
    target_id: str
