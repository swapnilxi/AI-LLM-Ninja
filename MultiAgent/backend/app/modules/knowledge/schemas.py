"""Request/response schemas for the knowledge module (with input limits as a safeguard)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.core.schemas import ORM

OwnerType = Literal["org", "project", "agent"]


class DocumentIn(BaseModel):
    owner_type: OwnerType
    owner_id: str
    title: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1, max_length=2_000_000)
    pinned: bool = False


class DocumentFromUrl(BaseModel):
    owner_type: OwnerType
    owner_id: str
    url: str = Field(max_length=2000)
    title: str | None = Field(default=None, max_length=255)
    pinned: bool = False


class DocumentUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    content: str | None = Field(default=None, max_length=2_000_000)
    pinned: bool | None = None


class DocumentOut(ORM):
    id: str
    owner_type: str
    owner_id: str
    title: str
    source: str
    source_ref: str
    mime: str
    size: int
    chunk_count: int
    pinned: bool
    created_at: datetime
    updated_at: datetime


class DocumentFull(DocumentOut):
    content: str


class MemoryIn(BaseModel):
    scope: Literal["agent", "project"]
    agent_id: str | None = None
    project_id: str | None = None
    key: str = Field(default="", max_length=120)
    content: str = Field(min_length=1, max_length=4000)
    tags: list[str] = Field(default_factory=list, max_length=20)


class MemoryUpdate(BaseModel):
    key: str | None = Field(default=None, max_length=120)
    content: str | None = Field(default=None, max_length=4000)


class MemoryOut(ORM):
    id: str
    scope: str
    agent_id: str | None
    project_id: str | None
    key: str
    content: str
    tags: list[str]
    source: str
    run_id: str | None
    created_at: datetime
