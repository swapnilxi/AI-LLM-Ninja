"""Database models for the training module."""
from __future__ import annotations

from sqlalchemy import (
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import TimestampMixin, _id
from app.core.db import Base


class Lesson(TimestampMixin, Base):
    """A proposed (or taught) lesson for an agent. Approved lessons become agent memories."""

    __tablename__ = "lessons"
    __table_args__ = (Index("ix_lessons_agent", "org_id", "agent_id", "status"),)
    id: Mapped[str] = _id("lsn")
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    agent_id: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending | approved | rejected
    source: Mapped[str] = mapped_column(String(20), default="auto")  # user | feedback | auto
    # rule | fact | example | correction. server_default so additive migration works on existing DBs.
    kind: Mapped[str] = mapped_column(String(20), default="rule", server_default="rule")
    title: Mapped[str] = mapped_column(String(120), default="")
    content: Mapped[str] = mapped_column(Text)
    # example: the question the ideal answer (content) responds to; correction: what the agent got wrong.
    prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    rationale: Mapped[str] = mapped_column(Text, default="")
    conversation_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    message_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    run_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    memory_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
