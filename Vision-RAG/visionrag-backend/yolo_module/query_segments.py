
# yolo_module/query_segments.py
"""
Query vision_rag_image_segments by embedding a user question and doing k-NN in Postgres (pgvector).
"""

import sys
sys.path.append('..')

from typing import List, Dict, Any

from RAG_Module.db import init_pool, close_pool, init_db, query_knn
from RAG_Module.embed import embed_text_one


async def query_segments(question: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """
    Embed a natural-language question and query top-k image segments.
    
    Returns a list of dicts:
    {
        "id": row id,
        "caption": segment caption,
        "score": similarity score,
        "bbox": [x1,y1,x2,y2],
        "cls": YOLO class label (if any),
        "conf": YOLO confidence score,
        "crop_path": saved crop path (if any)
    }
    """
    await init_pool()
    await init_db()

    # Embed the query as a retrieval query vector
    q_vec = embed_text_one(question, task_type="RETRIEVAL_QUERY")

    # Run k-NN search on the image segments
    rows = await query_knn(
        table="vision_rag_image_segments",
        embedding=q_vec,
        k=top_k,
        extra_cols=["bbox", "meta"]
    )

    hits: List[Dict[str, Any]] = []
    seen = set()
    for r in rows:
        import json
        meta = r.get("meta") or {}
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except Exception:
                meta = {}
        crop_path = meta.get("crop_path")
        cls = meta.get("cls")
        # Use crop_path as unique key if present, else cls
        key = crop_path if crop_path else cls
        if key in seen:
            continue
        seen.add(key)
        hits.append({
            "id": r.get("id"),
            "caption": r.get("content"),
            "score": float(r.get("score", 0.0)),
            "bbox": r.get("bbox"),
            "cls": cls,
            "conf": meta.get("conf"),
            "crop_path": crop_path,
        })

    await close_pool()
    return hits
