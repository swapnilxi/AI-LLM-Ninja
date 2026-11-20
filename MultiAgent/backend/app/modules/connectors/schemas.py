"""Request/response schemas for the connectors module (with input limits as a safeguard)."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ConnectionIn(BaseModel):
    connector_key: str = Field(max_length=40)
    name: str = Field(min_length=1, max_length=120)
    config: dict[str, Any] = Field(default_factory=dict)
    enabled_tools: list[str] = Field(default_factory=list)
    enabled: bool = True


class ConnectionUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    config: dict[str, Any] | None = None
    enabled_tools: list[str] | None = None
    enabled: bool | None = None
