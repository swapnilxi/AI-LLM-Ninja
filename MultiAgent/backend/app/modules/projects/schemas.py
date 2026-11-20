"""Request/response schemas for the projects module (with input limits as a safeguard)."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.core.schemas import ORM


class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=4000)
    context: str = Field(default="", max_length=50000)
    variables: dict[str, Any] = Field(default_factory=dict)
    settings: dict[str, Any] = Field(default_factory=dict)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=4000)
    context: str | None = Field(default=None, max_length=50000)
    variables: dict[str, Any] | None = None
    settings: dict[str, Any] | None = None
    archived: bool | None = None


class ProjectOut(ORM):
    id: str
    org_id: str
    name: str
    description: str
    context: str
    variables: dict[str, Any]
    settings: dict[str, Any]
    archived: bool
    created_at: datetime
    updated_at: datetime
