"""
FastAPI router: End-to-end pipeline for image analysis using YOLO (object detection) and Gemini (captioning/attributes).
- POST /yolo-gemini/analyze: Accepts image upload, runs YOLO detection, then Gemini captioning on full image and each detected region.
- Returns: detections, region segments, region captions, and full-image caption.
"""

from fastapi import APIRouter, UploadFile, File, HTTPException
from typing import List, Dict, Any
from PIL import Image
from io import BytesIO
import base64
import os

from yolo_module.yolo_infer import detect_with_segments
from RAG_Module import embed

router = APIRouter(prefix="/yolo-gemini", tags=["yolo-gemini-pipeline"])

@router.post("/yolo-analyze")
async def analyze_image_yolo_gemini(file: UploadFile = File(...), engine: str = "gemini") -> Dict[str, Any]:
    """
    Upload an image, run YOLO detection, then Gemini captioning on full image and each detected region.
    Returns detections, region segments (base64), region captions, and full-image caption.
    """
    try:
        data = await file.read()
        # 1. YOLO detection (regions)
        regions = detect_with_segments(data, conf=0.25, max_regions=12)
        # 2. Gemini caption on full image
        full_caption = embed.caption_image(data)
        # 3. Gemini caption on each region segment
        region_results = []
        for r in regions:
            segment_bytes = r["segment_bytes"]
            segment_caption = embed.caption_image(segment_bytes)
            region_results.append({
                "bbox_xyxy": r["bbox_xyxy"],
                "obj_class": r["cls_name"],
                "obj_conf": r["conf"],
                "image_w": r["image_w"],
                "image_h": r["image_h"],
                "segment_b64": "data:image/png;base64," + base64.b64encode(segment_bytes).decode(),
                "caption": segment_caption,
            })
        return {
            "full_caption": full_caption,
            "regions": region_results,
            "num_regions": len(region_results),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"YOLO-Gemini pipeline error: {str(e)}")
