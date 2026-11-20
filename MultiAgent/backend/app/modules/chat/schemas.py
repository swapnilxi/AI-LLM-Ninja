"""Request/response schemas for the chat module (with input limits as a safeguard)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.core.schemas import ORM


class ConversationIn(BaseModel):
    project_id: str
    target_type: Literal["agent", "team"]
    target_id: str
    title: str = Field(default="New chat", max_length=255)


class ConversationOut(ORM):
    id: str
    project_id: str
    target_type: str
    target_id: str
    title: str
    skill_ids: list[str] | None = None
    created_at: datetime
    updated_at: datetime


class MessageIn(BaseModel):
    content: str = Field(min_length=1, max_length=100_000)


class MessageOut(ORM):
    id: str
    role: str
    content: str
    run_id: str | None
    meta: dict[str, Any]
    created_at: datetime


class ConversationUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    skill_ids: list[str] | None = Field(default=None, max_length=20)


class FeedbackIn(BaseModel):
    feedback: Literal["up", "down"] | None = None
    note: str = Field(default="", max_length=1000)
