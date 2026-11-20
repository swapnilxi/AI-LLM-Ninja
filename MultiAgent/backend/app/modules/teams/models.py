"""Database models for the teams module."""
from __future__ import annotations

from typing import Any

from sqlalchemy import (
    JSON,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import TimestampMixin, _id
from app.core.db import Base


class Team(TimestampMixin, Base):
    __tablename__ = "teams"
    id: Mapped[str] = _id("team")
    org_id: Mapped[str | None] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    style: Mapped[str] = mapped_column(String(20), default="sequential")
    members: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)  # [{agent_id, role, instructions}]
    manager_agent_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
