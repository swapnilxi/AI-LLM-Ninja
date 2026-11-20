"""Database models for the agents module."""
from __future__ import annotations

from typing import Any

from sqlalchemy import (
    JSON,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import TimestampMixin, _id
from app.core.db import Base


class Agent(TimestampMixin, Base):
    __tablename__ = "agents"
    id: Mapped[str] = _id("agt")
    org_id: Mapped[str | None] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    avatar: Mapped[str] = mapped_column(String(40), default="bot")  # icon key (flat icon set)
    color: Mapped[str] = mapped_column(String(20), default="indigo")
    provider: Mapped[str] = mapped_column(String(40), default="default")
    model: Mapped[str] = mapped_column(String(120), default="")
    system_prompt: Mapped[str] = mapped_column(Text, default="")
    temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_tokens: Mapped[int] = mapped_column(Integer, default=8000)
    max_steps: Mapped[int] = mapped_column(Integer, default=8)
    effort: Mapped[str] = mapped_column(String(10), default="medium")
    tool_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    skill_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    connection_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    # settings: browser_enabled, memory_enabled, knowledge_enabled, show_thinking, render_js
    settings: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
