
from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import JSONResponse, FileResponse
import os
import json
import asyncio
from typing import Optional
from .retrieval_gemini import gemini_embed_text, _load_image_bytes, gemini_caption_image_json
from .embed import embed_image, embed_text_one_siglip
from .db import query_knn
from urllib.parse import quote

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
    k: int = 5,
    engine: Optional[str] = None
) -> dict:
    embedding = None
    method = ""
    eng = (engine or "gemini").lower()

    if image:
        img_bytes, img_mime = _load_image_bytes(image)
        if not img_bytes:
            return {"error": "Could not load image."}

        if eng == "siglip":
            # Direct image embedding via SigLIP
            try:
                embedding = embed_image(img_bytes, engine="siglip")
                method = "image-siglip"
            except Exception as e:
                return {"error": f"SigLIP image embedding failed: {e}"}
        else:
            # Default: Gemini caption -> embed caption
            det = gemini_caption_image_json(img_bytes, img_mime)
            caption = ", ".join(det.get("objects", []) + det.get("text", [])) or "image"
            try:
                embedding = gemini_embed_text(caption)
                method = "image+caption-gemini"
            except Exception as e:
                # Fallback to SigLIP if Gemini fails
                try:
                    embedding = embed_image(img_bytes, engine="siglip")
                    method = "image-siglip"
                except Exception as e2:
                    return {"error": f"Failed to generate embedding with Gemini and SigLIP: {e}, {e2}"}
    elif query_text:
        # Text queries: choose engine
        if eng == "siglip":
            try:
                embedding = embed_text_one_siglip(query_text)
                method = "text-siglip"
            except Exception as e:
                return {"error": f"SigLIP text embedding failed: {e}"}
        else:
            try:
                embedding = gemini_embed_text(query_text)
                method = "text-gemini"
            except Exception as e:
                # Fallback: try SigLIP if Gemini fails
                try:
                    embedding = embed_text_one_siglip(query_text)
                    method = "text-siglip"
                except Exception as e2:
                    return {"error": f"Failed to generate text embedding: {e}, {e2}"}

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
                    "engine": (json.loads(result.get("meta", "{}")).get("engine") if isinstance(result.get("meta"), str) else result.get("meta", {}).get("engine")) or eng,
                    "image_url": result.get("uri") or result.get("content"),
                }
            }
            for result in results
        ]
    }

def _resolve_image_url(raw_uri: Optional[str], request: Request) -> Optional[str]:
    if not raw_uri:
        return None
    uri = str(raw_uri)
    if uri.startswith("http://") or uri.startswith("https://") or uri.startswith("data:"):
        return uri
    # return absolute URL to file-serving endpoint
    base = str(request.base_url).rstrip('/')
    return f"{base}/image?path={quote(uri)}"


@router.post("/query-image")
async def query_image(
    request: Request,
    question: Optional[str] = Form(None),
    image: Optional[str] = Form(None),
    k: int = Form(5),
    engine: Optional[str] = Form(None)
):
    """
    Unified endpoint: retrieve images by text or image (or both).
    """
    image_path = None
    if image and image.strip():
        image_path = image.strip()

    result = await retrieve_images(query_text=question, image=image_path, k=k, engine=engine)

    # Post-process to ensure image URLs are resolvable from the browser
    for item in result.get("results", []):
        disp = item.get("display_info", {}) or {}
        resolved = _resolve_image_url(disp.get("image_url") or item.get("uri") or item.get("content"), request)
        if resolved:
            disp["image_url"] = resolved
        item["display_info"] = disp

    return result


@router.get("/image")
async def serve_image(path: str):
    """
    Serve a local image file by absolute path. Minimal validation.
    """
    if not path or not os.path.exists(path) or not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(path)
