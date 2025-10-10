# retrieval_yolo.py
"""
YOLO-based segment retrieval for Vision RAG.
Handles querying image segments table and generating answers from segment context.

This module provides:
- query_segments: Retrieve top-k image segments by semantic similarity
- answer_from_segments: Generate grounded answers using segment context
- CLI support for standalone testing
"""

import asyncio
import json
import sys
from typing import List, Dict, Any
from .db import init_pool, close_pool, init_db, query_knn
from .embed import embed_text_one
from .retrieval_gemini import gemini_generate_grounded


async def query_segments(question: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """
    Embed a natural-language question and query top-k image segments.
    
    Args:
        question: Natural language query (e.g., "is there any sofa?")
        top_k: Number of top matches to return
    
    Returns:
        List of dicts with keys:
        {
            "id": row id,
            "caption": segment caption,
            "score": similarity score,
            "bbox": [x1,y1,x2,y2],
            "cls": YOLO class label (if any),
            "conf": YOLO confidence score,
            "crop_path": saved crop path (if any),
            "image_id": parent image ID,
            "image_uri": parent image URI from database
        }
    """
    await init_pool()
    await init_db()

    # Embed the query as a retrieval query vector
    q_vec = embed_text_one(question, task_type="RETRIEVAL_QUERY")

    # Run k-NN search on the image segments table, including image_id
    rows = await query_knn(
        table="vision_rag_image_segments",
        embedding=q_vec,
        k=top_k,
        extra_cols=["bbox", "meta", "image_id"]
    )

    hits: List[Dict[str, Any]] = []
    seen = set()
    
    # Fetch parent image URIs for all unique image_ids
    from .db import get_pool
    pool = get_pool()
    image_uris = {}
    
    # Collect unique image_ids
    image_ids = set()
    for r in rows:
        img_id = r.get("image_id")
        if img_id:
            image_ids.add(img_id)
    
    # Batch fetch URIs from vision_rag_images table
    if image_ids:
        async with pool.acquire() as conn:
            uri_rows = await conn.fetch(
                "SELECT image_id, uri FROM vision_rag_images WHERE image_id = ANY($1)",
                list(image_ids)
            )
            for uri_row in uri_rows:
                image_uris[uri_row["image_id"]] = uri_row["uri"]
    
    for r in rows:
        meta = r.get("meta") or {}
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except Exception:
                meta = {}
        crop_path = meta.get("crop_path")
        cls = meta.get("cls") or meta.get("obj_class")
        img_id = r.get("image_id")
        
        # Use crop_path as unique key if present, else use segment id
        key = crop_path if crop_path else r.get("id")
        if key in seen:
            continue
        seen.add(key)
        
        hits.append({
            "id": r.get("id"),
            "caption": r.get("content"),
            "score": float(r.get("score", 0.0)),
            "bbox": r.get("bbox"),
            "cls": cls,
            "conf": meta.get("conf") or meta.get("obj_conf"),
            "crop_path": crop_path,
            "image_id": img_id,
            "image_uri": image_uris.get(img_id),  # Database URI, not localhost
        })

    await close_pool()
    return hits


def _build_contexts(hits: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """
    Build context list from segment hits for grounded answer generation.
    
    Args:
        hits: List of segment matches from query_segments
    
    Returns:
        List of context dicts with keys: id, text, source
    """
    ctx = []
    for h in hits:
        cap = (h.get("caption") or "").strip()
        if not cap:
            continue
        src = h.get("crop_path") or str(h.get("id"))
        ctx.append({"id": str(h.get("id")), "text": cap[:2000], "source": src})
    return ctx


async def answer_from_segments(question: str, top_k: int = 5) -> Dict[str, Any]:
    """
    Query image segments and generate a grounded answer using Gemini.
    
    This is the high-level function that combines retrieval + generation.
    
    Args:
        question: Natural language query
        top_k: Number of segments to retrieve
    
    Returns:
        {
            "question": str,
            "answer": str (Gemini-generated grounded answer),
            "hits": List[Dict] (top segment matches)
        }
    """
    hits = await query_segments(question, top_k=top_k)
    contexts = _build_contexts(hits)
    answer = gemini_generate_grounded(question, contexts)
    return {"question": question, "answer": answer, "hits": hits}


# ---------- CLI Support ----------
async def _cli_main():
    """
    CLI runner for testing segment retrieval and answer generation.
    
    Usage:
        python -m RAG_Module.retrieval_yolo "is there a sofa?"
        python -m RAG_Module.retrieval_yolo "is there a sofa?" --top-k 10
    """
    question = sys.argv[1] if len(sys.argv) > 1 else "is there any sofa?"
    top_k = int(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[2] == "--top-k" else 5

    print("=" * 60)
    print(f"🔎 QUERY: {question}")
    print(f"📊 TOP_K: {top_k}")
    print("=" * 60)

    resp = await answer_from_segments(question, top_k=top_k)

    print(f"\n🧠 ANSWER: {resp.get('answer')}")
    print(f"\n📋 Based on {len(resp.get('hits', []))} segment(s):")
    for i, h in enumerate(resp.get('hits', []), 1):
        print(f"\n{i}. score={h['score']:.4f} cls={h.get('cls')} conf={h.get('conf')}")
        print(f"   bbox={h.get('bbox')}")
        print(f"   caption={h['caption']}")
        if h.get('crop_path'):
            print(f"   crop={h['crop_path']}")

    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(_cli_main())
 