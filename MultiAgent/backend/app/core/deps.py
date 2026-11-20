"""Request dependencies: authentication, tenant (org) resolution, RBAC and scoped lookups."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, TypeVar

from fastapi import Depends, HTTPException, Request
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from .db import get_session
from .models import ApiKey, AuditLog, Membership, Organization, Project, User
from .ratelimit import client_ip
from .security import decode_access_token, sha256_hex

ROLE_RANK = {"viewer": 0, "member": 1, "admin": 2, "owner": 3}
T = TypeVar("T")


@dataclass
class Principal:
    user: User
    api_key: ApiKey | None = None


@dataclass
class OrgContext:
    user: User
    org: Organization
    role: str
    api_key: ApiKey | None = None

    @property
    def org_id(self) -> str:
        return self.org.id

    def has(self, min_role: str) -> bool:
        return ROLE_RANK.get(self.role, -1) >= ROLE_RANK[min_role]

    def require(self, min_role: str) -> None:
        if not self.has(min_role):
            raise HTTPException(403, f"Requires {min_role} role")


def _bearer(request: Request) -> str | None:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    key = request.headers.get("x-api-key")
    return key.strip() if key else None


async def get_principal(request: Request, session: AsyncSession = Depends(get_session)) -> Principal:
    token = _bearer(request)
    if not token:
        raise HTTPException(401, "Not authenticated", headers={"WWW-Authenticate": "Bearer"})

    if token.startswith("afk_"):
        key = (await session.execute(select(ApiKey).where(ApiKey.key_hash == sha256_hex(token)))).scalar_one_or_none()
        now = datetime.now(timezone.utc)
        if not key or key.revoked or (key.expires_at and _aware(key.expires_at) < now):
            raise HTTPException(401, "Invalid API key")
        user = await session.get(User, key.user_id)
        if not user or not user.is_active:
            raise HTTPException(401, "Invalid API key")
        key.last_used_at = now
        await session.commit()
        return Principal(user=user, api_key=key)

    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(401, "Invalid or expired token", headers={"WWW-Authenticate": "Bearer"})
    user = await session.get(User, payload["sub"])
    if not user or not user.is_active or user.token_version != payload.get("ver"):
        raise HTTPException(401, "Session expired, please sign in again")
    return Principal(user=user)


async def get_current_user(principal: Principal = Depends(get_principal)) -> User:
    return principal.user


async def get_org_ctx(
    request: Request,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> OrgContext:
    org_id = request.headers.get("x-org-id") or request.query_params.get("org_id")
    if principal.api_key:
        if org_id and org_id != principal.api_key.org_id:
            raise HTTPException(403, "API key is not valid for this organization")
        org_id = principal.api_key.org_id
    if not org_id:
        raise HTTPException(400, "Missing X-Org-Id header")
    membership = (
        await session.execute(
            select(Membership).where(Membership.org_id == org_id, Membership.user_id == principal.user.id)
        )
    ).scalar_one_or_none()
    if not membership:
        raise HTTPException(403, "You are not a member of this organization")
    org = await session.get(Organization, org_id)
    if not org:
        raise HTTPException(404, "Organization not found")
    role = membership.role
    if principal.api_key:  # an API key can never exceed its creator's role
        role = min(role, principal.api_key.role, key=lambda r: ROLE_RANK.get(r, 0))
    return OrgContext(user=principal.user, org=org, role=role, api_key=principal.api_key)


def require_role(min_role: str):
    async def dep(ctx: OrgContext = Depends(get_org_ctx)) -> OrgContext:
        ctx.require(min_role)
        return ctx

    return dep


# --------------------------------------------------------------------------- scoped lookups
def visible(model: Any, org_id: str):
    """SQL filter: resources owned by the org or in the global library."""
    return or_(model.org_id == org_id, model.org_id.is_(None))


async def get_visible(session: AsyncSession, model: type[T], obj_id: str, org_id: str) -> T:
    obj = await session.get(model, obj_id)
    if not obj or (obj.org_id is not None and obj.org_id != org_id):
        raise HTTPException(404, f"{model.__name__} not found")
    return obj


async def get_writable(session: AsyncSession, model: type[T], obj_id: str, ctx: OrgContext) -> T:
    obj = await get_visible(session, model, obj_id, ctx.org_id)
    if obj.org_id is None and not ctx.user.is_superadmin:
        raise HTTPException(403, "Global library items are read-only. Duplicate it into your organization to customize.")
    ctx.require("member")
    return obj


async def get_project(session: AsyncSession, project_id: str, org_id: str) -> Project:
    project = await session.get(Project, project_id)
    if not project or project.org_id != org_id:
        raise HTTPException(404, "Project not found")
    return project


async def filter_visible_ids(session: AsyncSession, model: Any, ids: list[str], org_id: str) -> list[str]:
    """Return only ids of `model` visible to the org (prevents cross-tenant references)."""
    if not ids:
        return []
    rows = (await session.execute(select(model.id).where(model.id.in_(ids), visible(model, org_id)))).scalars().all()
    allowed = set(rows)
    return [i for i in ids if i in allowed]


async def audit(
    session: AsyncSession,
    *,
    action: str,
    org_id: str | None,
    user_id: str | None,
    request: Request | None = None,
    target_type: str = "",
    target_id: str = "",
    details: dict[str, Any] | None = None,
    commit: bool = True,
) -> None:
    session.add(
        AuditLog(
            org_id=org_id,
            user_id=user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            ip=client_ip(request) if request else "",
            details=details or {},
        )
    )
    if commit:
        await session.commit()


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
