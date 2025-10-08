"""
#ingest.py
Unified ingestion pipeline for images into Postgres/pgvector.
- Computes global image embeddings using Gemini (caption -> text-embedding) or SigLIP.
- Optionally segments with Gemini Vision and stores segment caption embeddings.
- Supports YOLO-based object detection and segmentation for more precise image analysis.
- Writes into canonical tables: vision_rag_images, vision_rag_image_segments.
"""

import os
import io
import time
import threading
from typing import List, Dict, Optional, Union, Tuple, Any, Callable, TypeVar

# Add tenacity for retry and rate limiting
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, RetryError, before_sleep_log
import logging
import anyio

# Set up logger for tenacity
logger = logging.getLogger("tenacity")
logging.basicConfig(level=logging.INFO)

from PIL import Image
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query, Body
# embedding engines are provided by embed.py
from . import db
from . import embed
from yolo_module.yolo_infer import detect_with_segments as detect_with_crops, set_yolo_device
# Import set_yolo_device directly from yolo_infer if it exists, otherwise it will need to be added
try:
    from yolo_module.yolo_infer import set_yolo_device
except ImportError:
    # Function doesn't exist yet, we'll provide implementation instructions later
    set_yolo_device = None

# Type variable for generics
T = TypeVar('T')

# ---- Retry configuration ----
# Configure retry parameters for API calls
GEMINI_MAX_RETRIES = int(os.getenv("GEMINI_MAX_RETRIES", "3"))
GEMINI_MIN_WAIT_SECONDS = float(os.getenv("GEMINI_MIN_WAIT", "1.0"))
GEMINI_MAX_WAIT_SECONDS = float(os.getenv("GEMINI_MAX_WAIT", "10.0"))
GEMINI_RETRY_MULTIPLIER = float(os.getenv("GEMINI_RETRY_MULTIPLIER", "2.0"))

# ---- Configuration ----
DATASET_PATH = os.getenv(
    "HOMEOBJECTS_DATASET_PATH",
    "room_dataset/HomeObjects-3k-Dataset/HomeObjects-dataset/images/train",
)

# YOLO configuration
YOLO_DEVICE = os.getenv("YOLO_DEVICE", "")  # Empty string means auto-select (cuda if available, else cpu)

# SigLIP and gemini embeddings are provided by embed.embed_image(..., engine="siglip")


# ---- Utilities ----
# Convert percentage bbox [x1,y1,x2,y2] (0-100) to pixel coords within image size.
def _pct_to_px(bbox_pct: List[float], w: int, h: int) -> List[float]:
    """Convert percentage bbox [x1,y1,x2,y2] (0-100) to pixel coords within image size."""
    x1 = max(0, min(w, int(round(bbox_pct[0] * w / 100.0))))
    y1 = max(0, min(h, int(round(bbox_pct[1] * h / 100.0))))
    x2 = max(0, min(w, int(round(bbox_pct[2] * w / 100.0))))
    y2 = max(0, min(h, int(round(bbox_pct[3] * h / 100.0))))
    if x2 < x1:
        x1, x2 = x2, x1
    if y2 < y1:
        y1, y2 = y2, y1
    return [float(x1), float(y1), float(x2), float(y2)]

async def run_blocking(func: Callable[..., T], *args, **kwargs) -> T:
    """
    Run a blocking function in a thread to avoid blocking the event loop.
    This is crucial for CPU or IO-bound operations like Gemini API calls and YOLO inference.
    
    Args:
        func: The blocking function to run
        *args, **kwargs: Arguments to pass to the function
        
    Returns:
        The result of the function call
    """
    return await anyio.to_thread.run_sync(func, *args, **kwargs)

@retry(
    stop=stop_after_attempt(GEMINI_MAX_RETRIES),
    wait=wait_exponential(
        multiplier=GEMINI_RETRY_MULTIPLIER, 
        min=GEMINI_MIN_WAIT_SECONDS,
        max=GEMINI_MAX_WAIT_SECONDS
    ),
    retry=retry_if_exception_type(Exception),  # Retry on all exceptions (can be more specific)
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
async def run_gemini_with_retry(func: Callable[..., T], *args, **kwargs) -> T:
    """
    Runs a Gemini API call with retry logic to handle transient errors and rate limits.
    
    Args:
        func: The Gemini API function to call
        *args, **kwargs: Arguments to pass to the function
        
    Returns:
        The result of the Gemini API call
    """
    return await run_blocking(func, *args, **kwargs)


# ---- YOLO specific processing ----
async def process_yolo_segments(
    image_bytes: bytes, 
    image_id: str, 
    engine: str,
    conf_threshold: float = 0.25, 
    max_regions: int = 12
) -> int:
    """
    Process an image with YOLO to detect objects, embed each detected region,
    and store in the database as image segments.
    
    Args:
        image_bytes: Raw image data
        image_id: Unique ID for the image
        engine: Embedding engine to use for region crops
        conf_threshold: Confidence threshold for YOLO detections
        max_regions: Maximum number of regions to process
        
    Returns:
        int: Number of segments processed and stored
    """
    seg_count = 0
    # Run YOLO detection in a separate thread to avoid blocking the event loop
    regions = await run_blocking(detect_with_crops, image_bytes, conf=conf_threshold, max_regions=max_regions)
    
    for r in regions:
        # Embed the segment bytes using the specified engine (with retry logic)
        reg_vec = await run_gemini_with_retry(embed.embed_image, r["segment_bytes"], engine=engine)
        
        await db.insert_image_segment(
            image_id=image_id,
            bbox=r["bbox_xyxy"],
            caption=r["cls_name"],
            embedding=reg_vec,
            meta={
                "from": "yolo_detection",
                "obj_class": r["cls_name"],
                "obj_conf": r["conf"],
                "image_w": r["image_w"],
                "image_h": r["image_h"],
                "coord_space": "pixel",  # Explicitly mark as pixel coordinates
            },
        )
        seg_count += 1
    
    return seg_count

async def ingest_yolo_segments(
    image_bytes: bytes,
    image_id: str,
    *,
    uri: Optional[str] = None,
    conf_threshold: float = 0.25,
    max_regions: int = 12,
    embedding_engine: str = "gemini",
    store_full_image: bool = True,
) -> Dict:
    """
    Dedicated function for YOLO-based object detection and segmentation.
    Optionally can store the full image embedding alongside object segments.
    
    Args:
        image_bytes: Raw image data
        image_id: Unique ID for the image
        uri: Optional URI for image source
        conf_threshold: Confidence threshold for YOLO detections
        max_regions: Maximum number of regions to process
        embedding_engine: Engine to use for embeddings
        store_full_image: Whether to also store the full image embedding
        
    Returns:
        Dict with status information
    """
    engine_lc = embedding_engine.lower()
    segments_count = 0
    
    # Store full image if requested
    if store_full_image:
        # Run all embedding operations with retry logic
        img_vec = await run_gemini_with_retry(embed.embed_image, image_bytes, engine=engine_lc)
        caption = await run_gemini_with_retry(embed.caption_image, image_bytes, temperature=0.0)  # Use temperature=0 for determinism
        caption_embedding = await run_gemini_with_retry(embed.embed_text_one, caption, task_type="RETRIEVAL_DOCUMENT")
        
        await db.insert_image(
            image_id=image_id,
            uri=uri,
            embedding=img_vec,
            caption_embedding=caption_embedding,  # Store in dedicated column
            meta={
                "source": "dataset" if uri else "upload",
                "engine": engine_lc,
                "caption": caption,
                "processing": "yolo_pipeline",
            },
        )
    
    # Process YOLO segments
    segments_count = await process_yolo_segments(
        image_bytes, 
        image_id, 
        engine_lc,
        conf_threshold, 
        max_regions
    )
    
    return {
        "image_id": image_id,
        "segments": segments_count,
        "engine": engine_lc,
        "full_image_stored": store_full_image
    }

# ---- Core ingestion ----
async def ingest_image_bytes(
    image_bytes: bytes,
    image_id: str,
    *,
    uri: Optional[str] = None,
    engine: str = "gemini",
    segment: bool = True,
    yolo: bool = True,
) -> Dict:
    """
    Ingest a single image (bytes) with chosen embedding engine and optional segmentation.
    engine: 'gemini' or 'siglip'
    """
    engine_lc = (engine or "gemini").lower()
    
    # Run all embedding operations in threads with retry logic
    img_vec = await run_gemini_with_retry(embed.embed_image, image_bytes, engine=engine_lc)
    caption = await run_gemini_with_retry(embed.caption_image, image_bytes, temperature=0.0)  # Use temperature=0 for deterministic outputs
    caption_embedding = await run_gemini_with_retry(embed.embed_text_one, caption, task_type="RETRIEVAL_DOCUMENT")

    await db.insert_image(
        image_id=image_id,
        uri=uri,
        embedding=img_vec,
        caption_embedding=caption_embedding,  # Store in dedicated column instead of meta
        meta={
            "source": "dataset" if uri else "upload",
            "engine": engine_lc,
            "caption": caption,
        },
    )

    seg_count = 0
    if segment:
        # Run segmentation in a thread with retry logic and use temperature=0 for deterministic outputs
        segs = await run_gemini_with_retry(embed.segment_image, image_bytes, max_items=10, temperature=0.0)
        if segs:
            # Open image in a thread to avoid blocking
            img = await run_blocking(lambda: Image.open(io.BytesIO(image_bytes)).convert("RGB"))
            W, H = img.size
            for s in segs:
                # Convert percentage bbox to pixel coordinates
                bbox_xyxy = _pct_to_px(s["bbox"], W, H)
                seg_cap = s["caption"]
                # Embed caption in a thread with retry logic
                seg_vec = await run_gemini_with_retry(embed.embed_text_one, seg_cap, task_type="RETRIEVAL_DOCUMENT")
                
                await db.insert_image_segment(
                    image_id=image_id,
                    bbox=bbox_xyxy,
                    caption=seg_cap,
                    embedding=seg_vec,
                    caption_embedding=seg_vec,  # Store in dedicated column
                    meta={
                        "from": "gemini_pct_bbox",
                        "caption": seg_cap,
                        "orig_bbox_pct": s["bbox"],  # Store original percentage bbox
                        "coord_space": "pixel",  # Explicitly mark as pixel coordinates (converted from percentages)
                    },
                )
                seg_count += 1

    # YOLO object regions → embed crop bytes and store as segments
    if yolo:
        try:
            yolo_segments = await process_yolo_segments(image_bytes, image_id, engine_lc)
            seg_count += yolo_segments
        except Exception as e:
            logger.warning(f"YOLO processing failed for {image_id}: {str(e)}")
            # Do not fail ingestion if YOLO is unavailable; just log later if needed
            pass

    return {"image_id": image_id, "caption": caption, "segments": seg_count, "engine": engine_lc}


async def ingest_homeobjects_images(
    dataset_path: str = DATASET_PATH,
    *,
    engine: str = "gemini",
    segment: bool = True,
    yolo: bool = True,
) -> Dict:
    """
    Bulk-ingest images from a directory into the canonical tables.
    Skips files whose URI already exists in vision_rag_images.
    """
    pool = db.get_pool()
    ingested: List[str] = []
    skipped: List[str] = []


    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((Exception,)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    async def ingest_with_retry(data, fname, img_path, engine, segment, yolo):
        try:
            await ingest_image_bytes(
                data,
                image_id=fname,
                uri=img_path,
                engine=engine,
                segment=segment,
                yolo=yolo,
            )
        except Exception as e:
            # If 429 or transient error, let tenacity retry
            if hasattr(e, 'status_code') and e.status_code == 429:
                logger.warning(f"429 Too Many Requests for {fname}, retrying...")
                raise
            logger.warning(f"Error ingesting {fname}: {e}, retrying...")
            raise

    async with pool.acquire() as conn:
        for fname in os.listdir(dataset_path):
            if not fname.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                continue
            img_path = os.path.join(dataset_path, fname)
            exists = await conn.fetchval(
                "SELECT 1 FROM vision_rag_images WHERE uri=$1",
                img_path,
            )
            if exists:
                skipped.append(fname)
                continue
            with open(img_path, "rb") as fh:
                data = fh.read()
            try:
                await ingest_with_retry(data, fname, img_path, engine, segment, yolo)
                ingested.append(fname)
            except RetryError as re:
                logger.error(f"Failed to ingest {fname} after retries: {re}")
                skipped.append(fname)

    return {"ingested": ingested, "skipped": skipped}


# ---- Init function for app startup ----
def init_ingest():
    """
    Initialize ingestion components. Call this function during app startup.
    This sets up YOLO device configuration and other necessary initialization.
    """
    # Configure YOLO device based on environment variable
    set_yolo_device(YOLO_DEVICE)
    logger.info(f"YOLO device configured: {YOLO_DEVICE or 'auto'}")
        
def configure_yolo_device(device: str = ""):
    """
    Configure the device for YOLO model inference.
    This function should be called before any other operations with YOLO.
    
    Args:
        device: The device to use for YOLO inference ("cpu", "cuda:0", etc.)
                Empty string means auto-select (cuda if available, else cpu)
    """
    if set_yolo_device:
        set_yolo_device(device)
    else:
        logger.warning("set_yolo_device function not available. Please update yolo_infer.py with the provided implementation.")

# ---- FastAPI router ----
ingest_router = APIRouter(prefix="/ingest", tags=["ingest"])


@ingest_router.post("/image")
async def ingest_image_api(
    file: UploadFile = File(...),
    engine: str = "gemini",
    segment: bool = True,
    yolo: bool = True,
):
    """
    Ingest a single image.
    Query params:
      - engine: 'gemini' or 'siglip' (default: 'gemini')
      - segment: true/false to also store Gemini Vision segments (default: true)
    """
    try:
        data = await file.read()
        result = await ingest_image_bytes(
            data, image_id=file.filename, uri=None, engine=engine, segment=segment, yolo=yolo
        )
        return {"status": "ingested", "caption": result.get("caption"), **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion error: {str(e)}")


@ingest_router.post("/homeobjects")
async def ingest_homeobjects_api(engine: str = "gemini", segment: bool = True, yolo: bool = True):
    """
    Ingest all images from the HomeObjects-3k dataset folder,
    skipping those already present in the vector DB.
    """
    try:
        result = await ingest_homeobjects_images(engine=engine, segment=segment, yolo=yolo)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Bulk ingestion error: {str(e)}")
    return {"status": "completed", **result}

@ingest_router.post("/homeobjects-yolo")
async def ingest_homeobjects_yolo_api(
    conf_threshold: float = Query(0.25, description="Confidence threshold for YOLO detections"),
    max_regions: int = Query(12, description="Maximum number of regions to process"),
    embedding_engine: str = Query("gemini", description="Engine for embedding generation"),
    store_full_image: bool = Query(True, description="Whether to also store the full image embedding"),
):
    """
    Ingest all images from the HomeObjects-3k dataset folder using YOLO for object detection.
    This endpoint focuses on YOLO processing with custom confidence thresholds and region limits.
    
    Query params:
      - conf_threshold: Minimum confidence for YOLO detections (default: 0.25)
      - max_regions: Maximum number of regions to process (default: 12)
      - embedding_engine: 'gemini' or 'siglip' (default: 'gemini')
      - store_full_image: Whether to also store the full image embedding (default: true)
    """
    try:
        # Initialize counters
        ingested = []
        skipped = []
        dataset_path = DATASET_PATH
        pool = db.get_pool()
        
        async with pool.acquire() as conn:
            for fname in os.listdir(dataset_path):
                if not fname.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                    continue
                img_path = os.path.join(dataset_path, fname)
                exists = await conn.fetchval(
                    "SELECT 1 FROM vision_rag_images WHERE uri=$1 AND meta->>'processing'='yolo_pipeline'",
                    img_path,
                )
                if exists:
                    skipped.append(fname)
                    continue
                
                try:
                    with open(img_path, "rb") as fh:
                        data = fh.read()
                    
                    await ingest_yolo_segments(
                        data,
                        image_id=fname,
                        uri=img_path,
                        conf_threshold=conf_threshold,
                        max_regions=max_regions,
                        embedding_engine=embedding_engine,
                        store_full_image=store_full_image
                    )
                    ingested.append(fname)
                except Exception as e:
                    logger.error(f"Failed to process {fname} with YOLO: {str(e)}")
                    skipped.append(fname)
        
        return {
            "status": "completed",
            "ingested": ingested,
            "skipped": skipped,
            "ingested_count": len(ingested),
            "skipped_count": len(skipped)
        }
    except Exception as e:
        logger.error(f"YOLO bulk ingestion error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"YOLO bulk ingestion error: {str(e)}")


# ---- Frontend-expected endpoints ----
@ingest_router.post("/pdf")
async def ingest_pdf_api(file: UploadFile = File(...)):
    """
    Ingest a PDF file (placeholder - not implemented yet).
    """
    raise HTTPException(status_code=501, detail="PDF ingestion not implemented yet")

@ingest_router.post("/segments")
async def ingest_segments_api():
    """
    Ingest segments configuration (placeholder - not implemented yet).
    """
    raise HTTPException(status_code=501, detail="Segments ingestion not implemented yet")

@ingest_router.post("/yolo-analyze")
async def analyze_yolo_detections(
    file: UploadFile = File(...),
    conf_threshold: float = Query(0.25, description="Confidence threshold for YOLO detections", ge=0.0, le=1.0),
    max_regions: int = Query(12, description="Maximum number of regions to process", ge=1, le=50),
):
    """
    Analyze an image with YOLO and return detected objects without ingesting into the database.
    Useful for testing the YOLO detection pipeline or previewing what would be detected.
    
    Query params:
      - conf_threshold: Minimum confidence for YOLO detections (default: 0.25)
      - max_regions: Maximum number of regions to process (default: 12)
    
    Returns detected objects with their bounding boxes, classes, and confidence scores.
    """
    try:
        data = await file.read()
        # Run YOLO detection in a thread to avoid blocking the event loop
        regions = await run_blocking(detect_with_crops, data, conf=conf_threshold, max_regions=max_regions)
        
        # Convert results to a more friendly format for API response
        results = []
        for r in regions:
            result_dict = {
                "class": r["cls_name"],
                "confidence": float(r["conf"]),
                "bbox": r["bbox_xyxy"],
                "coord_space": "pixel",  # Explicitly mark coordinate system
                "image_dimensions": {
                    "width": r["image_w"],
                    "height": r["image_h"]
                }
            }
            # Include segment bytes base64 encoded if needed in frontend
            # from base64 import b64encode
            # result_dict["segment_base64"] = b64encode(r["segment_bytes"]).decode('utf-8')
            
            results.append(result_dict)
        
        return {
            "status": "success",
            "filename": file.filename,
            "detection_count": len(results),
            "detections": results,
            "parameters": {
                "conf_threshold": conf_threshold,
                "max_regions": max_regions
            }
        }
    except Exception as e:
        logger.error(f"YOLO analysis error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"YOLO analysis error: {str(e)}")

# ---- YOLO-specific endpoints ----
@ingest_router.post("/yolo")
async def ingest_image_yolo_api(
    file: UploadFile = File(...),
    conf_threshold: float = Query(0.25, description="Confidence threshold for YOLO detections", ge=0.0, le=1.0),
    max_regions: int = Query(12, description="Maximum number of regions to process", ge=1, le=50),
    embedding_engine: str = Query("gemini", description="Engine for embedding generation ('gemini' or 'siglip')"),
    store_full_image: bool = Query(True, description="Whether to also store the full image embedding"),
):
    """
    Ingest a single image using YOLO for object detection and segmentation.
    
    - Detects objects in the image using YOLO
    - Embeds each detected region and stores as image segments
    - Optionally embeds and stores the full image
    
    Query params:
      - conf_threshold: Minimum confidence for YOLO detections (default: 0.25)
      - max_regions: Maximum number of regions to process (default: 12)
      - embedding_engine: 'gemini' or 'siglip' (default: 'gemini')
      - store_full_image: Whether to also store the full image embedding (default: true)
    """
    try:
        data = await file.read()
        result = await ingest_yolo_segments(
            data, 
            image_id=file.filename, 
            uri=None,
            conf_threshold=conf_threshold,
            max_regions=max_regions,
            embedding_engine=embedding_engine,
            store_full_image=store_full_image
        )
        return {"status": "ingested", "segments_detected": result.get("segments"), **result}
    except Exception as e:
        logger.error(f"YOLO ingestion error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"YOLO ingestion error: {str(e)}")

@ingest_router.post("/yolo/batch")
async def ingest_yolo_batch_api(
    files: List[UploadFile] = File(...),
    conf_threshold: float = Query(0.25, description="Confidence threshold for YOLO detections"),
    max_regions: int = Query(12, description="Maximum number of regions to process"),
    embedding_engine: str = Query("gemini", description="Engine for embedding generation"),
    store_full_image: bool = Query(True, description="Whether to also store the full image embedding"),
):
    """
    Batch ingest multiple images using YOLO for object detection and segmentation.
    
    Process multiple images with YOLO simultaneously:
    - Detects objects in each image
    - Embeds and stores each detected region
    - Optionally embeds and stores the full images
    
    Same parameters as the single image endpoint.
    """
    results = []
    errors = []
    
    for file in files:
        try:
            data = await file.read()
            result = await ingest_yolo_segments(
                data, 
                image_id=file.filename, 
                uri=None,
                conf_threshold=conf_threshold,
                max_regions=max_regions,
                embedding_engine=embedding_engine,
                store_full_image=store_full_image
            )
            results.append({"filename": file.filename, "status": "success", **result})
        except Exception as e:
            logger.error(f"Error processing {file.filename}: {str(e)}")
            errors.append({"filename": file.filename, "error": str(e)})
    
    return {
        "status": "completed", 
        "success_count": len(results), 
        "error_count": len(errors), 
        "results": results,
        "errors": errors
    }

# ---- Backward-compat endpoints ----
@ingest_router.post("/image-gemini")
async def ingest_image_gemini_api(file: UploadFile = File(...)):
    try:
        data = await file.read()
        result = await ingest_image_bytes(data, image_id=file.filename, engine="gemini")
        return {"status": "ingested", "caption": result.get("caption"), **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion error: {str(e)}")

@ingest_router.post("/image-local")
async def ingest_image_local_api(file: UploadFile = File(...)):
    """
    Ingest a single image using SigLIP (local) embeddings.
    """
    try:
        data = await file.read()
        result = await ingest_image_bytes(data, image_id=file.filename, engine="siglip")
        return {"status": "ingested", "caption": result.get("caption"), **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion error: {str(e)}")