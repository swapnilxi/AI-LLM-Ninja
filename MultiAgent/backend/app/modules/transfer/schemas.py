"""Request/response schemas for the transfer module (with input limits as a safeguard)."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ExportIn(BaseModel):
    agent_ids: list[str] = Field(default_factory=list, max_length=200)
    skill_ids: list[str] = Field(default_factory=list, max_length=200)
    tool_ids: list[str] = Field(default_factory=list, max_length=200)
    team_ids: list[str] = Field(default_factory=list, max_length=200)
    workflow_ids: list[str] = Field(default_factory=list, max_length=200)
    include_dependencies: bool = True


class ImportIn(BaseModel):
    bundle: dict[str, Any]
