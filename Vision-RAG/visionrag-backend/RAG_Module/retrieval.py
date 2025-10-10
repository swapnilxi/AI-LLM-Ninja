
from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import JSONResponse, FileResponse
import os
import json
import asyncio
from typing import Optional, List, Dict
from .retrieval_gemini import gemini_embed_text, _load_image_bytes, gemini_caption_image_json
from .retrieval_yolo import query_segments, answer_from_segments
from .embed import embed_image, embed_text_one_siglip
from .db import query_knn
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


@router.post("/query-image")
async def query_image(
    request: Request,
    question: Optional[str] = Form(None),
    image: Optional[str] = Form(None),
    k: int = Form(5),
    engine: Optional[str] = Form(None),
    yolo: Optional[bool] = Form(False),
):
    """
    Unified endpoint: retrieve images by text or image (or both).
    """
    image_path = None
    if image and image.strip():
        image_path = image.strip()

    result = await retrieve_images(query_text=question, image=image_path, k=k, engine=engine, yolo=bool(yolo))

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


@router.post("/query-segments")
async def query_segments_api(
    request: Request,
    question: str = Form(...),
    top_k: int = Form(5),
):
    """
    Query YOLO-detected image segments directly using text.
    
    This endpoint searches only the segments table (vision_rag_image_segments)
    which contains YOLO-detected objects with their bounding boxes and embeddings.
    
    Example queries:
    - "find all sofas"
    - "is there a chair?"
    - "show me all bottles"
    
    Args:
        question: Natural language query
        top_k: Number of top segment matches to return (default: 5)
    
    Returns:
        {
            "question": str,
            "results": List[Dict] with segment info (caption, bbox, score, confidence, image_uri, etc.)
        }
    """
    try:
        hits = await query_segments(question, top_k=top_k)
        
        # Return database URIs directly, no localhost URL resolution
        # Frontend can handle URL resolution if needed
        
        return {
            "question": question,
            "top_k": top_k,
            "count": len(hits),
            "results": hits  # Contains image_uri from database
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Segment query error: {str(e)}")


@router.post("/query-answer")
async def query_answer_api(
    question: str = Form(...),
    top_k: int = Form(5),
):
    """
    Get a Gemini-generated grounded answer based on YOLO segment context.
    
    This endpoint:
    1. Queries YOLO segments for relevant objects
    2. Builds context from segment captions and metadata
    3. Uses Gemini to generate a grounded answer
    
    Example queries:
    - "is there a sofa in the room?"
    - "what furniture is visible?"
    - "describe the objects in the scene"
    
    Args:
        question: Natural language query
        top_k: Number of segments to use as context (default: 5)
    
    Returns:
        {
            "question": str,
            "answer": str (Gemini-generated grounded answer),
            "hits": List[Dict] (segment matches used for context),
            "context_count": int (number of segments used)
        }
    """
    try:
        result = await answer_from_segments(question, top_k=top_k)
        return {
            "question": result["question"],
            "answer": result["answer"],
            "hits": result["hits"],
            "context_count": len(result["hits"]),
            "top_k": top_k
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Answer generation error: {str(e)}")


@router.post("/query-unified")
async def query_unified_api(
    request: Request,
    question: str = Form(...),
    k: int = Form(5),
    search_segments: bool = Form(True),
    engine: Optional[str] = Form("gemini"),
):
    """
    Unified text query that searches BOTH full images AND YOLO segments.
    
    This provides comprehensive results by:
    1. Searching full image embeddings (vision_rag_images table)
    2. Searching YOLO segment embeddings (vision_rag_image_segments table)
    3. Merging and ranking results by similarity score
    
    Use this for queries that might match either:
    - Overall scene descriptions (from Gemini captions)
    - Specific objects (from YOLO detections)
    
    Example queries:
    - "living room with furniture" (matches scene captions)
    - "images with sofas" (matches YOLO segments)
    - "modern office space" (matches both)
    
    Args:
        question: Natural language query
        k: Number of top results to return (default: 5)
        search_segments: Whether to include segment search (default: True)
        engine: Embedding engine to use - 'gemini' or 'siglip' (default: 'gemini')
    
    Returns:
        {
            "question": str,
            "method": str (embedding engine used),
            "results": List[Dict] (merged and ranked results),
            "image_hits": int (number from full images),
            "segment_hits": int (number from segments)
        }
    """
    try:
        eng = (engine or "gemini").lower()
        
        # Generate query embedding
        if eng == "siglip":
            try:
                query_embedding = embed_text_one_siglip(question)
                method = "text-siglip"
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"SigLIP embedding failed: {str(e)}")
        else:
            try:
                query_embedding = gemini_embed_text(question)
                method = "text-gemini"
            except Exception as e:
                # Fallback to SigLIP
                try:
                    query_embedding = embed_text_one_siglip(question)
                    method = "text-siglip-fallback"
                except Exception as e2:
                    raise HTTPException(status_code=500, detail=f"Embedding generation failed: {str(e)}, {str(e2)}")
        
        # Search full images table
        image_results = []
        try:
            image_results = await query_knn(
                table="vision_rag_images",
                embedding=query_embedding,
                k=k,
                extra_cols=["uri", "meta"]
            )
        except Exception as e:
            # Continue even if image search fails
            pass
        
        # Search segments table if requested
        segment_results = []
        if search_segments:
            try:
                segment_results = await query_knn(
                    table="vision_rag_image_segments",
                    embedding=query_embedding,
                    k=k,
                    extra_cols=["bbox", "meta", "image_id"]
                )
            except Exception as e:
                # Continue even if segment search fails
                pass
        
        # Merge results by image_id and rank by score
        merged = {}
        
        # Process image results
        for img in image_results:
            img_id = img.get("id")
            meta = img.get("meta")
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except Exception:
                    meta = {}
            
            merged[img_id] = {
                "id": img_id,
                "type": "full_image",
                "score": float(img.get("score", 0.0)),
                "uri": img.get("uri"),
                "caption": meta.get("caption") if meta else None,
                "meta": meta,
                "content": img.get("content"),
            }
        
        # Process segment results
        for seg in segment_results:
            seg_id = seg.get("id")
            image_id = seg.get("image_id")
            meta = seg.get("meta")
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except Exception:
                    meta = {}
            
            score = float(seg.get("score", 0.0))
            
            # If we already have this image from full search, keep the better score
            if image_id in merged:
                if score > merged[image_id]["score"]:
                    merged[image_id]["score"] = score
                    merged[image_id]["matched_segment"] = {
                        "caption": seg.get("content"),
                        "bbox": seg.get("bbox"),
                        "obj_class": meta.get("obj_class") if meta else None,
                        "confidence": meta.get("obj_conf") if meta else None,
                    }
            else:
                # New image from segment search
                merged[image_id] = {
                    "id": image_id,
                    "type": "segment_match",
                    "score": score,
                    "image_id": image_id,
                    "segment_caption": seg.get("content"),
                    "bbox": seg.get("bbox"),
                    "meta": meta,
                }
        
        # Sort by score and take top k
        ranked_results = sorted(merged.values(), key=lambda x: -x["score"])[:k]
        
        # Post-process URLs
        for result in ranked_results:
            if result.get("uri"):
                resolved = _resolve_image_url(result["uri"], request)
                if resolved:
                    result["image_url"] = resolved
        
        return {
            "question": question,
            "method": method,
            "k": k,
            "search_segments": search_segments,
            "image_hits": len(image_results),
            "segment_hits": len(segment_results),
            "total_results": len(ranked_results),
            "results": ranked_results
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unified query error: {str(e)}")
