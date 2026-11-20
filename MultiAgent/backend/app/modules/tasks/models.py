"""Database models for the tasks module."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import TimestampMixin, UTCDateTime, _id
from app.core.db import Base


class Task(TimestampMixin, Base):
    """A to-do item. Created by hand, from chat text ("text to task") or by an agent's task tools."""

    __tablename__ = "tasks"
    __table_args__ = (Index("ix_tasks_project_status", "org_id", "project_id", "status"),)
    id: Mapped[str] = _id("tsk")
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    notes: Mapped[str] = mapped_column(Text, default="")
    # Background handed to whoever works on the task. Filled from the source text; passed to the agent on "Run".
    context: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="todo")  # todo | doing | done
    priority: Mapped[str] = mapped_column(String(10), default="normal")  # low | normal | high
    due_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    source: Mapped[str] = mapped_column(String(20), default="manual")  # manual | chat | agent | text
    conversation_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    message_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    run_id: Mapped[str | None] = mapped_column(String(32), nullable=True)  # latest run started for this task
    created_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
