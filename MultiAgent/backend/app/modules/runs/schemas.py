"""Request/response schemas for the runs module (with input limits as a safeguard)."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.core.schemas import ORM, TargetType


class RunCreate(BaseModel):
    project_id: str
    target_type: TargetType
    target_id: str
    input: dict[str, Any] = Field(default_factory=dict)
    wait: bool = False
    wait_timeout: int = Field(default=120, ge=1, le=600)


class RunOut(ORM):
    id: str
    project_id: str
    target_type: str
    target_id: str
    target_name: str
    status: str
    input: dict[str, Any]
    output: str
    error: str
    trigger: str
    automation_id: str | None
    conversation_id: str | None
    user_id: str | None
    usage: dict[str, Any]
    total_tokens: int
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class RunEventOut(ORM):
    id: int
    seq: int
    type: str
    agent: str
    node_id: str
    data: dict[str, Any]
    created_at: datetime
