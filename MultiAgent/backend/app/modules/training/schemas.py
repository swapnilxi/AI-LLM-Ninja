"""Request/response schemas for the training module (with input limits as a safeguard)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.core.schemas import ORM


LessonKind = Literal["rule", "fact", "example", "correction"]


class LessonIn(BaseModel):
    """`content` is the rule / fact / ideal answer / corrected behaviour. `prompt` is the question (example) or the mistake (correction)."""

    content: str = Field(min_length=1, max_length=2000)
    title: str = Field(default="", max_length=120)
    kind: LessonKind = "rule"
    prompt: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def _example_needs_question(self):
        if self.kind == "example" and not (self.prompt or "").strip():
            raise ValueError("A Q&A example needs a question (prompt)")
        return self


class LessonUpdate(BaseModel):
    content: str | None = Field(default=None, min_length=1, max_length=2000)
    title: str | None = Field(default=None, max_length=120)
    kind: LessonKind | None = None
    prompt: str | None = Field(default=None, max_length=2000)


class LessonOut(ORM):
    id: str
    agent_id: str
    status: str
    source: str
    kind: str = "rule"
    title: str
    content: str
    prompt: str | None = None
    rationale: str
    conversation_id: str | None
    message_id: str | None
    run_id: str | None
    memory_id: str | None
    created_at: datetime


class TrainingSettingsIn(BaseModel):
    auto_learn: bool


class ReflectIn(BaseModel):
    conversation_id: str | None = None
