"""Database models for the workflows module."""
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


class Workflow(TimestampMixin, Base):
    __tablename__ = "workflows"
    id: Mapped[str] = _id("wf")
    org_id: Mapped[str | None] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    graph: Mapped[dict[str, Any]] = mapped_column(JSON, default=lambda: {"nodes": [], "edges": []})
    input_fields: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)  # [{name,label,type,default}]
    created_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
