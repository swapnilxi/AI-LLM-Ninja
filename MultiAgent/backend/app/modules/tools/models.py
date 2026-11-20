"""Database models for the tools module."""
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


class Tool(TimestampMixin, Base):
    __tablename__ = "tools"
    id: Mapped[str] = _id("tool")
    org_id: Mapped[str | None] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(64))  # function name exposed to the model
    display_name: Mapped[str] = mapped_column(String(120), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    kind: Mapped[str] = mapped_column(String(20), default="http")  # builtin | http | agent
    builtin_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    category: Mapped[str] = mapped_column(String(40), default="custom")
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)  # JSON schema
    config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
