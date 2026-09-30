# utils.py — FILE SCANNER + CHUNKER + EMBEDDER WITH DEDUPE LOGIC (asyncpg / document_chunks flavour)
#
# The original helper module, cleaned up and wired into the app:
#   * embeddings come from the configured provider (app/embeddings) instead of a SentenceTransformer that
#     was loaded at import time (which made `import utils` take seconds and required torch);
#   * chunk size / overlap / documents folder come from the layered config (defaults < .env < UI);
#   * database calls go to app/core/db.py.
# The running API uses app/ingestion/* (sync, provider-agnostic); this module is the simple, readable
# version to learn from and to script with:  python -m app.utils.utils
import hashlib
import os
from datetime import datetime, timezone
from typing import Iterator, List, Optional, Tuple

from ..config import Settings, current_settings
from ..embeddings import build_embedder
from ..ingestion.loaders import SUPPORTED


def _s(settings: Optional[Settings]) -> Settings:
    return settings or current_settings()


# -----------------------------------------------------------------------------
# TEXT NORMALIZATION + HASHES
# -----------------------------------------------------------------------------
def normalize_text(s: str) -> str:
    # STABLE, DETERMINISTIC NORMALIZATION
    return " ".join((s or "").split())


def sha256_bytes(b: bytes) -> str:
    h = hashlib.sha256()
    h.update(b)
    return h.hexdigest()


def sha256_text(s: str) -> str:
    return sha256_bytes(s.encode("utf-8"))


def file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


# -----------------------------------------------------------------------------
# FILE LOADING
# -----------------------------------------------------------------------------
def load_pdf_file(path: str) -> str:
    from pypdf import PdfReader  # pypdf replaces pdfplumber (one PDF dependency for the whole app)

    parts = [(page.extract_text() or "") for page in PdfReader(path).pages]
    return "\n".join(p for p in parts if p)


def load_txt_file(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def yield_files(folder: Optional[str] = None) -> Iterator[str]:
    # YIELD ONLY SUPPORTED FILE TYPES (.txt .md .pdf .csv .json .html .docx)
    root = folder or str(_s(None).data_dir())
    if not os.path.isdir(root):
        return
    for fname in sorted(os.listdir(root)):
        path = os.path.join(root, fname)
        if os.path.isfile(path) and not fname.startswith(".") and os.path.splitext(fname)[1].lower() in SUPPORTED:
            yield path


def load_document(path: str) -> str:
    """Full text of one file (any supported type)."""
    from ..ingestion.loaders import load_file
    from pathlib import Path

    return "\n".join(text for _, text in load_file(Path(path)))


def load_documents(folder: Optional[str] = None) -> List[str]:
    """Return the full text of every supported document in the folder."""
    return [load_document(p) for p in yield_files(folder)]


# -----------------------------------------------------------------------------
# CHUNKING
# -----------------------------------------------------------------------------
def chunk_text(text: str, chunk_size: Optional[int] = None, overlap: Optional[int] = None) -> List[str]:
    """Simple sliding window over normalized text. (app/ingestion/chunker.py is the smarter,
    paragraph/sentence-aware splitter the running app uses.)"""
    s = _s(None)
    chunk_size = chunk_size or s.chunk_size
    overlap = s.chunk_overlap if overlap is None else overlap
    text = normalize_text(text)
    step = max(1, chunk_size - max(0, overlap))  # SAFETY FOR OVERLAP >= CHUNK
    return [text[i : i + chunk_size] for i in range(0, len(text), step)]


# -----------------------------------------------------------------------------
# EMBEDDING (delegates to the configured provider: sentence-transformers / ollama / gemini / openai)
# -----------------------------------------------------------------------------
def embed_text(s: str, settings: Optional[Settings] = None) -> List[float]:
    return build_embedder(_s(settings)).embed_query(s)


def embed_texts_batched(texts: List[str], settings: Optional[Settings] = None) -> List[List[float]]:
    # the embedder batches internally in provider-appropriate sizes
    return build_embedder(_s(settings)).embed_documents(texts)


# -----------------------------------------------------------------------------
# HIGH-LEVEL: FILE -> CHUNKS + EMBEDDINGS (+ CHUNK HASH)
# -----------------------------------------------------------------------------
def process_file_to_chunks_and_embeddings(
    file_path: str, chunk_size: Optional[int] = None, overlap: Optional[int] = None
) -> List[Tuple[int, str, List[float], str]]:
    """Returns list of (chunk_index, chunk_text, embedding, chunk_sha256)."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext not in SUPPORTED:
        raise ValueError(f"Unsupported file type: {file_path}")
    chunks = [c for c in chunk_text(load_document(file_path), chunk_size, overlap) if c]
    embeddings = embed_texts_batched(chunks)
    return [(idx, t, emb, sha256_text(t)) for idx, (t, emb) in enumerate(zip(chunks, embeddings))]


# -----------------------------------------------------------------------------
# INDEXING PIPELINE (SKIPS UNCHANGED FILES, RE-INGESTS CHANGED ONES)
# -----------------------------------------------------------------------------
async def index_documents_once(pool, folder: Optional[str] = None) -> None:
    # Lazy import: asyncpg is an optional dependency ([learning] extra)
    from ..core.db import (
        delete_chunks_for_document,
        get_document_by_path,
        insert_chunks,
    )

    for path in yield_files(folder):
        stat = os.stat(path)
        filename = os.path.basename(path)
        size_bytes = stat.st_size
        mtime_dt = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        content_hash = file_sha256(path)

        existing = await get_document_by_path(pool, path)

        # SKIP UNCHANGED FILES
        if existing and existing["sha256"] == content_hash:
            continue

        # IF CHANGED, CLEAR OLD CHUNKS FOR A CLEAN REBUILD
        if existing:
            await delete_chunks_for_document(pool, path)

        # PROCESS + INSERT (DEDUPED BY UNIQUE CONSTRAINTS). Metadata is written with the chunks, so a
        # file whose embedding fails is retried next run instead of being marked "done".
        rows = process_file_to_chunks_and_embeddings(path)
        await insert_chunks(pool, path, filename, size_bytes, mtime_dt, content_hash, rows)


# -----------------------------------------------------------------------------
# RAG CONTEXT BUILDER (USES TOP-K SIMILAR CHUNKS)
# -----------------------------------------------------------------------------
async def get_rag_context(query: str, pool, top_k: int = 5) -> str:
    from ..core.db import fetch_similar

    if pool is None:
        print("Database pool is None, cannot fetch RAG context")
        return ""
    try:
        results = await fetch_similar(pool, embed_text(query), limit=top_k)  # [(content, distance)]
        return "\n".join(content for content, _ in results)
    except Exception as e:
        print(f"Error fetching RAG context: {str(e)}")
        return ""


# -----------------------------------------------------------------------------
# LOCAL TEST (OPTIONAL) — chunks locally, embeds with the configured provider:
#   python -m app.utils.utils          (from rag-be/)
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    for p in yield_files():
        rows = process_file_to_chunks_and_embeddings(p)
        print(f"{os.path.basename(p)} -> {len(rows)} chunks")
