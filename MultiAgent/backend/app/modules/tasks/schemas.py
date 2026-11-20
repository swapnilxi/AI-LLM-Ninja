"""Request/response schemas for the tasks module (with input limits as a safeguard)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.core.schemas import ORM

TaskStatus = Literal["todo", "doing", "done"]


TaskPriority = Literal["low", "normal", "high"]


class TaskIn(BaseModel):
    project_id: str
    title: str = Field(min_length=1, max_length=255)
    notes: str = Field(default="", max_length=4000)
    context: str = Field(default="", max_length=8000)
    priority: TaskPriority = "normal"
    status: TaskStatus = "todo"
    due_at: datetime | None = None


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    notes: str | None = Field(default=None, max_length=4000)
    context: str | None = Field(default=None, max_length=8000)
    priority: TaskPriority | None = None
    status: TaskStatus | None = None
    due_at: datetime | None = None  # send null to clear (fields are applied with exclude_unset)


class TaskOut(ORM):
    id: str
    project_id: str
    title: str
    notes: str
    context: str
    status: str
    priority: str
    due_at: datetime | None
    completed_at: datetime | None
    source: str
    conversation_id: str | None
    message_id: str | None
    run_id: str | None
    created_at: datetime
    updated_at: datetime


class TaskItemIn(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    notes: str = Field(default="", max_length=4000)
    priority: TaskPriority = "normal"
    due_at: datetime | None = None


class TaskExtractIn(BaseModel):
    project_id: str
    text: str = Field(default="", max_length=20000)  # empty + message_id => use that chat message
    context: str = Field(default="", max_length=4000)  # extra background attached to every task ("context giver")
    hint: str = Field(default="", max_length=500)
    conversation_id: str | None = None
    message_id: str | None = None
    save: bool = False


class TaskBulkIn(BaseModel):
    project_id: str
    items: list[TaskItemIn] = Field(min_length=1, max_length=50)
    context: str = Field(default="", max_length=8000)
    conversation_id: str | None = None
    message_id: str | None = None
    source: Literal["chat", "text", "manual"] = "text"


class TaskRunIn(BaseModel):
    agent_id: str | None = None
