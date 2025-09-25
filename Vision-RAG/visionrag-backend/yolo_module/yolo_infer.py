"""
Lightweight YOLO inference helpers.
- Loads ultralytics YOLO model once using YOLO_WEIGHTS from env (default: yolov8n.pt)
- Provides detection on image path or bytes
- Returns segments (bytes) and metadata for each detection
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict, Any, Union
from io import BytesIO

from PIL import Image

YOLO_WEIGHTS = os.getenv("YOLO_WEIGHTS", "yolov8n.pt")
YOLO_CONF = float(os.getenv("YOLO_CONF", "0.25"))
YOLO_MAX_REGIONS = int(os.getenv("YOLO_MAX_REGIONS", "12"))

_yolo_model = None
_yolo_names = None


def _load_model():
    global _yolo_model, _yolo_names
    if _yolo_model is None:
        from ultralytics import YOLO  # lazy import
        _yolo_model = YOLO(YOLO_WEIGHTS)
        _yolo_names = _yolo_model.names
    return _yolo_model, _yolo_names


@dataclass
class Det:
    xyxy: Tuple[float, float, float, float]
    cls: int
    conf: float
    name: Optional[str] = None


def _crop_to_bytes(img: Image.Image, xyxy: Tuple[float, float, float, float]) -> bytes:
    x1, y1, x2, y2 = map(int, xyxy)
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = max(x1 + 1, x2), max(y1 + 1, y2)
    crop = img.crop((x1, y1, x2, y2))
    buf = BytesIO()
    crop.save(buf, format="PNG")
    return buf.getvalue()


def detect(source: Union[str, bytes], conf: Optional[float] = None) -> List[Det]:
    """Run YOLO detection on an image path or bytes."""
    model, names = _load_model()
    c = YOLO_CONF if conf is None else float(conf)
    if isinstance(source, bytes):
        img = Image.open(BytesIO(source)).convert("RGB")
        results = model(img, conf=c, verbose=False)
    else:
        results = model(source, conf=c, verbose=False)
    out: List[Det] = []
    for r in results:
        for b in r.boxes:
            xyxy = tuple(float(v) for v in b.xyxy[0].tolist())
            cls = int(b.cls[0])
            confv = float(b.conf[0])
            out.append(Det(xyxy, cls, confv, names.get(cls) if isinstance(names, dict) else None))
    return out


def detect_with_segments(source: Union[str, bytes], conf: Optional[float] = None, max_regions: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Run detection and return a list of dicts with bbox, class, conf, image size, and segment bytes.
    """
    dets = detect(source, conf=conf)
    if isinstance(source, bytes):
        img = Image.open(BytesIO(source)).convert("RGB")
    else:
        img = Image.open(source).convert("RGB")
    W, H = img.size
    cap = YOLO_MAX_REGIONS if (max_regions is None) else int(max_regions)
    out: List[Dict[str, Any]] = []
    for i, d in enumerate(dets[:cap]):
        segment_bytes = _crop_to_bytes(img, d.xyxy)
        out.append({
            "bbox_xyxy": list(d.xyxy),
            "cls": d.cls,
            "cls_name": d.name or str(d.cls),
            "conf": d.conf,
            "image_w": W,
            "image_h": H,
            "segment_bytes": segment_bytes,
        })
    return out
