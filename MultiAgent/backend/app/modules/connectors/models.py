"""Database models for the connectors module."""
from __future__ import annotations

from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import TimestampMixin, _id
from app.core.db import Base


class Connection(TimestampMixin, Base):
    """An installed app connector (GitHub, Slack, Notion, MCP server, ...) for an org."""

    __tablename__ = "connections"
    id: Mapped[str] = _id("con")
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    connector_key: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(120))
    config_enc: Mapped[str] = mapped_column(Text, default="")  # encrypted JSON (tokens etc.)
    public_config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)  # non-secret fields
    enabled_tools: Mapped[list[str]] = mapped_column(JSON, default=list)  # empty = all
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(20), default="unknown")
    created_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
