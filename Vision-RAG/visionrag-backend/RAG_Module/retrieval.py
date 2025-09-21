
from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import JSONResponse
import os
import json
import asyncio
from typing import Optional
from .retrieval_gemini import gemini_embed_text, _load_image_bytes, gemini_caption_image_json
from .db import query_knn

router = APIRouter()

def retrieve_images(
    query_text: Optional[str] = None,
    image: Optional[str] = None,
    k: int = 5
) -> dict:
    """
    Retrieve relevant images from the DB using either a text prompt or an image.
    Returns a list of images and their associated text/meta.
    """
    if not query_text and not image:
        return {"error": "Provide either a text prompt or an image."}

async def retrieve_images(
    query_text: Optional[str] = None,
    image: Optional[str] = None,
    k: int = 5
) -> dict:
    if image:
        img_bytes, img_mime = _load_image_bytes(image)
        if img_bytes:
            det = gemini_caption_image_json(img_bytes, img_mime)
            caption = ", ".join(det.get("objects", []) + det.get("text", []))
            if not caption:
                caption = "image"
            try:
                embedding = gemini_embed_text(caption)
                method = "image+caption-gemini"
            except Exception as e:
                # Fallback to SigLIP if Gemini fails
                try:
                    from .retrieval_siglip import embed_text_one
                    embedding = embed_text_one(caption)
                    method = "image+caption-siglip"
                except Exception as e2:
                    return {"error": f"Failed to generate embedding with Gemini and SigLIP: {e}, {e2}"}
        else:
            return {"error": "Could not load image."}
    elif query_text:
        try:
            embedding = gemini_embed_text(query_text)
            method = "text-gemini"
        except Exception as e:
            # Fallback to SigLIP if Gemini fails
            try:
                from .retrieval_siglip import embed_text_one
                embedding = embed_text_one(query_text)
                method = "text-siglip"
            except Exception as e2:
                return {"error": f"Failed to generate embedding with Gemini and SigLIP: {e}, {e2}"}

    if embedding is None:
        return {"error": "Failed to generate embedding."}

    try:
        # Use the correct table name from your database schema
        results = await query_knn("vision_rag_images", embedding, k=k, extra_cols=["uri", "meta"])
    except Exception as e:
        return {"error": f"DB retrieval failed: {e}"}

    return {
        "method": method,
        "query_text": query_text,
        "image": image,
        "k": k,
        "results": [
            {
                **result,
                # Parse meta if it's a string, add display info for frontend
                "meta_parsed": json.loads(result.get("meta", "{}")) if isinstance(result.get("meta"), str) else result.get("meta", {}),
                "display_info": {
                    "caption": json.loads(result.get("meta", "{}")).get("caption") if isinstance(result.get("meta"), str) else result.get("meta", {}).get("caption"),
                    "source": json.loads(result.get("meta", "{}")).get("source") if isinstance(result.get("meta"), str) else result.get("meta", {}).get("source"),
                    "engine": json.loads(result.get("meta", "{}")).get("engine") if isinstance(result.get("meta"), str) else result.get("meta", {}).get("engine"),
                    "image_url": result.get("uri") or result.get("content")  # fallback to content if uri is null
                }
            }
            for result in results
        ]
    }

@router.post("/query-image")
async def query_image(
    question: Optional[str] = Form(None),
    image: Optional[str] = Form(None),
    k: int = Form(5)
):
    """
    Unified endpoint: retrieve images by text or image (or both).
    """
    image_path = None
    # Only process if image is provided and not empty
    if image and image.strip():
        image_path = image.strip()

    result = await retrieve_images(query_text=question, image=image_path, k=k)

    return result
