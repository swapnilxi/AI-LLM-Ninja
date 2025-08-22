<<<<<<< HEAD
<<<<<<< HEAD
=======
>>>>>>> e311865 (document-load-once)
# utils.py
# =============================================================================
#FILE SCANNER + CHUNKER + EMBEDDER WITH DEDUPE LOGIC
# =============================================================================
<<<<<<< HEAD
import os
import hashlib
from datetime import datetime, timezone
from typing import Iterator, List, Tuple, Optional

import pdfplumber
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

#LOAD ENV
load_dotenv()

# ====== PARAMETERS (OVERRIDABLE VIA .env) ======
MODEL_NAME = os.getenv("EMBED_MODEL", "thenlper/gte-large")  # 1024-dim
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "500"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "50"))
DOCUMENTS_DIR = os.getenv("DOCUMENTS_DIR", "documents")
EMBED_BATCH = int(os.getenv("EMBED_BATCH", "128"))

# ====== LOAD MODEL ONCE ======
model = SentenceTransformer(MODEL_NAME)
MODEL_DIM = getattr(model, "get_sentence_embedding_dimension", lambda: None)() or len(
    model.encode("dim_probe")
)

#HARD CHECK TO AVOID DIMENSION MISMATCH WITH DB
env_embed_dim = int(os.getenv("EMBED_DIM", str(MODEL_DIM)))
if env_embed_dim != MODEL_DIM:
    # YOU CAN SILENCE THIS IF YOU GUARANTEE MATCH IN DB INIT.
    print(
        f"[utils] WARNING: EMBED_DIM ({env_embed_dim}) != model_dim ({MODEL_DIM}). "
        "Ensure db.py uses the same dimension in VECTOR(n)."
    )


# -----------------------------------------------------------------------------
# TEXT NORMALIZATION + HASHES
# -----------------------------------------------------------------------------
def normalize_text(s: str) -> str:
    #STABLE, DETERMINISTIC NORMALIZATION
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
    parts: List[str] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            if page_text:
                parts.append(page_text)
    return "\n".join(parts)


def load_txt_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def yield_files(folder: str = DOCUMENTS_DIR) -> Iterator[str]:
    #YIELD ONLY SUPPORTED FILE TYPES
    if not os.path.isdir(folder):
        return
    for fname in os.listdir(folder):
        path = os.path.join(folder, fname)
        if not os.path.isfile(path):
            continue
        low = fname.lower()
        if low.endswith(".txt") or low.endswith(".pdf"):
            yield path


# -----------------------------------------------------------------------------
# CHUNKING
# -----------------------------------------------------------------------------
def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    text = normalize_text(text)
    chunks: List[str] = []
    i = 0
    n = len(text)
    step = max(1, chunk_size - max(0, overlap))  #SAFETY FOR OVERLAP>=CHUNK
    while i < n:
        end = min(i + chunk_size, n)
        chunks.append(text[i:end])
        i += step
    return chunks


# -----------------------------------------------------------------------------
# EMBEDDING
# -----------------------------------------------------------------------------
def embed_text(s: str) -> List[float]:
    return model.encode(s).tolist()


def embed_texts_batched(texts: List[str], batch_size: int = EMBED_BATCH) -> List[List[float]]:
    out: List[List[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        out.extend(model.encode(batch).tolist())
    return out


# -----------------------------------------------------------------------------
# HIGH-LEVEL: FILE -> CHUNKS + EMBEDDINGS (+ CHUNK HASH)
# -----------------------------------------------------------------------------
def process_file_to_chunks_and_embeddings(
    file_path: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> List[Tuple[int, str, List[float], str]]:
    """
    Returns list of (chunk_index, chunk_text, embedding, chunk_sha256)
    """
    if file_path.lower().endswith(".txt"):
        text = load_txt_file(file_path)
    elif file_path.lower().endswith(".pdf"):
        text = load_pdf_file(file_path)
    else:
        raise ValueError(f"Unsupported file type: {file_path}")

    chunks = chunk_text(text, chunk_size, overlap)
    embeddings = embed_texts_batched(chunks, EMBED_BATCH)

    results: List[Tuple[int, str, List[float], str]] = []
    for idx, (t, emb) in enumerate(zip(chunks, embeddings)):
        chash = sha256_text(t)
        results.append((idx, t, emb, chash))
    return results


# -----------------------------------------------------------------------------
# INDEXING PIPELINE (SKIPS UNCHANGED FILES, RE-INGESTS CHANGED ONES)
# -----------------------------------------------------------------------------
async def index_documents_once(pool, folder: str = DOCUMENTS_DIR) -> None:
    #LAZY IMPORT TO AVOID CIRCULAR DEPENDENCIES
    from db import (
        get_document_by_path,
        upsert_document_metadata,
        delete_chunks_for_document,
        insert_chunks,
    )

    for path in yield_files(folder):
        stat = os.stat(path)
        filename = os.path.basename(path)
        size_bytes = stat.st_size
        mtime_dt = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        content_hash = file_sha256(path)

        existing = await get_document_by_path(pool, path)

        #SKIP UNCHANGED FILES
        if existing and existing["sha256"] == content_hash:
            # print(f"[indexer] SKIP unchanged: {path}")
            continue

        #UPSERT DOC METADATA (NEW OR UPDATED)
        await upsert_document_metadata(
            pool,
            path=path,
            filename=filename,
            size_bytes=size_bytes,
            mtime_dt=mtime_dt,
            sha256=content_hash,
        )

        #IF CHANGED, CLEAR OLD CHUNKS FOR CLEAN REBUILD
        if existing and existing["sha256"] != content_hash:
            await delete_chunks_for_document(pool, path)

        #PROCESS + INSERT (DEDUPED BY UNIQUE CONSTRAINTS)
        rows = process_file_to_chunks_and_embeddings(path, CHUNK_SIZE, CHUNK_OVERLAP)
        _ = await insert_chunks(pool, path, filename, size_bytes, mtime_dt, content_hash, rows)


def load_documents(folder: str = DOCUMENTS_DIR):
    """Return a list of full-text docs from .txt/.pdf in the folder."""
    docs = []
    if not os.path.isdir(folder):
        return docs
    for path in yield_files(folder):
        if path.lower().endswith(".txt"):
            docs.append(load_txt_file(path))
        elif path.lower().endswith(".pdf"):
            docs.append(load_pdf_file(path))
    return docs

# -----------------------------------------------------------------------------
# RAG CONTEXT BUILDER (USES TOP-K SIMILAR CHUNKS)
# -----------------------------------------------------------------------------
async def get_rag_context(query: str, pool, top_k: int = 5, probes: int = 10) -> str:
    # LAZY IMPORT TO AVOID CYCLES
    from db import fetch_similar
    
    if pool is None:
        print("Database pool is None, cannot fetch RAG context")
        return ""
        
    try:
        q_emb = embed_text(query)
        results = await fetch_similar(pool, q_emb, limit=top_k, probes=probes)
        # results: List[(content, distance)]
        return "\n".join(content for content, _ in results)
    except Exception as e:
        print(f"Error fetching RAG context: {str(e)}")
        return ""


# -----------------------------------------------------------------------------
# LOCAL TEST (OPTIONAL)
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    # A LIGHTWEIGHT DRY RUN THAT ONLY CHUNKS LOCALLY
    for p in yield_files(DOCUMENTS_DIR):
        rows = process_file_to_chunks_and_embeddings(p)
        print(f"{os.path.basename(p)} -> {len(rows)} chunks")
=======
=======
>>>>>>> e311865 (document-load-once)
import os
import hashlib
from datetime import datetime, timezone
from typing import Iterator, List, Tuple, Optional

import pdfplumber
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

#LOAD ENV
load_dotenv()

# ====== PARAMETERS (OVERRIDABLE VIA .env) ======
MODEL_NAME = os.getenv("EMBED_MODEL", "thenlper/gte-large")  # 1024-dim
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "500"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "50"))
DOCUMENTS_DIR = os.getenv("DOCUMENTS_DIR", "documents")
EMBED_BATCH = int(os.getenv("EMBED_BATCH", "128"))

# ====== LOAD MODEL ONCE ======
model = SentenceTransformer(MODEL_NAME)
MODEL_DIM = getattr(model, "get_sentence_embedding_dimension", lambda: None)() or len(
    model.encode("dim_probe")
)

#HARD CHECK TO AVOID DIMENSION MISMATCH WITH DB
env_embed_dim = int(os.getenv("EMBED_DIM", str(MODEL_DIM)))
if env_embed_dim != MODEL_DIM:
    # YOU CAN SILENCE THIS IF YOU GUARANTEE MATCH IN DB INIT.
    print(
        f"[utils] WARNING: EMBED_DIM ({env_embed_dim}) != model_dim ({MODEL_DIM}). "
        "Ensure db.py uses the same dimension in VECTOR(n)."
    )


# -----------------------------------------------------------------------------
# TEXT NORMALIZATION + HASHES
# -----------------------------------------------------------------------------
def normalize_text(s: str) -> str:
    #STABLE, DETERMINISTIC NORMALIZATION
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
    parts: List[str] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            if page_text:
                parts.append(page_text)
    return "\n".join(parts)


def load_txt_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def yield_files(folder: str = DOCUMENTS_DIR) -> Iterator[str]:
    #YIELD ONLY SUPPORTED FILE TYPES
    if not os.path.isdir(folder):
        return
    for fname in os.listdir(folder):
        path = os.path.join(folder, fname)
        if not os.path.isfile(path):
            continue
        low = fname.lower()
        if low.endswith(".txt") or low.endswith(".pdf"):
            yield path


# -----------------------------------------------------------------------------
# CHUNKING
# -----------------------------------------------------------------------------
def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    text = normalize_text(text)
    chunks: List[str] = []
    i = 0
    n = len(text)
    step = max(1, chunk_size - max(0, overlap))  #SAFETY FOR OVERLAP>=CHUNK
    while i < n:
        end = min(i + chunk_size, n)
        chunks.append(text[i:end])
        i += step
    return chunks


# -----------------------------------------------------------------------------
# EMBEDDING
# -----------------------------------------------------------------------------
def embed_text(s: str) -> List[float]:
    return model.encode(s).tolist()


def embed_texts_batched(texts: List[str], batch_size: int = EMBED_BATCH) -> List[List[float]]:
    out: List[List[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        out.extend(model.encode(batch).tolist())
    return out


# -----------------------------------------------------------------------------
# HIGH-LEVEL: FILE -> CHUNKS + EMBEDDINGS (+ CHUNK HASH)
# -----------------------------------------------------------------------------
def process_file_to_chunks_and_embeddings(
    file_path: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> List[Tuple[int, str, List[float], str]]:
    """
    Returns list of (chunk_index, chunk_text, embedding, chunk_sha256)
    """
    if file_path.lower().endswith(".txt"):
        text = load_txt_file(file_path)
    elif file_path.lower().endswith(".pdf"):
        text = load_pdf_file(file_path)
    else:
        raise ValueError(f"Unsupported file type: {file_path}")

    chunks = chunk_text(text, chunk_size, overlap)
    embeddings = embed_texts_batched(chunks, EMBED_BATCH)

    results: List[Tuple[int, str, List[float], str]] = []
    for idx, (t, emb) in enumerate(zip(chunks, embeddings)):
        chash = sha256_text(t)
        results.append((idx, t, emb, chash))
    return results


# -----------------------------------------------------------------------------
# INDEXING PIPELINE (SKIPS UNCHANGED FILES, RE-INGESTS CHANGED ONES)
# -----------------------------------------------------------------------------
async def index_documents_once(pool, folder: str = DOCUMENTS_DIR) -> None:
    #LAZY IMPORT TO AVOID CIRCULAR DEPENDENCIES
    from db import (
        get_document_by_path,
        upsert_document,
        delete_chunks_for_document,
        insert_chunks,
    )

    for path in yield_files(folder):
        stat = os.stat(path)
        filename = os.path.basename(path)
        size_bytes = stat.st_size
        mtime_dt = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        content_hash = file_sha256(path)

        existing = await get_document_by_path(pool, path)

        #SKIP UNCHANGED FILES
        if existing and existing["sha256"] == content_hash:
            # print(f"[indexer] SKIP unchanged: {path}")
            continue

        #UPSERT DOC ROW (NEW OR UPDATED)
        doc_id = await upsert_document(
            pool,
            path=path,
            filename=filename,
            size_bytes=size_bytes,
            mtime_dt=mtime_dt,
            sha256=content_hash,
        )

        #IF CHANGED, CLEAR OLD CHUNKS FOR CLEAN REBUILD
        if existing and existing["sha256"] != content_hash:
            await delete_chunks_for_document(pool, doc_id)

        #PROCESS + INSERT (DEDUPED BY UNIQUE CONSTRAINTS)
        rows = process_file_to_chunks_and_embeddings(path, CHUNK_SIZE, CHUNK_OVERLAP)
        _ = await insert_chunks(pool, doc_id, rows)


def load_documents(folder: str = DOCUMENTS_DIR):
    """Return a list of full-text docs from .txt/.pdf in the folder."""
    docs = []
    if not os.path.isdir(folder):
        return docs
    for path in yield_files(folder):
        if path.lower().endswith(".txt"):
            docs.append(load_txt_file(path))
        elif path.lower().endswith(".pdf"):
            docs.append(load_pdf_file(path))
    return docs

# -----------------------------------------------------------------------------
# RAG CONTEXT BUILDER (USES TOP-K SIMILAR CHUNKS)
# -----------------------------------------------------------------------------
async def get_rag_context(query: str, pool, top_k: int = 5, probes: int = 10) -> str:
    # LAZY IMPORT TO AVOID CYCLES
    from db import fetch_similar
    
    if pool is None:
        print("Database pool is None, cannot fetch RAG context")
        return ""
        
    try:
        q_emb = embed_text(query)
        results = await fetch_similar(pool, q_emb, limit=top_k, probes=probes)
        # results: List[(content, distance)]
        return "\n".join(content for content, _ in results)
    except Exception as e:
        print(f"Error fetching RAG context: {str(e)}")
        return ""


# -----------------------------------------------------------------------------
# LOCAL TEST (OPTIONAL)
# -----------------------------------------------------------------------------
if __name__ == "__main__":
<<<<<<< HEAD
<<<<<<< HEAD
    # Example: process all .txt files in DOCUMENTS_DIR
    for fname in os.listdir(DOCUMENTS_DIR):
        if fname.endswith(".txt"):
            path = os.path.join(DOCUMENTS_DIR, fname)
            results = process_file_to_chunks_and_embeddings(path)
            print(f"Processed {fname}, got {len(results)} chunks.")
>>>>>>> db6380b (embedding and chunking)
=======
    docs = load_documents()
    for i, doc in enumerate(docs):
        chunks = chunk_text(doc)
        print(f"Doc {i}: {len(chunks)} chunks")
>>>>>>> 339029c (first-api)
=======
    # A LIGHTWEIGHT DRY RUN THAT ONLY CHUNKS LOCALLY
    for p in yield_files(DOCUMENTS_DIR):
        rows = process_file_to_chunks_and_embeddings(p)
        print(f"{os.path.basename(p)} -> {len(rows)} chunks")
>>>>>>> e311865 (document-load-once)
