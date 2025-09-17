import json
import logging

from fastapi import APIRouter, HTTPException
query_router = APIRouter(tags=["ask"])

@query_router.post("/query", tags=["retrieval"])
async def query(payload: dict):
    q = payload.get("question") if isinstance(payload, dict) else None
    if not q:
        return JSONResponse({"error": "question required"}, status_code=400)
    try:
        result = retrieve_with_siglip(q)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query error: {str(e)}")