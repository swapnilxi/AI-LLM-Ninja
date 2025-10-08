# app/yolo_gemini.py
"""
Unified YOLO + Gemini Vision RAG service.

Endpoints:
- POST /ingest-yolo  { "source": "<url|path>" }  -> runs YOLO, crops, captions, embeds, inserts
- POST /query-yolo   { "question": "...", "top_k": 5 } -> returns {question, answer, hits[]}
- POST /query-segments { "question": "...", "top_k": 5 } -> returns {question, hits[]} (retrieval only)

Relies on RAG_Module package for DB + embeddings + Gemini generation.
"""

import os
import io
import uuid
import json
import base64
import asyncio
from typing import List, Dict, Any, Optional, Tuple

from fastapi import FastAPI
from pydantic import BaseModel, Field
from urllib.parse import urlparse
import urllib.request

# ---- import your existing helpers (no duplication) ----
from RAG_Module.db import (
    init_pool, close_pool, init_db
)
from RAG_Module.ingest import ingest_yolo_segments

# Import query functions from unified query module
from yolo_module.query_questions import query_segments, answer_from_segments


# ========================
# Config
# ========================
SAVE_DIR = os.getenv("YOLO_SAVE_DIR", "runs/segment/service")

# Validate required environment variables
if not os.getenv("GEMINI_API_KEY"):
    raise ValueError("GEMINI_API_KEY environment variable is required")
if not os.getenv("DB_URL"):
    raise ValueError("DB_URL environment variable is required")

os.makedirs(SAVE_DIR, exist_ok=True)


# ========================
# Small utils
# ========================
def _download_to_local(url: str, dest_dir: str) -> str:
    """Download a file from a URL to a local directory."""
    p = urlparse(url)
    fname = os.path.basename(p.path) or "download.jpg"
    if not fname.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
        fname += ".jpg"
    dest = os.path.join(dest_dir, fname)
    urllib.request.urlretrieve(url, dest)
    return dest


# ========================
# Ingestion (YOLO → crops → caption → embed → DB)
# ========================
async def ingest_one_image(
    source: str,
    conf_threshold: float = 0.25,
    max_regions: int = 12,
    embedding_engine: str = "gemini",
    store_full_image: bool = True
) -> Dict[str, Any]:
    """
    Ingest one image using the existing YOLO pipeline from ingest.py.
    
    Args:
        source: Image URL or local file path
        conf_threshold: Confidence threshold for YOLO detections
        max_regions: Maximum number of regions to process
        embedding_engine: Engine to use for embeddings ('gemini' or 'siglip')
        store_full_image: Whether to also store the full image embedding
    
    Returns: 
        { "image_id": str, "segments": int, "image_path": str, "engine": str }
    """
    # Resolve local file
    storage_url = source if source.startswith(("http://", "https://")) else None
    if storage_url:
        local_path = _download_to_local(source, SAVE_DIR)
    else:
        local_path = source

    # Read image bytes
    with open(local_path, 'rb') as f:
        image_bytes = f.read()

    # DB bootstrap
    await init_pool()
    await init_db()

    # Generate unique image ID
    image_id = str(uuid.uuid4())
    
    # Use the existing ingest_yolo_segments function from ingest.py
    result = await ingest_yolo_segments(
        image_bytes=image_bytes,
        image_id=image_id,
        uri=(storage_url or f"file://{os.path.abspath(local_path)}"),
        conf_threshold=conf_threshold,
        max_regions=max_regions,
        embedding_engine=embedding_engine,
        store_full_image=store_full_image
    )

    await close_pool()
    
    return {
        "image_id": result["image_id"],
        "count": result["segments"],  # Keep 'count' for backward compatibility
        "segments": result["segments"],
        "image_path": os.path.abspath(local_path),
        "engine": result["engine"]
    }


# ========================
# FastAPI
# ========================
app = FastAPI(title="VisionRAG – YOLO x Gemini Service")

class IngestBody(BaseModel):
    source: str = Field(..., description="Image URL or local file path")
    conf_threshold: float = Field(0.25, description="Confidence threshold for YOLO detections", ge=0.0, le=1.0)
    max_regions: int = Field(12, description="Maximum number of regions to process", ge=1)
    embedding_engine: str = Field("gemini", description="Engine for embedding generation ('gemini' or 'siglip')")
    store_full_image: bool = Field(True, description="Whether to also store the full image embedding")

class QueryBody(BaseModel):
    question: str
    top_k: int = 5

class SegmentQueryBody(BaseModel):
    question: str
    top_k: int = 5

@app.on_event("startup")
async def _startup():
    # Lazily ensure pool/tables once; functions still ensure idempotency.
    await init_pool()
    await init_db()
    await close_pool()

@app.post("/ingest-yolo")
async def ingest_yolo(body: IngestBody):
    """
    Ingest one image: run YOLO, crop detections, caption, embed, insert into DB.
    Uses the centralized ingestion logic from ingest.py to avoid code duplication.
    """
    info = await ingest_one_image(
        source=body.source,
        conf_threshold=body.conf_threshold,
        max_regions=body.max_regions,
        embedding_engine=body.embedding_engine,
        store_full_image=body.store_full_image
    )
    return {"ok": True, **info}

@app.post("/query-yolo")
async def query_yolo(body: QueryBody):
    """
    Query by natural language. Returns Gemini-grounded answer + top segment hits.
    """
    result = await answer_from_segments(body.question, top_k=body.top_k)
    return result


# --- New endpoint: segment-level query ---
@app.post("/query-segments")
async def query_segments_endpoint(body: SegmentQueryBody):
    """
    Query image segments by natural language. Returns top segment hits only.
    """
    hits = await query_segments(body.question, top_k=body.top_k)
    return {"question": body.question, "hits": hits}


# ---- Local runner (optional) ----
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("yolo_module.yolo_gemini:app", host="0.0.0.0", port=8000, reload=True)
