"""Request/response schemas for the tools module (with input limits as a safeguard)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.core.schemas import ORM


class ToolIn(BaseModel):
    name: str = Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z][a-zA-Z0-9_-]*$")
    display_name: str = Field(default="", max_length=120)
    description: str = Field(default="", max_length=4000)
    kind: Literal["http", "agent"] = "http"
    category: str = Field(default="custom", max_length=40)
    parameters: dict[str, Any] = Field(default_factory=lambda: {"type": "object", "properties": {}, "required": []})
    config: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    scope: Literal["org", "global"] = "org"

    @field_validator("parameters")
    @classmethod
    def _params(cls, v: dict[str, Any]) -> dict[str, Any]:
        if v.get("type") != "object":
            raise ValueError("parameters must be a JSON schema with type 'object'")
        v.setdefault("properties", {})
        return v


class ToolOut(ORM):
    id: str
    org_id: str | None
    name: str
    display_name: str
    description: str
    kind: str
    builtin_key: str | None
    category: str
    parameters: dict[str, Any]
    config: dict[str, Any]
    enabled: bool
    created_at: datetime
    updated_at: datetime


class ToolTest(BaseModel):
    project_id: str
    arguments: dict[str, Any] = Field(default_factory=dict)
