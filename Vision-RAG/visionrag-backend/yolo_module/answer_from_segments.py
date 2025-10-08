# yolo_module/answer_from_segments.py
from typing import Dict, Any, List
import asyncio

# absolute import is simpler and avoids Pylance issues
from query_segments import query_segments
from RAG_Module.retrieval_gemini import gemini_generate_grounded

def _build_contexts(hits: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    ctx = []
    for h in hits:
        cap = (h.get("caption") or "").strip()
        if not cap:
            continue
        src = h.get("crop_path") or str(h.get("id"))
        ctx.append({"id": str(h.get("id")), "text": cap[:2000], "source": src})
    return ctx

async def answer_from_segments(question: str, top_k: int = 5) -> Dict[str, Any]:
    hits = await query_segments(question, top_k=top_k)
    contexts = _build_contexts(hits)
    answer = gemini_generate_grounded(question, contexts)
    return {"question": question, "answer": answer, "hits": hits}

# ---- SMOKE RUNNER (so `python -m yolo_module.answer_from_segments` prints something) ----
async def _smoke():
    q = "Is there a sofa with teal pillows?"
    print("🔎 QUESTION:", q)
    resp = await answer_from_segments(q, top_k=5)
    print("\n🧠 ANSWER:", resp.get("answer"))
    print("\n📌 TOP HITS:")
    for i, h in enumerate(resp.get("hits", []), 1):
        print(f"{i}. score={h['score']:.4f} cls={h.get('cls')} conf={h.get('conf')}")
        print(f"   caption={h['caption']}")
        if h.get('crop_path'):
            print(f"   crop={h['crop_path']}")
        print()

if __name__ == "__main__":
    asyncio.run(_smoke())
