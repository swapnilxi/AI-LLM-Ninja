"""Request/response schemas for the skills module (with input limits as a safeguard)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.core.schemas import ORM


class SkillIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=4000)
    instructions: str = Field(default="", max_length=50000)
    tool_ids: list[str] = Field(default_factory=list, max_length=50)
    tags: list[str] = Field(default_factory=list, max_length=20)
    command: str | None = Field(default=None, max_length=40)
    argument_hint: str = Field(default="", max_length=200)
    command_template: str = Field(default="", max_length=20000)
    scope: Literal["org", "global"] = "org"

    @field_validator("command")
    @classmethod
    def _cmd(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip().lstrip("/").lower()
        return v or None


class SkillImport(BaseModel):
    markdown: str = Field(min_length=1, max_length=60000)


class SkillInstall(BaseModel):
    command: str = Field(min_length=1, max_length=500)
    paths: list[str] | None = Field(default=None, max_length=200)


class SkillOut(ORM):
    id: str
    org_id: str | None
    name: str
    description: str
    instructions: str
    tool_ids: list[str]
    tags: list[str]
    command: str | None = None
    argument_hint: str | None = ""
    command_template: str | None = ""
    created_at: datetime
    updated_at: datetime
