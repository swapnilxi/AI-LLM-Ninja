"""
Unified ingestion pipeline for images into Postgres/pgvector.
- Computes global image embeddings using Gemini (caption -> text-embedding) or SigLIP.
- Optionally segments with Gemini Vision and stores segment caption embeddings.
- Writes into canonical tables: vision_rag_images, vision_rag_image_segments.
"""
import os
import io
from typing import List, Dict, Optional

from PIL import Image
from fastapi import APIRouter, HTTPException, UploadFile, File
# embedding engines are provided by embed.py
from . import db
from . import embed

# ---- Configuration ----
DATASET_PATH = os.getenv(
    "HOMEOBJECTS_DATASET_PATH",
    "room_dataset/HomeObjects-3k-Dataset/HomeObjects-dataset/images/train",
)

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


# ---- Core ingestion ----
async def ingest_image_bytes(
    image_bytes: bytes,
    image_id: str,
    *,
    uri: Optional[str] = None,
    engine: str = "gemini",
    segment: bool = True,
) -> Dict:
    """
    Ingest a single image (bytes) with chosen embedding engine and optional segmentation.
    engine: 'gemini' or 'siglip'
    """
    engine_lc = (engine or "gemini").lower()
    img_vec = embed.embed_image(image_bytes, engine=engine_lc)
    caption = embed.caption_image(image_bytes)
    caption_embedding = embed.embed_text_one(caption, task_type="RETRIEVAL_DOCUMENT")

    await db.insert_image(
        image_id=image_id,
        uri=uri,
        embedding=img_vec,
        meta={
            "source": "dataset" if uri else "upload",
            "engine": engine_lc,
            "caption": caption,
            "caption_embedding": caption_embedding,
        },
    )

    seg_count = 0
    if segment:
        segs = embed.segment_image(image_bytes, max_items=10)
        if segs:
            img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            W, H = img.size
            for s in segs:
                bbox_xyxy = _pct_to_px(s["bbox"], W, H)
                seg_cap = s["caption"]
                seg_vec = embed.embed_text_one(seg_cap, task_type="RETRIEVAL_DOCUMENT")
                await db.insert_image_segment(
                    image_id=image_id,
                    bbox=bbox_xyxy,
                    caption=seg_cap,
                    embedding=seg_vec,
                    meta={
                        "from": "gemini_pct_bbox",
                        "caption": seg_cap,
                        "caption_embedding": seg_vec,
                    },
                )
                seg_count += 1

    return {"image_id": image_id, "caption": caption, "segments": seg_count, "engine": engine_lc}


async def ingest_homeobjects_images(
    dataset_path: str = DATASET_PATH,
    *,
    engine: str = "gemini",
    segment: bool = True,
) -> Dict:
    """
    Bulk-ingest images from a directory into the canonical tables.
    Skips files whose URI already exists in vision_rag_images.
    """
    pool = db.get_pool()
    ingested: List[str] = []
    skipped: List[str] = []

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
            await ingest_image_bytes(
                data,
                image_id=fname,
                uri=img_path,
                engine=engine,
                segment=segment,
            )
            ingested.append(fname)

    return {"ingested": ingested, "skipped": skipped}


# ---- FastAPI router ----
ingest_router = APIRouter(prefix="/ingest", tags=["ingest"])


@ingest_router.post("/image")
async def ingest_image_api(
    file: UploadFile = File(...),
    engine: str = "gemini",
    segment: bool = True,
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
            data, image_id=file.filename, uri=None, engine=engine, segment=segment
        )
        return {"status": "ingested", "caption": result.get("caption"), **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion error: {str(e)}")


@ingest_router.post("/homeobjects")
async def ingest_homeobjects_api(engine: str = "gemini", segment: bool = True):
    """
    Ingest all images from the HomeObjects-3k dataset folder,
    skipping those already present in the vector DB.
    """
    try:
        result = await ingest_homeobjects_images(engine=engine, segment=segment)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Bulk ingestion error: {str(e)}")
    return {"status": "completed", **result}


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