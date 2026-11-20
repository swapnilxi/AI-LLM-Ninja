from __future__ import annotations

import secrets as pysecrets
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.common import create_default_project, slugify
from app.core.config import settings
from app.core.db import get_session
from app.core.deps import OrgContext, audit, get_current_user, get_org_ctx, require_role
from app.core.security import decrypt, encrypt, generate_api_key, hash_password, mask, sha256_hex, validate_password_strength
from app.engine.llm.base import LLMError, ModelSettings
from app.engine.llm.registry import PROVIDERS, default_model_for, env_key, get_provider, org_credentials, resolve_model
from app.modules.auth.models import User
from app.modules.auth.router import user_orgs
from app.modules.orgs.models import ApiKey, AuditLog, Membership, Organization, ProviderCredential, Secret
from app.modules.orgs.schemas import ApiKeyIn, MemberAdd, MemberOut, MemberUpdate, OrgCreate, OrgOut, OrgUpdate, OrgWithRole, ProviderIn, SecretIn
from app.modules.runs.models import Run
from app.modules.runs.service import daily_limit, tokens_used_today

router = APIRouter(tags=["organization"])

ALLOWED_ORG_SETTINGS = {
    "default_provider": str,
    "default_model": str,
    "daily_token_limit": int,
    "max_concurrent_runs": int,
    "allowed_providers": list,
    "web_search_provider": str,
}


@router.get("/orgs", response_model=list[OrgWithRole])
async def list_orgs(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    return await user_orgs(session, user.id)


@router.post("/orgs", response_model=OrgWithRole, status_code=201)
async def create_org(body: OrgCreate, request: Request, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    owned = (await session.execute(select(func.count()).select_from(Membership).where(Membership.user_id == user.id, Membership.role == "owner"))).scalar_one()
    if owned >= 20 and not user.is_superadmin:
        raise HTTPException(400, "Organization limit reached")
    org = Organization(name=body.name.strip(), slug=slugify(body.name), settings={})
    session.add(org)
    await session.flush()
    session.add(Membership(org_id=org.id, user_id=user.id, role="owner"))
    await create_default_project(session, org)
    await audit(session, action="org.create", org_id=org.id, user_id=user.id, request=request, commit=False)
    await session.commit()
    return OrgWithRole(**OrgOut.model_validate(org).model_dump(), role="owner")


@router.get("/org", response_model=OrgWithRole)
async def get_org(ctx: OrgContext = Depends(get_org_ctx)):
    return OrgWithRole(**OrgOut.model_validate(ctx.org).model_dump(), role=ctx.role)


@router.patch("/org", response_model=OrgWithRole)
async def update_org(body: OrgUpdate, request: Request, ctx: OrgContext = Depends(require_role("admin")), session: AsyncSession = Depends(get_session)):
    org = await session.get(Organization, ctx.org_id)
    if body.name is not None:
        org.name = body.name.strip() or org.name
    if body.context is not None:
        org.context = body.context
    if body.settings is not None:
        merged = dict(org.settings or {})
        for k, v in body.settings.items():
            if k not in ALLOWED_ORG_SETTINGS:
                raise HTTPException(400, f"Unknown org setting '{k}'")
            if v is not None and not isinstance(v, ALLOWED_ORG_SETTINGS[k]):
                raise HTTPException(400, f"Setting '{k}' has the wrong type")
            if k == "default_provider" and v and v not in PROVIDERS:
                raise HTTPException(400, "Unknown provider")
            if k in ("daily_token_limit", "max_concurrent_runs") and v is not None and v < 0:
                raise HTTPException(400, f"{k} must be >= 0")
            if v is None or v == "":
                merged.pop(k, None)
            else:
                merged[k] = v
        org.settings = merged
    await audit(session, action="org.update", org_id=org.id, user_id=ctx.user.id, request=request, details={"fields": list(body.model_dump(exclude_none=True))}, commit=False)
    await session.commit()
    return OrgWithRole(**OrgOut.model_validate(org).model_dump(), role=ctx.role)


@router.delete("/org", status_code=204)
async def delete_org(request: Request, ctx: OrgContext = Depends(require_role("owner")), session: AsyncSession = Depends(get_session)):
    count = (await session.execute(select(func.count()).select_from(Membership).where(Membership.user_id == ctx.user.id))).scalar_one()
    if count <= 1:
        raise HTTPException(400, "You cannot delete your only organization")
    org = await session.get(Organization, ctx.org_id)
    await session.delete(org)
    await audit(session, action="org.delete", org_id=None, user_id=ctx.user.id, request=request, target_id=ctx.org_id)


# ------------------------------------------------------------------ members
@router.get("/org/members", response_model=list[MemberOut])
async def list_members(ctx: OrgContext = Depends(get_org_ctx), session: AsyncSession = Depends(get_session)):
    rows = (
        await session.execute(
            select(Membership, User).join(User, User.id == Membership.user_id).where(Membership.org_id == ctx.org_id).order_by(Membership.created_at)
        )
    ).all()
    return [MemberOut(id=m.id, user_id=u.id, email=u.email, name=u.name, role=m.role, created_at=m.created_at) for m, u in rows]


@router.post("/org/members", status_code=201)
async def add_member(body: MemberAdd, request: Request, ctx: OrgContext = Depends(require_role("admin")), session: AsyncSession = Depends(get_session)):
    if body.role == "owner" and ctx.role != "owner":
        raise HTTPException(403, "Only owners can add owners")
    email = body.email.lower()
    user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
    temp_password = None
    if not user:
        password = body.password or pysecrets.token_urlsafe(12)
        if body.password and (err := validate_password_strength(body.password)):
            raise HTTPException(422, err)
        temp_password = None if body.password else password
        user = User(email=email, name=body.name or email.split("@")[0], password_hash=hash_password(password))
        session.add(user)
        await session.flush()
    exists = (await session.execute(select(Membership).where(Membership.org_id == ctx.org_id, Membership.user_id == user.id))).scalar_one_or_none()
    if exists:
        raise HTTPException(409, "User is already a member")
    m = Membership(org_id=ctx.org_id, user_id=user.id, role=body.role)
    session.add(m)
    await audit(session, action="member.add", org_id=ctx.org_id, user_id=ctx.user.id, request=request, target_type="user", target_id=user.id, details={"role": body.role}, commit=False)
    await session.commit()
    out = MemberOut(id=m.id, user_id=user.id, email=user.email, name=user.name, role=m.role, created_at=m.created_at)
    if temp_password:
        return {**out.model_dump(), "temporary_password": temp_password}
    return out


async def _owner_count(session: AsyncSession, org_id: str) -> int:
    return (await session.execute(select(func.count()).select_from(Membership).where(Membership.org_id == org_id, Membership.role == "owner"))).scalar_one()


@router.patch("/org/members/{member_id}", response_model=MemberOut)
async def update_member(member_id: str, body: MemberUpdate, request: Request, ctx: OrgContext = Depends(require_role("admin")), session: AsyncSession = Depends(get_session)):
    m = await session.get(Membership, member_id)
    if not m or m.org_id != ctx.org_id:
        raise HTTPException(404, "Member not found")
    if (m.role == "owner" or body.role == "owner") and ctx.role != "owner":
        raise HTTPException(403, "Only owners can change owner roles")
    if m.role == "owner" and body.role != "owner" and await _owner_count(session, ctx.org_id) <= 1:
        raise HTTPException(400, "An organization needs at least one owner")
    m.role = body.role
    await audit(session, action="member.role", org_id=ctx.org_id, user_id=ctx.user.id, request=request, target_type="member", target_id=m.id, details={"role": body.role}, commit=False)
    await session.commit()
    u = await session.get(User, m.user_id)
    return MemberOut(id=m.id, user_id=u.id, email=u.email, name=u.name, role=m.role, created_at=m.created_at)


@router.delete("/org/members/{member_id}", status_code=204)
async def remove_member(member_id: str, request: Request, ctx: OrgContext = Depends(require_role("admin")), session: AsyncSession = Depends(get_session)):
    m = await session.get(Membership, member_id)
    if not m or m.org_id != ctx.org_id:
        raise HTTPException(404, "Member not found")
    if m.role == "owner":
        if ctx.role != "owner":
            raise HTTPException(403, "Only owners can remove owners")
        if await _owner_count(session, ctx.org_id) <= 1:
            raise HTTPException(400, "An organization needs at least one owner")
    await session.execute(delete(ApiKey).where(ApiKey.org_id == ctx.org_id, ApiKey.user_id == m.user_id))
    await session.delete(m)
    await audit(session, action="member.remove", org_id=ctx.org_id, user_id=ctx.user.id, request=request, target_type="user", target_id=m.user_id)


# ------------------------------------------------------------------ model providers
@router.get("/org/providers")
async def list_providers(ctx: OrgContext = Depends(get_org_ctx), session: AsyncSession = Depends(get_session)):
    creds = await org_credentials(session, ctx.org_id)
    out = []
    for key, meta in PROVIDERS.items():
        c = creds.get(key)
        key_val = decrypt(c.api_key_enc) if c else ""
        out.append(
            {
                "key": key,
                "label": meta["label"],
                "models": meta["models"],
                "needs_key": meta["needs_key"],
                "supports_temperature": meta["supports_temperature"],
                "docs": meta["docs"],
                "default_base_url": meta["base_url"],
                "configured": bool(key_val) or (not meta["needs_key"] and key != "openai_compatible") or bool(c and c.base_url),
                "org_key": mask(key_val) if ctx.has("admin") else ("set" if key_val else ""),
                "base_url": c.base_url if c else "",
                "server_key": bool(env_key(key)),
            }
        )
    p, m = await resolve_model(session, ctx.org, "default", "")
    return {"providers": out, "default": {"provider": p, "model": m}}


@router.put("/org/providers/{provider}")
async def set_provider(provider: str, body: ProviderIn, request: Request, ctx: OrgContext = Depends(require_role("admin")), session: AsyncSession = Depends(get_session)):
    if provider not in PROVIDERS or provider == "mock":
        raise HTTPException(404, "Unknown provider")
    cred = (await org_credentials(session, ctx.org_id)).get(provider)
    if not cred:
        cred = ProviderCredential(org_id=ctx.org_id, provider=provider)
        session.add(cred)
    if body.api_key is not None and "•" not in body.api_key:
        cred.api_key_enc = encrypt(body.api_key.strip())
    if body.base_url is not None:
        url = body.base_url.strip()
        if url and not url.startswith(("https://", "http://")):
            raise HTTPException(400, "Base URL must start with http(s)://")
        cred.base_url = url
    await audit(session, action="provider.update", org_id=ctx.org_id, user_id=ctx.user.id, request=request, target_id=provider, commit=False)
    await session.commit()
    return {"ok": True}


@router.delete("/org/providers/{provider}", status_code=204)
async def delete_provider(provider: str, request: Request, ctx: OrgContext = Depends(require_role("admin")), session: AsyncSession = Depends(get_session)):
    await session.execute(delete(ProviderCredential).where(ProviderCredential.org_id == ctx.org_id, ProviderCredential.provider == provider))
    await audit(session, action="provider.delete", org_id=ctx.org_id, user_id=ctx.user.id, request=request, target_id=provider)


@router.post("/org/providers/{provider}/test")
async def test_provider(provider: str, model: str | None = None, ctx: OrgContext = Depends(require_role("admin")), session: AsyncSession = Depends(get_session)):
    try:
        llm = await get_provider(session, ctx.org, provider)
        resp = await llm.complete(
            system="You are a connectivity check.",
            messages=[{"role": "user", "content": "Reply with the single word: OK"}],
            tools=[],
            settings=ModelSettings(model=model or default_model_for(provider), max_tokens=1024, effort="low"),
        )
        return {"ok": True, "message": f"Model replied: {resp.text.strip()[:80]}"}
    except LLMError as exc:
        return {"ok": False, "message": str(exc)}
    except Exception as exc:
        return {"ok": False, "message": f"{type(exc).__name__}: {str(exc)[:300]}"}


# ------------------------------------------------------------------ secrets
@router.get("/org/secrets")
async def list_secrets(ctx: OrgContext = Depends(require_role("admin")), session: AsyncSession = Depends(get_session)):
    rows = (await session.execute(select(Secret).where(Secret.org_id == ctx.org_id).order_by(Secret.name))).scalars().all()
    return [{"id": r.id, "name": r.name, "description": r.description, "preview": mask(decrypt(r.value_enc)), "updated_at": r.updated_at} for r in rows]


@router.post("/org/secrets", status_code=201)
async def upsert_secret(body: SecretIn, request: Request, ctx: OrgContext = Depends(require_role("admin")), session: AsyncSession = Depends(get_session)):
    row = (await session.execute(select(Secret).where(Secret.org_id == ctx.org_id, Secret.name == body.name))).scalar_one_or_none()
    if not row:
        count = (await session.execute(select(func.count()).select_from(Secret).where(Secret.org_id == ctx.org_id))).scalar_one()
        if count >= 200:
            raise HTTPException(400, "Secret limit reached")
        row = Secret(org_id=ctx.org_id, name=body.name, value_enc="")
        session.add(row)
    row.value_enc = encrypt(body.value)
    row.description = body.description
    await audit(session, action="secret.upsert", org_id=ctx.org_id, user_id=ctx.user.id, request=request, target_id=body.name, commit=False)
    await session.commit()
    return {"id": row.id, "name": row.name}


@router.delete("/org/secrets/{secret_id}", status_code=204)
async def delete_secret(secret_id: str, request: Request, ctx: OrgContext = Depends(require_role("admin")), session: AsyncSession = Depends(get_session)):
    row = await session.get(Secret, secret_id)
    if not row or row.org_id != ctx.org_id:
        raise HTTPException(404, "Secret not found")
    await session.delete(row)
    await audit(session, action="secret.delete", org_id=ctx.org_id, user_id=ctx.user.id, request=request, target_id=row.name)


# ------------------------------------------------------------------ API keys
@router.get("/org/api-keys")
async def list_api_keys(ctx: OrgContext = Depends(require_role("admin")), session: AsyncSession = Depends(get_session)):
    rows = (await session.execute(select(ApiKey).where(ApiKey.org_id == ctx.org_id).order_by(ApiKey.created_at.desc()))).scalars().all()
    return [
        {"id": k.id, "name": k.name, "prefix": k.prefix, "role": k.role, "revoked": k.revoked, "expires_at": k.expires_at, "last_used_at": k.last_used_at, "created_at": k.created_at}
        for k in rows
    ]


@router.post("/org/api-keys", status_code=201)
async def create_api_key(body: ApiKeyIn, request: Request, ctx: OrgContext = Depends(require_role("admin")), session: AsyncSession = Depends(get_session)):
    if body.role == "owner":
        raise HTTPException(400, "API keys cannot have the owner role")
    raw = generate_api_key()
    key = ApiKey(
        org_id=ctx.org_id,
        user_id=ctx.user.id,
        name=body.name,
        prefix=raw[:10],
        key_hash=sha256_hex(raw),
        role=body.role,
        expires_at=datetime.now(timezone.utc) + timedelta(days=body.expires_in_days) if body.expires_in_days else None,
    )
    session.add(key)
    await audit(session, action="apikey.create", org_id=ctx.org_id, user_id=ctx.user.id, request=request, target_id=key.prefix, commit=False)
    await session.commit()
    return {"id": key.id, "key": raw, "prefix": key.prefix, "note": "Copy this key now - it will not be shown again."}


@router.delete("/org/api-keys/{key_id}", status_code=204)
async def revoke_api_key(key_id: str, request: Request, ctx: OrgContext = Depends(require_role("admin")), session: AsyncSession = Depends(get_session)):
    key = await session.get(ApiKey, key_id)
    if not key or key.org_id != ctx.org_id:
        raise HTTPException(404, "API key not found")
    key.revoked = True
    await audit(session, action="apikey.revoke", org_id=ctx.org_id, user_id=ctx.user.id, request=request, target_id=key.prefix)


# ------------------------------------------------------------------ audit & usage
@router.get("/org/audit")
async def audit_log(limit: int = Query(100, le=500), offset: int = 0, ctx: OrgContext = Depends(require_role("admin")), session: AsyncSession = Depends(get_session)):
    rows = (
        await session.execute(
            select(AuditLog, User.email)
            .outerjoin(User, User.id == AuditLog.user_id)
            .where(AuditLog.org_id == ctx.org_id)
            .order_by(AuditLog.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
    ).all()
    return [
        {"id": a.id, "action": a.action, "user": email or "", "target_type": a.target_type, "target_id": a.target_id, "ip": a.ip, "details": a.details, "created_at": a.created_at}
        for a, email in rows
    ]


@router.get("/org/usage")
async def usage(ctx: OrgContext = Depends(get_org_ctx), session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    used = await tokens_used_today(session, ctx.org_id)
    limit = daily_limit(ctx.org)
    active = (await session.execute(select(func.count()).select_from(Run).where(Run.org_id == ctx.org_id, Run.status.in_(["queued", "running"])))).scalar_one()
    return {
        "tokens_today": used,
        "daily_token_limit": limit,
        "active_runs": active,
        "max_concurrent_runs": int((ctx.org.settings or {}).get("max_concurrent_runs") or settings.max_concurrent_runs_per_org),
    }
