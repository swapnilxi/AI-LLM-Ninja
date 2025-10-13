
from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import JSONResponse, FileResponse
import os
import json
import asyncio
from typing import Optional, List, Dict, Union
from .retrieval_gemini import gemini_embed_text, _load_image_bytes, gemini_caption_image_json, unified_query
from .retrieval_yolo import query_segments, answer_from_segments
from .embed import embed_image, embed_text_one_siglip
from .db import query_knn, init_pool, init_db
from yolo_module.yolo_infer import detect_with_crops
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
    engine: Optional[str] = None,
    yolo: bool = False,
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

    # Region-based search using YOLO (optional)
    results_regions: List[Dict] = []
    if image and yolo:
        try:
            regions = detect_with_crops(img_bytes, conf=0.25, max_regions=8)
            for r in regions:
                vec = embed_image(r["crop_bytes"], engine=eng)
                # search in segments table; include image_id and meta for UI
                seg_hits = await query_knn("vision_rag_image_segments", vec, k=k, extra_cols=["image_id", "meta"])
                # annotate hits with matched query region
                for h in seg_hits:
                    md = h.get("meta")
                    if isinstance(md, str):
                        try:
                            md = json.loads(md)
                        except Exception:
                            md = {}
                    md = md or {}
                    md["matched_query_bbox"] = r["bbox_xyxy"]
                    md["matched_query_obj_class"] = r["cls_name"]
                    h["meta"] = md
                results_regions.extend(seg_hits)
        except Exception:
            # ignore YOLO failure to keep base flow working
            pass

    if embedding is None and not results_regions:
        return {"error": "Failed to generate embedding."}

    # Base image/text retrieval against images table
    results = []
    if embedding is not None:
        try:
            results = await query_knn("vision_rag_images", embedding, k=k, extra_cols=["uri", "meta"])
        except Exception as e:
            return {"error": f"DB retrieval failed: {e}"}

    # Merge region results and base results
    def _merge_sets(a: List[Dict], b: List[Dict], top_k: int) -> List[Dict]:
        by_key = {}
        def _key(x):
            md = x.get("meta")
            if isinstance(md, str):
                try:
                    md = json.loads(md)
                except Exception:
                    md = {}
            img_id = x.get("image_id") or (md or {}).get("image_id") or (md or {}).get("id") or x.get("id")
            return img_id
        for x in a + b:
            k_ = _key(x)
            if k_ not in by_key or float(x.get("score", 0)) > float(by_key[k_].get("score", 0)):
                by_key[k_] = x
        merged = sorted(by_key.values(), key=lambda r: -float(r.get("score", 0)))
        return merged[:top_k]

    merged_results = _merge_sets(results, results_regions, k)

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
            for result in merged_results
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







# ========== NEW UNIFIED ENDPOINTS ==========

@router.post("/query")
async def unified_query_endpoint(
    request: Request,
    question: Optional[str] = Form(None),
    image: Optional[Union[UploadFile, str]] = Form(None),
    image_url: Optional[str] = Form(None),
    k: int = Form(5),
    include_segments: bool = Form(True),
    include_text_chunks: bool = Form(True),
    include_images: bool = Form(True),
):
    """
    🎯 UNIFIED QUERY ENDPOINT - Your one-stop query interface!
    
    This endpoint handles ALL query types and returns:
    - A grounded text answer from the LLM
    - Relevant images from the database
    - Relevant image segments (YOLO detections)
    - Text chunks for context
    
    Works with:
    - Text-only queries: "What furniture is in the living room?"
    - Image-only queries: Upload an image (will auto-generate question from image)
    - Combined: Upload image + "Is there a sofa like this in our inventory?"
    
    Args:
        question: Natural language query (optional if image provided)
        image: Optional uploaded image file or image string (base64 data URL, URL, etc.)
        image_url: Optional image URL (if no file uploaded)
        k: Number of results per category (default: 5)
        include_segments: Search YOLO segments (default: True)
        include_text_chunks: Search text chunks (default: True)
        include_images: Search full images (default: True)
    
    Returns:
        {
            "question": str,
            "answer": str (grounded LLM answer),
            "caption": dict (if image was analyzed),
            "images": List[Dict] (relevant full images with URIs),
            "segments": List[Dict] (relevant segments with bboxes, crops),
            "text_chunks": List[Dict] (relevant text chunks),
            "stats": dict (counts for each category)
        }
    """
    try:
        # Initialize DB
        await init_pool()
        await init_db()
        
        # Validate: must provide either question or image
        if not question and not image and not image_url:
            raise HTTPException(
                status_code=400, 
                detail="Must provide either 'question' (text query) or 'image'/'image_url' (image query) or both"
            )
        
        # Handle image input
        image_input = None
        if image:
            if isinstance(image, UploadFile):
                # Read uploaded file
                contents = await image.read()
                # Convert to base64 data URL
                import base64
                b64 = base64.b64encode(contents).decode('utf-8')
                mime = image.content_type or "image/jpeg"
                image_input = f"data:{mime};base64,{b64}"
            else:
                # image is a string (base64 data URL, URL, or other string)
                image_input = image
        elif image_url:
            image_input = image_url
        
        # Generate a default question if only image is provided
        query_question = question
        if not query_question and image_input:
            # Auto-generate question from image caption
            query_question = "Describe what you see in this image and find similar content"
        
        # Call unified query function
        result = await unified_query(
            question=query_question,
            image=image_input,
            k=k,
            include_segments=include_segments,
            include_text_chunks=include_text_chunks,
            include_images=include_images
        )
        
        # Check for errors
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])
        
        # Post-process image URIs for frontend
        def resolve_uri(uri: Optional[str]) -> Optional[str]:
            if not uri:
                return None
            if uri.startswith("http://") or uri.startswith("https://") or uri.startswith("data:"):
                return uri
            # Convert local path to API endpoint
            base = str(request.base_url).rstrip('/')
            return f"{base}/image?path={quote(uri)}"
        
        # Process image results
        images = []
        for img_res in result.get("image_results", []):
            meta = img_res.get("meta") or {}
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except Exception:
                    meta = {}
            
            images.append({
                "id": img_res.get("id"),
                "image_id": img_res.get("image_id"),
                "uri": resolve_uri(img_res.get("uri")),
                "score": float(img_res.get("score", 0)),
                "caption": meta.get("caption"),
                "source": meta.get("source"),
                "meta": meta
            })
        
        # Process segment results
        segments = []
        for seg_res in result.get("segment_results", []):
            meta = seg_res.get("meta") or {}
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except Exception:
                    meta = {}
            
            segments.append({
                "id": seg_res.get("id"),
                "image_id": seg_res.get("image_id"),
                "caption": seg_res.get("content"),
                "score": float(seg_res.get("score", 0)),
                "bbox": seg_res.get("bbox"),
                "cls": meta.get("cls") or meta.get("obj_class"),
                "conf": meta.get("conf") or meta.get("obj_conf"),
                "crop_path": resolve_uri(meta.get("crop_path")),
                "image_uri": resolve_uri(meta.get("image_uri")),
                "meta": meta
            })
        
        # Process text chunks
        text_chunks = []
        for txt_res in result.get("text_results", []):
            meta = txt_res.get("meta") or {}
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except Exception:
                    meta = {}
            
            text_chunks.append({
                "id": txt_res.get("id"),
                "doc_id": txt_res.get("doc_id"),
                "text": txt_res.get("content"),
                "score": float(txt_res.get("score", 0)),
                "source": meta.get("source"),
                "meta": meta
            })
        
        return {
            "question": query_question,  # Return the actual question used (may be auto-generated)
            "original_question": question,  # Return original question (may be None)
            "answer": result.get("answer"),
            "method": result.get("method"),
            "caption": result.get("caption"),
            "caption_used": result.get("caption_used", False),
            "images": images,
            "segments": segments,
            "text_chunks": text_chunks,
            "stats": result.get("stats", {}),
            "all_contexts": result.get("all_contexts", [])  # For debugging
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unified query failed: {str(e)}")


@router.post("/query-segments-with-answer")
async def query_segments_with_answer_endpoint(
    request: Request,
    question: str = Form(...),
    top_k: int = Form(5),
):
    """
    🔍 SEGMENT-FOCUSED QUERY WITH GROUNDED ANSWER
    
    This endpoint:
    1. Searches ONLY image segments (YOLO detections)
    2. Generates a grounded answer using segment context
    3. Returns both the answer AND the segments with images
    
    Best for object-specific queries like:
    - "Is there a sofa?"
    - "Find all chairs"
    - "Show me bottles"
    
    Args:
        question: Natural language query
        top_k: Number of segments to retrieve (default: 5)
    
    Returns:
        {
            "question": str,
            "answer": str (grounded LLM answer),
            "segments": List[Dict] (matched segments with images, bboxes, scores)
        }
    """
    try:
        # Initialize DB
        await init_pool()
        await init_db()
        
        # Get answer + segments
        result = await answer_from_segments(question, top_k=top_k)
        
        # Resolve URIs
        def resolve_uri(uri: Optional[str]) -> Optional[str]:
            if not uri:
                return None
            if uri.startswith("http://") or uri.startswith("https://") or uri.startswith("data:"):
                return uri
            base = str(request.base_url).rstrip('/')
            return f"{base}/image?path={quote(uri)}"
        
        # Format segments for frontend
        segments = []
        for hit in result.get("hits", []):
            segments.append({
                "id": hit.get("id"),
                "image_id": hit.get("image_id"),
                "caption": hit.get("caption"),
                "score": hit.get("score"),
                "bbox": hit.get("bbox"),
                "cls": hit.get("cls"),
                "conf": hit.get("conf"),
                "crop_path": resolve_uri(hit.get("crop_path")),
                "image_uri": resolve_uri(hit.get("image_uri")),
            })
        
        return {
            "question": result["question"],
            "answer": result["answer"],
            "segments": segments,
            "count": len(segments),
            "top_k": top_k
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Segment query failed: {str(e)}")

