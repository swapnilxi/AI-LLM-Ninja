"""Request/response schemas for the orgs module (with input limits as a safeguard)."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field

from app.core.schemas import ORM, Role


class OrgOut(ORM):
    id: str
    name: str
    slug: str
    context: str
    settings: dict[str, Any]
    created_at: datetime


class OrgWithRole(OrgOut):
    role: str


class OrgCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class OrgUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    context: str | None = Field(default=None, max_length=20000)
    settings: dict[str, Any] | None = None


class MemberOut(BaseModel):
    id: str
    user_id: str
    email: str
    name: str
    role: str
    created_at: datetime


class MemberAdd(BaseModel):
    email: EmailStr
    role: Role = "member"
    name: str | None = Field(default=None, max_length=120)
    password: str | None = Field(default=None, min_length=8, max_length=256)


class MemberUpdate(BaseModel):
    role: Role


class ProviderIn(BaseModel):
    api_key: str | None = Field(default=None, max_length=500)
    base_url: str | None = Field(default=None, max_length=500)


class SecretIn(BaseModel):
    name: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    value: str = Field(min_length=1, max_length=10000)
    description: str = Field(default="", max_length=300)


class ApiKeyIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    role: Role = "member"
    expires_in_days: int | None = Field(default=None, ge=1, le=3650)
