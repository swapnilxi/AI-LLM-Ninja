"""Database models for the chat module."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import TimestampMixin, UTCDateTime, _id, utcnow
from app.core.db import Base


class Conversation(TimestampMixin, Base):
    __tablename__ = "conversations"
    id: Mapped[str] = _id("cnv")
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(String(32))
    target_type: Mapped[str] = mapped_column(String(20))  # agent | team
    target_id: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(255), default="New chat")
    skill_ids: Mapped[list[str]] = mapped_column(JSON, default=list, server_default="[]")  # extra skills for this chat


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[str] = _id("msg")
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(20))  # user | assistant
    content: Mapped[str] = mapped_column(Text)
    run_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    meta: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
