"""Document knowledge: text extraction, chunking, BM25 retrieval and pinned-context assembly.

Documents can be attached to an org, a project or an agent. At runtime an agent
searches the union of: its own docs + the current project's docs + the org's docs.
"""
from __future__ import annotations

import io
import math
import re
from collections import Counter
from typing import Any

from bs4 import BeautifulSoup
from sqlalchemy import and_, delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.knowledge.models import Document, DocumentChunk

TEXT_EXTS = {".txt", ".md", ".markdown", ".csv", ".tsv", ".json", ".log", ".yaml", ".yml", ".xml", ".ini", ".toml", ".py", ".js", ".ts", ".sql"}
ALLOWED_EXTS = TEXT_EXTS | {".html", ".htm", ".pdf", ".docx"}
_STOP = set(
    "a an the and or but if of to in on for with by at from as is are was were be been it its this that these those "
    "i you he she we they them our your their my me do does did can could should would will shall may might not no "
    "what which who whom how when where why about into over than then so such there here also just".split()
)


def tokenize(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in _STOP and len(t) > 1]


def html_to_text(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    title = (soup.title.string or "").strip() if soup.title and soup.title.string else ""
    for tag in soup(["script", "style", "noscript", "svg", "iframe", "nav", "footer", "header", "aside", "form"]):
        tag.decompose()
    main = soup.find("main") or soup.find("article") or soup.body or soup
    text = main.get_text("\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return title, text


def extract_text(filename: str, data: bytes) -> str:
    name = filename.lower()
    ext = name[name.rfind(".") :] if "." in name else ""
    if ext not in ALLOWED_EXTS:
        raise ValueError(f"Unsupported file type '{ext or filename}'. Allowed: {', '.join(sorted(ALLOWED_EXTS))}")
    if ext in TEXT_EXTS:
        return data.decode("utf-8", errors="replace")
    if ext in (".html", ".htm"):
        return html_to_text(data.decode("utf-8", errors="replace"))[1]
    if ext == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        if len(reader.pages) > 1000:
            raise ValueError("PDF has too many pages (max 1000)")
        return "\n\n".join((p.extract_text() or "") for p in reader.pages)
    if ext == ".docx":
        import docx  # python-docx

        d = docx.Document(io.BytesIO(data))
        return "\n".join(p.text for p in d.paragraphs)
    raise ValueError("Unsupported file type")


def chunk_text(text: str, size: int = 1200, overlap: int = 150) -> list[str]:
    text = text.replace("\r\n", "\n").strip()
    if not text:
        return []
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    buf = ""
    for p in paras:
        while len(p) > size:  # very long paragraph: hard split
            head, p = p[:size], p[size - overlap :]
            if buf:
                chunks.append(buf)
                buf = ""
            chunks.append(head)
        if len(buf) + len(p) + 2 <= size:
            buf = f"{buf}\n\n{p}" if buf else p
        else:
            if buf:
                chunks.append(buf)
            tail = buf[-overlap:] if buf else ""
            buf = f"{tail}\n\n{p}".strip() if tail else p
    if buf:
        chunks.append(buf)
    return chunks


async def index_document(session: AsyncSession, doc: Document) -> None:
    await session.execute(delete(DocumentChunk).where(DocumentChunk.document_id == doc.id))
    chunks = chunk_text(doc.content)
    for i, c in enumerate(chunks):
        session.add(
            DocumentChunk(document_id=doc.id, org_id=doc.org_id, owner_type=doc.owner_type, owner_id=doc.owner_id, idx=i, text=c)
        )
    doc.chunk_count = len(chunks)
    doc.size = len(doc.content.encode())


def owners_for(org_id: str, project_id: str | None, agent_id: str | None) -> list[tuple[str, str]]:
    owners = [("org", org_id)]
    if project_id:
        owners.append(("project", project_id))
    if agent_id:
        owners.append(("agent", agent_id))
    return owners


def _owner_filter(model: Any, owners: list[tuple[str, str]]):
    return or_(*[and_(model.owner_type == t, model.owner_id == i) for t, i in owners])


async def search(
    session: AsyncSession, org_id: str, owners: list[tuple[str, str]], query: str, top_k: int = 5, max_chunks: int = 8000
) -> list[dict[str, Any]]:
    q_terms = tokenize(query)
    if not q_terms or not owners:
        return []
    rows = (
        await session.execute(
            select(DocumentChunk.document_id, DocumentChunk.idx, DocumentChunk.text, DocumentChunk.owner_type)
            .where(DocumentChunk.org_id == org_id, _owner_filter(DocumentChunk, owners))
            .limit(max_chunks)
        )
    ).all()
    if not rows:
        return []
    docs_tokens = [tokenize(r.text) for r in rows]
    n = len(rows)
    avgdl = sum(len(t) for t in docs_tokens) / n or 1
    df: Counter = Counter()
    for toks in docs_tokens:
        df.update(set(toks))
    k1, b = 1.5, 0.75
    scored = []
    for r, toks in zip(rows, docs_tokens):
        tf = Counter(toks)
        dl = len(toks) or 1
        score = 0.0
        for term in q_terms:
            if term not in tf:
                continue
            idf = math.log(1 + (n - df[term] + 0.5) / (df[term] + 0.5))
            score += idf * (tf[term] * (k1 + 1)) / (tf[term] + k1 * (1 - b + b * dl / avgdl))
        if score > 0:
            scored.append((score, r))
    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:top_k]
    titles = {}
    if top:
        ids = list({r.document_id for _, r in top})
        titles = dict((await session.execute(select(Document.id, Document.title).where(Document.id.in_(ids)))).all())
    return [
        {
            "document_id": r.document_id,
            "title": titles.get(r.document_id, ""),
            "scope": r.owner_type,
            "chunk": r.idx,
            "score": round(s, 3),
            "text": r.text,
        }
        for s, r in top
    ]


async def pinned_documents(session: AsyncSession, org_id: str, owners: list[tuple[str, str]], max_chars: int = 16000) -> list[tuple[Document, str]]:
    docs = (
        (
            await session.execute(
                select(Document)
                .where(Document.org_id == org_id, Document.pinned.is_(True), _owner_filter(Document, owners))
                .order_by(Document.created_at)
            )
        )
        .scalars()
        .all()
    )
    out, used = [], 0
    for d in docs:
        remaining = max_chars - used
        if remaining <= 200:
            break
        body = d.content[:remaining]
        if len(d.content) > remaining:
            body += "\n…[truncated - use read_document for the full text]"
        out.append((d, body))
        used += len(body)
    return out


async def has_documents(session: AsyncSession, org_id: str, owners: list[tuple[str, str]]) -> bool:
    row = (
        await session.execute(select(Document.id).where(Document.org_id == org_id, _owner_filter(Document, owners)).limit(1))
    ).first()
    return row is not None
