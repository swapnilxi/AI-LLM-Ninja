"""Database models for the projects module."""
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


class Project(TimestampMixin, Base):
    __tablename__ = "projects"
    id: Mapped[str] = _id("prj")
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    context: Mapped[str] = mapped_column(Text, default="")  # project brief injected into every agent
    variables: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    # settings: web_access, browser_render_js, allowed_domains, blocked_domains, memory_enabled,
    #           shared_tool_ids, connection_ids, default_agent_id
    settings: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
