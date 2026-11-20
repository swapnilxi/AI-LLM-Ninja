"""Database models for the skills module."""
from __future__ import annotations

from sqlalchemy import (
    JSON,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import TimestampMixin, _id
from app.core.db import Base


class Skill(TimestampMixin, Base):
    __tablename__ = "skills"
    id: Mapped[str] = _id("skl")
    org_id: Mapped[str | None] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    instructions: Mapped[str] = mapped_column(Text, default="")
    tool_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    # Slash command: "/command args" in chat, API, automations or webhooks applies this skill to the run.
    command: Mapped[str | None] = mapped_column(String(40), nullable=True)
    argument_hint: Mapped[str] = mapped_column(String(200), default="", server_default="")
    # Optional prompt template for the command; {{ args }} is what the user typed after the command.
    command_template: Mapped[str] = mapped_column(Text, default="", server_default="")
    created_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
