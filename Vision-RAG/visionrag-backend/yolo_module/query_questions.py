# query_questions.py
"""
Unified query module for Vision RAG image segments.
Combines retrieval, answer generation, and CLI testing capabilities.

Usage:
    python query_questions.py "is there any sofa?"
    python query_questions.py "Is there a sofa with teal pillows?" --top-k 10
"""

import asyncio
import sys
import os
import json
from typing import List, Dict, Any
from dotenv import load_dotenv

# Add visionrag-backend to sys.path for robust imports
sys.path.append('..')
from RAG_Module.db import init_pool, close_pool, init_db, query_knn
from RAG_Module.embed import embed_text_one
from RAG_Module.retrieval_gemini import rag_answer, gemini_generate_grounded

load_dotenv()

# >>> CLI OVERRIDE — python query_questions.py "is there any sofa?" --top-k 5
QUESTION = sys.argv[1] if len(sys.argv) > 1 else "is there any sofa?"
TOP_K = int(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[2] == "--top-k" else 5


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


def _build_contexts(hits: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """
    Build context list from segment hits for grounded answer generation.
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


async def main():
    """
    Main CLI runner supporting both retrieval methods:
    1. Original rag_answer (legacy)
    2. New answer_from_segments (preferred)
    """
    await init_pool()
    try:
        await init_db()
        
        print("=" * 60)
        print(f"🔎 QUERY: {QUESTION}")
        print(f"📊 TOP_K: {TOP_K}")
        print("=" * 60)
        
        # Method 1: Using answer_from_segments (preferred - more detailed)
        print("\n📌 Method 1: Query Segments (retrieval + generation)")
        print("-" * 60)
        resp = await answer_from_segments(QUESTION, top_k=TOP_K)
        
        print(f"\n🧠 ANSWER: {resp.get('answer')}")
        print(f"\n📋 Based on {len(resp.get('hits', []))} segment(s):")
        for i, h in enumerate(resp.get('hits', []), 1):
            print(f"\n{i}. score={h['score']:.4f} cls={h.get('cls')} conf={h.get('conf')}")
            print(f"   bbox={h.get('bbox')}")
            print(f"   caption={h['caption']}")
            if h.get('crop_path'):
                print(f"   crop={h['crop_path']}")
        
        # Method 2: Using rag_answer (legacy - for comparison)
        print("\n" + "=" * 60)
        print("📌 Method 2: RAG Answer (legacy method)")
        print("-" * 60)
        resp_legacy = rag_answer(QUESTION, k=TOP_K)
        
        if resp_legacy.get("error"):
            print("Raw RAG response:", resp_legacy)
            print("Answer:", "No answer generated.")
        else:
            print("Answer:", resp_legacy.get("answer", "No answer generated."))
            print("\nTop results:")
            for i, r in enumerate(resp_legacy.get("results", []), 1):
                cap = r.get("content")
                score = float(r.get("score", 0))
                bbox = r.get("bbox")
                meta = r.get("meta") or {}
                print(f"{i}. score={score:.4f}  cls={meta.get('cls')}  conf={meta.get('conf')}")
                print(f"   bbox={bbox}")
                print(f"   caption={cap}")
                if meta.get("crop_path"):
                    print(f"   crop={meta['crop_path']}")
                print()
        
        print("=" * 60)
    finally:
        await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
