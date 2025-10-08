# query_one_question.py
import asyncio, sys
sys.path.append('..')
from RAG_Module.db import init_pool, close_pool, init_db, query_knn
from RAG_Module.embed import embed_text
from RAG_Module.retrieval_gemini import rag_answer
import google.generativeai as genai
import os
from dotenv import load_dotenv
load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

QUESTION = "is there any sofa?"
TOP_K = 5

async def main():
    await init_pool()
    await init_db()

    # Use unified RAG logic from retrieval_gemini
    resp = rag_answer(QUESTION, k=TOP_K)
    print(f"\n🔎 QUERY: {QUESTION}\n")
    print("Raw RAG response:", resp)
    print("Answer:", resp.get("answer", "No answer generated."))
    print("Top results:")
    for i, r in enumerate(resp.get("results", []), 1):
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
    await close_pool()

if __name__ == "__main__":
    asyncio.run(main())
