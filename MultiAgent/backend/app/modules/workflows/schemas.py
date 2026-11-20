"""Request/response schemas for the workflows module (with input limits as a safeguard)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.core.schemas import ORM


class WorkflowIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=4000)
    graph: dict[str, Any] = Field(default_factory=lambda: {"nodes": [], "edges": []})
    input_fields: list[dict[str, Any]] = Field(default_factory=list, max_length=30)
    scope: Literal["org", "global"] = "org"


class WorkflowOut(ORM):
    id: str
    org_id: str | None
    name: str
    description: str
    graph: dict[str, Any]
    input_fields: list[dict[str, Any]]
    created_at: datetime
    updated_at: datetime
