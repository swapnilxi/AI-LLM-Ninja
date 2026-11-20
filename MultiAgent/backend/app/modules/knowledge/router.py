"""Documents (org / project / agent knowledge) and memories (agent / project)."""
from __future__ import annotations

import re

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import get_session
from app.core.deps import OrgContext, audit, get_org_ctx, get_project, get_visible, require_role
from app.engine.net import BlockedURL, safe_request
from app.modules.agents.models import Agent
from app.modules.knowledge import service as knowledge
from app.modules.knowledge.models import Document, Memory
from app.modules.knowledge.schemas import DocumentFromUrl, DocumentFull, DocumentIn, DocumentOut, DocumentUpdate, MemoryIn, MemoryOut, MemoryUpdate

router = APIRouter(tags=["knowledge"])
MAX_DOCS_PER_OWNER = 500


async def check_owner(session: AsyncSession, ctx: OrgContext, owner_type: str, owner_id: str) -> None:
    if owner_type == "org":
        if owner_id != ctx.org_id:
            raise HTTPException(404, "Organization not found")
    elif owner_type == "project":
        await get_project(session, owner_id, ctx.org_id)
    elif owner_type == "agent":
        await get_visible(session, Agent, owner_id, ctx.org_id)
    else:
        raise HTTPException(400, "owner_type must be org, project or agent")


async def _save(session: AsyncSession, ctx: OrgContext, *, owner_type: str, owner_id: str, title: str, content: str, source: str, source_ref: str = "", mime: str = "text/plain", pinned: bool = False) -> Document:
    await check_owner(session, ctx, owner_type, owner_id)
    if owner_type == "org":
        ctx.require("admin")
    count = (
        await session.execute(select(func.count()).select_from(Document).where(Document.org_id == ctx.org_id, Document.owner_type == owner_type, Document.owner_id == owner_id))
    ).scalar_one()
    if count >= MAX_DOCS_PER_OWNER:
        raise HTTPException(400, "Document limit reached for this owner")
    content = content.replace("\x00", "").strip()
    if not content:
        raise HTTPException(400, "Document has no extractable text")
    doc = Document(
        org_id=ctx.org_id, owner_type=owner_type, owner_id=owner_id, title=title[:255], content=content[:2_000_000],
        source=source, source_ref=source_ref[:1000], mime=mime[:100], pinned=pinned, created_by=ctx.user.id,
    )
    session.add(doc)
    await session.flush()
    await knowledge.index_document(session, doc)
    await session.commit()
    return doc


@router.get("/documents", response_model=list[DocumentOut])
async def list_documents(owner_type: str, owner_id: str, ctx: OrgContext = Depends(get_org_ctx), session: AsyncSession = Depends(get_session)):
    await check_owner(session, ctx, owner_type, owner_id)
    stmt = select(Document).where(Document.org_id == ctx.org_id, Document.owner_type == owner_type, Document.owner_id == owner_id).order_by(Document.created_at.desc())
    return (await session.execute(stmt)).scalars().all()


@router.post("/documents", response_model=DocumentOut, status_code=201)
async def create_document(body: DocumentIn, ctx: OrgContext = Depends(require_role("member")), session: AsyncSession = Depends(get_session)):
    return await _save(session, ctx, owner_type=body.owner_type, owner_id=body.owner_id, title=body.title, content=body.content, source="text", pinned=body.pinned)


@router.post("/documents/upload", response_model=DocumentOut, status_code=201)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    owner_type: str = Form(...),
    owner_id: str = Form(...),
    pinned: bool = Form(False),
    title: str | None = Form(None),
    ctx: OrgContext = Depends(require_role("member")),
    session: AsyncSession = Depends(get_session),
):
    filename = re.sub(r"[^\w.\- ]", "_", (file.filename or "upload.txt"))[:200]
    data = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"File too large (max {settings.max_upload_mb} MB)")
    try:
        text = knowledge.extract_text(filename, data)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(400, f"Could not read file: {exc}") from exc
    doc = await _save(session, ctx, owner_type=owner_type, owner_id=owner_id, title=title or filename, content=text, source="upload", source_ref=filename, mime=file.content_type or "", pinned=pinned)
    await audit(session, action="document.upload", org_id=ctx.org_id, user_id=ctx.user.id, request=request, target_type="document", target_id=doc.id, details={"file": filename, "bytes": len(data)})
    return doc


@router.post("/documents/from-url", response_model=DocumentOut, status_code=201)
async def document_from_url(body: DocumentFromUrl, ctx: OrgContext = Depends(require_role("member")), session: AsyncSession = Depends(get_session)):
    try:
        r = await safe_request("GET", body.url, max_bytes=5 * 1024 * 1024)
    except BlockedURL as exc:
        raise HTTPException(400, f"Blocked: {exc}") from exc
    except Exception as exc:
        raise HTTPException(400, f"Could not fetch URL: {exc}") from exc
    if r.status_code >= 400:
        raise HTTPException(400, f"URL returned HTTP {r.status_code}")
    ctype = r.headers.get("content-type", "")
    if "pdf" in ctype:
        text, title = knowledge.extract_text("doc.pdf", r.content), ""
    elif "html" in ctype:
        title, text = knowledge.html_to_text(r.text)
    else:
        text, title = r.text, ""
    return await _save(session, ctx, owner_type=body.owner_type, owner_id=body.owner_id, title=body.title or title or body.url, content=text, source="url", source_ref=r.url, mime=ctype, pinned=body.pinned)


async def _doc(session: AsyncSession, ctx: OrgContext, doc_id: str) -> Document:
    doc = await session.get(Document, doc_id)
    if not doc or doc.org_id != ctx.org_id:
        raise HTTPException(404, "Document not found")
    return doc


@router.get("/documents/search")
async def search_documents(
    q: str = Query(..., min_length=1, max_length=500),
    project_id: str | None = None,
    agent_id: str | None = None,
    top_k: int = Query(10, ge=1, le=50),
    agent_only: bool = Query(False, description="Search only the agent's own documents (skip org/project knowledge)"),
    ctx: OrgContext = Depends(get_org_ctx),
    session: AsyncSession = Depends(get_session),
):
    """Retrieve the chunks an agent would get from knowledge_search (used by the Training > Test playground)."""
    if project_id:
        await get_project(session, project_id, ctx.org_id)
    if agent_id:
        await get_visible(session, Agent, agent_id, ctx.org_id)
    if agent_only and not agent_id:
        raise HTTPException(400, "agent_only requires agent_id")
    owners = [("agent", agent_id)] if agent_only and agent_id else knowledge.owners_for(ctx.org_id, project_id, agent_id)
    return await knowledge.search(session, ctx.org_id, owners, q, top_k)


@router.get("/documents/{doc_id}", response_model=DocumentFull)
async def read_document(doc_id: str, ctx: OrgContext = Depends(get_org_ctx), session: AsyncSession = Depends(get_session)):
    return await _doc(session, ctx, doc_id)


@router.patch("/documents/{doc_id}", response_model=DocumentOut)
async def update_document(doc_id: str, body: DocumentUpdate, ctx: OrgContext = Depends(require_role("member")), session: AsyncSession = Depends(get_session)):
    doc = await _doc(session, ctx, doc_id)
    if doc.owner_type == "org":
        ctx.require("admin")
    if body.title is not None:
        doc.title = body.title
    if body.pinned is not None:
        doc.pinned = body.pinned
    if body.content is not None:
        doc.content = body.content
        await knowledge.index_document(session, doc)
    await session.commit()
    return doc


@router.delete("/documents/{doc_id}", status_code=204)
async def delete_document(doc_id: str, ctx: OrgContext = Depends(require_role("member")), session: AsyncSession = Depends(get_session)):
    doc = await _doc(session, ctx, doc_id)
    if doc.owner_type == "org":
        ctx.require("admin")
    await session.delete(doc)
    await session.commit()


# ------------------------------------------------------------------ memories
@router.get("/memories", response_model=list[MemoryOut])
async def list_memories(
    scope: str | None = Query(None, pattern="^(agent|project)$"),
    agent_id: str | None = None,
    project_id: str | None = None,
    q: str | None = Query(None, max_length=200),
    ctx: OrgContext = Depends(get_org_ctx),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(Memory).where(Memory.org_id == ctx.org_id)
    if scope:
        stmt = stmt.where(Memory.scope == scope)
    if agent_id:
        stmt = stmt.where(Memory.agent_id == agent_id)
    if project_id:
        stmt = stmt.where(Memory.project_id == project_id)
    if q:
        stmt = stmt.where(Memory.content.ilike(f"%{q}%"))
    return (await session.execute(stmt.order_by(Memory.created_at.desc()).limit(500))).scalars().all()


@router.post("/memories", response_model=MemoryOut, status_code=201)
async def create_memory(body: MemoryIn, ctx: OrgContext = Depends(require_role("member")), session: AsyncSession = Depends(get_session)):
    if body.scope == "agent":
        if not body.agent_id:
            raise HTTPException(400, "agent_id is required for agent memory")
        await get_visible(session, Agent, body.agent_id, ctx.org_id)
    else:
        if not body.project_id:
            raise HTTPException(400, "project_id is required for project memory")
        await get_project(session, body.project_id, ctx.org_id)
    m = Memory(
        org_id=ctx.org_id, scope=body.scope, agent_id=body.agent_id if body.scope == "agent" else None,
        project_id=body.project_id if body.scope == "project" else None, key=body.key, content=body.content, tags=body.tags, source="user",
    )
    session.add(m)
    await session.commit()
    return m


@router.patch("/memories/{memory_id}", response_model=MemoryOut)
async def update_memory(memory_id: str, body: MemoryUpdate, ctx: OrgContext = Depends(require_role("member")), session: AsyncSession = Depends(get_session)):
    m = await session.get(Memory, memory_id)
    if not m or m.org_id != ctx.org_id:
        raise HTTPException(404, "Memory not found")
    if body.key is not None:
        m.key = body.key
    if body.content is not None:
        m.content = body.content
    await session.commit()
    return m


@router.delete("/memories/{memory_id}", status_code=204)
async def delete_memory(memory_id: str, ctx: OrgContext = Depends(require_role("member")), session: AsyncSession = Depends(get_session)):
    m = await session.get(Memory, memory_id)
    if not m or m.org_id != ctx.org_id:
        raise HTTPException(404, "Memory not found")
    await session.delete(m)
    await session.commit()
