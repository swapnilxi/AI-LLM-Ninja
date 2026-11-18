from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db import get_session
from ..deps import audit, get_current_user
from ..models import Membership, Organization, User
from ..ratelimit import client_ip, enforce
from ..schemas import LoginIn, OrgOut, OrgWithRole, RegisterIn, TokenOut, UpdateMeIn, UserOut
from ..security import DUMMY_HASH, create_access_token, hash_password, validate_password_strength, verify_password
from .common import create_default_project, slugify

router = APIRouter(prefix="/auth", tags=["auth"])


async def user_orgs(session: AsyncSession, user_id: str) -> list[OrgWithRole]:
    rows = (
        await session.execute(
            select(Organization, Membership.role)
            .join(Membership, Membership.org_id == Organization.id)
            .where(Membership.user_id == user_id)
            .order_by(Organization.created_at)
        )
    ).all()
    return [OrgWithRole(**OrgOut.model_validate(o).model_dump(), role=r) for o, r in rows]


async def _token_response(session: AsyncSession, user: User) -> TokenOut:
    return TokenOut(
        access_token=create_access_token(user.id, user.token_version),
        user=UserOut.model_validate(user),
        orgs=await user_orgs(session, user.id),
    )


@router.post("/register", response_model=TokenOut, status_code=201)
async def register(body: RegisterIn, request: Request, session: AsyncSession = Depends(get_session)):
    await enforce(f"auth:{client_ip(request)}", settings.rate_limit_auth_per_minute)
    user_count = (await session.execute(select(func.count()).select_from(User))).scalar_one()
    if not settings.registration_open and user_count > 0:
        raise HTTPException(403, "Registration is closed. Ask an admin to invite you.")
    if err := validate_password_strength(body.password):
        raise HTTPException(422, err)
    email = body.email.lower()
    if (await session.execute(select(User.id).where(User.email == email))).first():
        raise HTTPException(409, "An account with this email already exists")
    user = User(email=email, name=body.name.strip(), password_hash=hash_password(body.password), is_superadmin=user_count == 0)
    session.add(user)
    await session.flush()
    org_name = (body.org_name or f"{body.name.split()[0]}'s Workspace").strip()
    org = Organization(name=org_name, slug=slugify(org_name), settings={})
    session.add(org)
    await session.flush()
    session.add(Membership(org_id=org.id, user_id=user.id, role="owner"))
    await create_default_project(session, org)
    await audit(session, action="user.register", org_id=org.id, user_id=user.id, request=request, commit=False)
    await session.commit()
    return await _token_response(session, user)


@router.post("/login", response_model=TokenOut)
async def login(body: LoginIn, request: Request, session: AsyncSession = Depends(get_session)):
    email = body.email.lower()
    await enforce(f"auth:{client_ip(request)}", settings.rate_limit_auth_per_minute)
    await enforce(f"login:{email}", settings.rate_limit_auth_per_minute)
    user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if user and user.locked_until and user.locked_until > now:
        raise HTTPException(423, "Account temporarily locked after too many failed attempts. Try again later.")
    if not user:
        verify_password(body.password, DUMMY_HASH)  # equalise timing
        raise HTTPException(401, "Invalid email or password")
    if not verify_password(body.password, user.password_hash) or not user.is_active:
        user.failed_logins = (user.failed_logins or 0) + 1
        if user.failed_logins >= settings.login_max_failures:
            user.locked_until = now + timedelta(minutes=settings.login_lockout_minutes)
            user.failed_logins = 0
            await audit(session, action="user.locked", org_id=None, user_id=user.id, request=request, commit=False)
        await session.commit()
        raise HTTPException(401, "Invalid email or password")
    user.failed_logins = 0
    user.locked_until = None
    user.last_login_at = now
    await audit(session, action="user.login", org_id=None, user_id=user.id, request=request, commit=False)
    await session.commit()
    return await _token_response(session, user)


@router.get("/me", response_model=TokenOut)
async def me(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    return await _token_response(session, user)


@router.patch("/me", response_model=TokenOut)
async def update_me(body: UpdateMeIn, request: Request, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    user = await session.get(User, user.id)
    if body.name:
        user.name = body.name.strip()
    if body.new_password:
        if not body.current_password or not verify_password(body.current_password, user.password_hash):
            raise HTTPException(400, "Current password is incorrect")
        if err := validate_password_strength(body.new_password):
            raise HTTPException(422, err)
        user.password_hash = hash_password(body.new_password)
        user.token_version += 1  # sign out other sessions
        await audit(session, action="user.password_changed", org_id=None, user_id=user.id, request=request, commit=False)
    await session.commit()
    return await _token_response(session, user)


@router.post("/logout-all", status_code=204)
async def logout_all(request: Request, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    user = await session.get(User, user.id)
    user.token_version += 1
    await audit(session, action="user.logout_all", org_id=None, user_id=user.id, request=request)
