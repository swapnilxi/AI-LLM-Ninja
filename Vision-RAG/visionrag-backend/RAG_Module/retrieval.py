from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

# Placeholder imports for your embedding/retrieval logic
# You should implement or import the actual logic for SigLIP and Google Vision retrieval
# Example: from .siglip_retriever import retrieve_with_siglip
# Example: from .google_vision_retriever import retrieve_with_google_vision


# --- SigLIP retrieval ---

import asyncio
from .embed import embed_text_one
from .db import query_knn
import os
import requests

def retrieve_with_siglip(question: str):
    """
    Embed the question using SigLIP and perform k-NN search on text_chunks table.
    """
    embedding = embed_text_one(question)
    # Run async query_knn in sync context
    loop = asyncio.get_event_loop()
    results = loop.run_until_complete(query_knn("text_chunks", embedding, k=5))
    return {"method": "siglip", "question": question, "results": results}


# --- Google Vision retrieval (stub: uses same embedding for demo) ---

def retrieve_with_google_vision(question: str):
    """
    Embed the question using Google Gemini API and perform k-NN search on text_chunks table.
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    model = os.getenv("GEMINI_EMBED_MODEL", "text-embedding-004")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:embedText?key={api_key}"
    headers = {"Content-Type": "application/json"}
    data = {"text": question}
    try:
        resp = requests.post(url, headers=headers, json=data, timeout=10)
        resp.raise_for_status()
        embedding = resp.json()["embedding"]["values"]
    except Exception as e:
        return {"error": f"Google Gemini embedding failed: {str(e)}"}
    loop = asyncio.get_event_loop()
    results = loop.run_until_complete(query_knn("text_chunks", embedding, k=5))
    return {"method": "google_vision", "question": question, "results": results}

router = APIRouter()

@router.post("/query-siglp")
async def query_siglp(payload: dict):
    q = payload.get("question") if isinstance(payload, dict) else None
    if not q:
        return JSONResponse({"error": "question required"}, status_code=400)
    try:
        result = retrieve_with_siglip(q)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"SigLIP query error: {str(e)}")

<<<<<<< HEAD
@router.post("/query-gemini")
async def query_gemini(payload: dict):
=======
@router.post("/query-google")
async def query_google(payload: dict):
>>>>>>> 2bd1a99 (vision-rag-chatbot)
    q = payload.get("question") if isinstance(payload, dict) else None
    if not q:
        return JSONResponse({"error": "question required"}, status_code=400)
    try:
<<<<<<< HEAD
        result = retrieve_with_gemini_vision(q)
=======
        result = retrieve_with_google_vision(q)
>>>>>>> 2bd1a99 (vision-rag-chatbot)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Google Vision query error: {str(e)}")
