
from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import JSONResponse, FileResponse, Response
import os
import json
import asyncio
from typing import Optional, List, Dict, Union
from .retrieval_gemini import gemini_embed_text, _load_image_bytes, gemini_caption_image_json, unified_query
import base64
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
    min_score: float = Form(0.6),
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
        min_score: Minimum relevance score (default: 0.6). set to 0 to disable.
    
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
            include_images=include_images,
            min_score=min_score
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
        
        # Helper: sanitize meta by removing large embedding vectors or fields
        def _sanitize_meta(meta_in: dict) -> dict:
            if not isinstance(meta_in, dict):
                return {}
            meta_out = {}
            for k, v in meta_in.items():
                kl = str(k).lower()
                # drop anything that looks like an embedding/vector
                if 'embed' in kl or 'embedding' in kl or 'vector' in kl:
                    continue
                # drop very large lists (likely numeric vectors)
                if isinstance(v, (list, tuple)) and len(v) > 128:
                    continue
                meta_out[k] = v
            return meta_out

        # Process image results
        images = []
        for img_res in result.get("image_results", []):
            meta = img_res.get("meta") or {}
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except Exception:
                    meta = {}
            # keep caption but remove large embeddings
            safe_meta = _sanitize_meta(meta)

            # Attempt to inline image bytes as base64 when possible (small local files or data URLs)
            raw_uri = img_res.get("uri")
            inline_b64 = None
            inline_mime = None
            try:
                if raw_uri:
                    # First try raw DB uri (may be a local path or data: URL)
                    bts, mime = _load_image_bytes(raw_uri)
                    # If that fails or returns nothing, try the resolved absolute URL (served by /image)
                    if not bts:
                        resolved = resolve_uri(raw_uri)
                        if resolved and resolved != raw_uri:
                            bts, mime = _load_image_bytes(resolved)

                    # Only inline reasonably-sized images to avoid huge payloads
                    if bts and mime and len(bts) <= 1_500_000:  # ~1.5 MB
                        inline_b64 = base64.b64encode(bts).decode("utf-8")
                        inline_mime = mime
            except Exception:
                inline_b64 = None
                inline_mime = None

            images.append({
                "id": img_res.get("id"),
                "image_id": img_res.get("image_id"),
                "uri": resolve_uri(raw_uri),
                "score": float(img_res.get("score", 0)),
                "caption": meta.get("caption"),
                "source": meta.get("source"),
                "meta": safe_meta,
                # Inline base64 (string without data: prefix) and mime type when available
                "image_base64": inline_b64,
                "mime_type": inline_mime,
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
            safe_meta = _sanitize_meta(meta)

            # Try to inline crop bytes for segments (if crop_path is local or a data URL)
            crop_raw = meta.get("crop_path")
            crop_b64 = None
            crop_mime = None
            try:
                if crop_raw:
                    # try raw path first
                    bts, mime = _load_image_bytes(crop_raw)
                    if not bts:
                        resolved_crop = resolve_uri(crop_raw)
                        if resolved_crop and resolved_crop != crop_raw:
                            bts, mime = _load_image_bytes(resolved_crop)
                    if bts and mime and len(bts) <= 1_500_000:
                        crop_b64 = base64.b64encode(bts).decode("utf-8")
                        crop_mime = mime
            except Exception:
                crop_b64 = None
                crop_mime = None

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
                "meta": safe_meta,
                # Inline crop base64 (no data: prefix) and mime type when available
                "image_base64": crop_b64,
                "mime_type": crop_mime,
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


# ========== IMAGE SERVING ENDPOINT ==========

@router.get("/image")
async def serve_image(path: str):
    """
    Serve image files from local filesystem or database.
    
    Args:
        path: Relative/absolute path to the image file, or image_id to query from DB
    
    Returns:
        FileResponse with the image or Response with image bytes from DB
    """
    try:
        # Handle both relative and absolute paths
        if not os.path.isabs(path):
            # Try multiple base directories
            base_dirs = [
                os.getcwd(),  # Current working directory
                os.path.dirname(os.path.dirname(__file__)),  # Project root
                "/",  # Absolute root
            ]
            
            for base_dir in base_dirs:
                full_path = os.path.join(base_dir, path)
                if os.path.exists(full_path) and os.path.isfile(full_path):
                    path = full_path
                    break
        
        # If file exists on filesystem, serve it
        if os.path.exists(path) and os.path.isfile(path):
            # Determine media type from extension
            ext = os.path.splitext(path)[1].lower()
            media_types = {
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.png': 'image/png',
                '.gif': 'image/gif',
                '.webp': 'image/webp',
                '.bmp': 'image/bmp',
                '.svg': 'image/svg+xml',
            }
            media_type = media_types.get(ext, 'application/octet-stream')
            return FileResponse(path, media_type=media_type)
        
        # If not found on filesystem, try to fetch from database by image_id
        from .db import get_pool
        pool = get_pool()
        async with pool.acquire() as conn:
            # Try exact match on image_id
            row = await conn.fetchrow(
                "SELECT image_data, mime_type FROM vision_rag_images WHERE image_id = $1 AND image_data IS NOT NULL LIMIT 1",
                path
            )
            
            # If not found by image_id, try uri column (might be basename match)
            if not row:
                row = await conn.fetchrow(
                    "SELECT image_data, mime_type FROM vision_rag_images WHERE uri LIKE $1 AND image_data IS NOT NULL LIMIT 1",
                    f"%{path}"
                )
            
            if row and row['image_data']:
                mime_type = row['mime_type'] or 'image/jpeg'
                return Response(content=bytes(row['image_data']), media_type=mime_type)
        
        # Not found anywhere
        raise HTTPException(status_code=404, detail=f"Image not found on filesystem or database: {path}")
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error serving image: {str(e)}")
