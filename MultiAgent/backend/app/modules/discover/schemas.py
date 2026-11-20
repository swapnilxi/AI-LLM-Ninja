"""Request/response schemas for the hub module (with input limits as a safeguard)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class HubSkillInstall(BaseModel):
    pack_id: str | None = Field(default=None, max_length=80)  # a curated pack...
    source: str | None = Field(default=None, max_length=200)  # ...or a registry result: owner/repo + skill
    skill: str | None = Field(default=None, max_length=120)
    project_id: str | None = None  # also attach to this project (project-level skill)


class HubMcpInstall(BaseModel):
    server_id: str = Field(max_length=80)
    token: str = Field(default="", max_length=4000)
    name: str = Field(default="", max_length=120)
    project_id: str | None = None


class HubKnowledgeInstall(BaseModel):
    item_id: str = Field(max_length=80)
    project_id: str
    pinned: bool = False
