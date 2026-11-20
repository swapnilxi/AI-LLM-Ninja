from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import OrgContext, audit, get_org_ctx, require_role
from app.core.security import encrypt_json, mask
from app.modules.connectors.models import Connection
from app.modules.connectors.registry import CONNECTORS, connection_config, connection_tools
from app.modules.connectors.schemas import ConnectionIn, ConnectionUpdate

router = APIRouter(tags=["connectors"])


def _split(connector_key: str, config: dict[str, Any], existing: dict[str, Any] | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    connector = CONNECTORS[connector_key]
    fields = {f.key: f for f in connector.fields}
    public, secret = {}, {}
    for key, f in fields.items():
        val = config.get(key, None)
        if f.secret:
            if val in (None, "") or (isinstance(val, str) and "•" in val):
                if existing and existing.get(key):
                    secret[key] = existing[key]  # keep current secret
                continue
            secret[key] = str(val)[:10000]
        else:
            if val is None:
                val = (existing or {}).get(key, f.default)
            if val is not None:
                public[key] = val if isinstance(val, (bool, int, float)) else str(val)[:2000]
    missing = [f.label for k, f in fields.items() if f.required and not (public.get(k) or secret.get(k))]
    if missing:
        raise HTTPException(400, f"Missing required field(s): {', '.join(missing)}")
    return public, secret


def _out(conn: Connection) -> dict[str, Any]:
    connector = CONNECTORS.get(conn.connector_key)
    cfg = connection_config(conn)
    shown: dict[str, Any] = {}
    for f in connector.fields if connector else []:
        v = cfg.get(f.key)
        shown[f.key] = mask(str(v)) if f.secret and v else v
    return {
        "id": conn.id,
        "connector_key": conn.connector_key,
        "connector_name": connector.name if connector else conn.connector_key,
        "icon": connector.icon if connector else "plug",
        "name": conn.name,
        "config": shown,
        "enabled_tools": conn.enabled_tools or [],
        "enabled": conn.enabled,
        "status": conn.status,
        "created_at": conn.created_at,
    }


@router.get("/connectors/catalog")
async def catalog(ctx: OrgContext = Depends(get_org_ctx)):
    return [c.describe() for c in CONNECTORS.values()]


@router.get("/connections")
async def list_connections(ctx: OrgContext = Depends(get_org_ctx), session: AsyncSession = Depends(get_session)):
    rows = (await session.execute(select(Connection).where(Connection.org_id == ctx.org_id).order_by(Connection.created_at))).scalars().all()
    return [_out(c) for c in rows]


@router.post("/connections", status_code=201)
async def create_connection(body: ConnectionIn, request: Request, ctx: OrgContext = Depends(require_role("admin")), session: AsyncSession = Depends(get_session)):
    if body.connector_key not in CONNECTORS:
        raise HTTPException(404, "Unknown connector")
    count = (await session.execute(select(func.count()).select_from(Connection).where(Connection.org_id == ctx.org_id))).scalar_one()
    if count >= 100:
        raise HTTPException(400, "Connection limit reached")
    public, secret = _split(body.connector_key, body.config)
    conn = Connection(
        org_id=ctx.org_id,
        connector_key=body.connector_key,
        name=body.name,
        public_config=public,
        config_enc=encrypt_json(secret),
        enabled_tools=body.enabled_tools,
        enabled=body.enabled,
        created_by=ctx.user.id,
    )
    session.add(conn)
    await audit(session, action="connection.create", org_id=ctx.org_id, user_id=ctx.user.id, request=request, target_type="connection", target_id=conn.id, details={"connector": body.connector_key}, commit=False)
    await session.commit()
    return _out(conn)


async def _get(session: AsyncSession, ctx: OrgContext, conn_id: str) -> Connection:
    conn = await session.get(Connection, conn_id)
    if not conn or conn.org_id != ctx.org_id:
        raise HTTPException(404, "Connection not found")
    return conn


@router.get("/connections/{conn_id}")
async def read_connection(conn_id: str, ctx: OrgContext = Depends(get_org_ctx), session: AsyncSession = Depends(get_session)):
    return _out(await _get(session, ctx, conn_id))


@router.patch("/connections/{conn_id}")
async def update_connection(conn_id: str, body: ConnectionUpdate, request: Request, ctx: OrgContext = Depends(require_role("admin")), session: AsyncSession = Depends(get_session)):
    conn = await _get(session, ctx, conn_id)
    if body.name is not None:
        conn.name = body.name
    if body.enabled is not None:
        conn.enabled = body.enabled
    if body.enabled_tools is not None:
        conn.enabled_tools = body.enabled_tools
    if body.config is not None:
        public, secret = _split(conn.connector_key, body.config, connection_config(conn))
        conn.public_config = public
        conn.config_enc = encrypt_json(secret)
        conn.status = "unknown"
    await audit(session, action="connection.update", org_id=ctx.org_id, user_id=ctx.user.id, request=request, target_type="connection", target_id=conn.id, commit=False)
    await session.commit()
    return _out(conn)


@router.delete("/connections/{conn_id}", status_code=204)
async def delete_connection(conn_id: str, request: Request, ctx: OrgContext = Depends(require_role("admin")), session: AsyncSession = Depends(get_session)):
    conn = await _get(session, ctx, conn_id)
    await session.delete(conn)
    await audit(session, action="connection.delete", org_id=ctx.org_id, user_id=ctx.user.id, request=request, target_type="connection", target_id=conn_id)


@router.post("/connections/{conn_id}/test")
async def test_connection(conn_id: str, ctx: OrgContext = Depends(require_role("admin")), session: AsyncSession = Depends(get_session)):
    conn = await _get(session, ctx, conn_id)
    ok, message = await CONNECTORS[conn.connector_key].test(connection_config(conn))
    conn.status = "ok" if ok else "error"
    await session.commit()
    return {"ok": ok, "message": message}


@router.get("/connections/{conn_id}/tools")
async def connection_tool_list(conn_id: str, ctx: OrgContext = Depends(get_org_ctx), session: AsyncSession = Depends(get_session)):
    conn = await _get(session, ctx, conn_id)
    connector = CONNECTORS[conn.connector_key]
    cfg = connection_config(conn)
    actions = await connector.list_actions(cfg, conn.id)
    exposed = {t.meta.get("connection_id") and t.name for t in await connection_tools(conn)}
    return [
        {"action": a.name, "tool_name": f"{conn.connector_key}_{a.name}", "description": a.description, "write": a.write, "exposed": f"{conn.connector_key}_{a.name}" in exposed}
        for a in actions
    ]
