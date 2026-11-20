"""Database models for the scheduler module.

A schedule (table `automations`) runs an agent, team or workflow on a trigger: cron, fixed interval, once at a
given time, an incoming webhook, or manually.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import TimestampMixin, UTCDateTime, _id
from app.core.db import Base


class Automation(TimestampMixin, Base):
    __tablename__ = "automations"
    id: Mapped[str] = _id("auto")
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    target_type: Mapped[str] = mapped_column(String(20))  # agent | team | workflow
    target_id: Mapped[str] = mapped_column(String(32))
    input: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    trigger_type: Mapped[str] = mapped_column(String(20), default="manual")  # schedule | interval | once | webhook | manual
    cron: Mapped[str] = mapped_column(String(120), default="")
    interval_minutes: Mapped[int] = mapped_column(Integer, default=0)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    run_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)  # one-time ("once") schedules
    source: Mapped[str] = mapped_column(String(20), default="form", server_default="form")  # form | chat | agent
    webhook_token_enc: Mapped[str] = mapped_column(Text, default="")
    webhook_token_hash: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    next_run_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True, index=True)
    last_run_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    last_status: Mapped[str] = mapped_column(String(20), default="")
    run_count: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
