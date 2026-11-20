"""Request/response schemas for the auth module (with input limits as a safeguard)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.core.schemas import ORM
from app.modules.orgs.schemas import OrgWithRole


class RegisterIn(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=8, max_length=256)
    org_name: str | None = Field(default=None, max_length=120)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class UserOut(ORM):
    id: str
    email: str
    name: str
    is_superadmin: bool
    created_at: datetime
    last_login_at: datetime | None = None


class UpdateMeIn(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    current_password: str | None = Field(default=None, max_length=256)
    new_password: str | None = Field(default=None, min_length=8, max_length=256)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
    orgs: list[OrgWithRole]
