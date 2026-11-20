"""Database models for the auth module."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import TimestampMixin, UTCDateTime, _id
from app.core.db import Base


class User(TimestampMixin, Base):
    __tablename__ = "users"
    id: Mapped[str] = _id("usr")
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    is_superadmin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    token_version: Mapped[int] = mapped_column(Integer, default=0)
    failed_logins: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
