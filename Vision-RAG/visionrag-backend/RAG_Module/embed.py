# app/embed.py
import os
import io
import re
import json
from typing import List, Dict, Tuple, Optional

import numpy as np
from PIL import Image
import google.generativeai as genai

# ---- Config ----
GEMINI_VISION_MODEL = os.getenv("GEMINI_VISION_MODEL", "gemini-1.5-flash")
GEMINI_EMBEDDING_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "text-embedding-004")
EMBED_DIM = int(os.getenv("EMBED_DIM", "768"))

# Init Gemini
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# ---- Internal helpers ----
def _l2_normalize(vec: List[float]) -> List[float]:
    arr = np.asarray(vec, dtype=np.float32)
    n = float(np.linalg.norm(arr))
    if n == 0:
        return arr.tolist()
    return (arr / n).tolist()

def _fit_dim(vec: List[float], dim: int = EMBED_DIM) -> List[float]:
    # pad or truncate to exactly EMBED_DIM
    if len(vec) < dim:
        return (vec + [0.0] * (dim - len(vec)))[:dim]
    return vec[:dim]

def _extract_json(text: str) -> str:
    m = re.search(r'(\[.*?\]|\{.*?\})', text, flags=re.S)
    if not m:
        raise ValueError("No JSON payload found in Gemini response")
    return m.group(1)

# ---- Public helpers: vector alignment ----
def ensure_dim(vec: List[float], dim: int = EMBED_DIM) -> List[float]:
    """Pad or truncate a vector to the desired dimension."""
    return _fit_dim(list(vec), dim)

def l2_normalize(vec: List[float]) -> List[float]:
    """Return L2-normalized copy of the vector (no-op for zero vector)."""
    return _l2_normalize(list(vec))

def align_vector(vec: List[float], dim: int = EMBED_DIM, normalize: bool = True) -> List[float]:
    """Fit to dimension and optionally L2-normalize. Use this before DB inserts."""
    v = ensure_dim(vec, dim)
    return l2_normalize(v) if normalize else v
# ---- Public: text embeddings ----
def embed_text(texts: List[str], *, task_type: str = "RETRIEVAL_DOCUMENT") -> np.ndarray:
    """
    Embeds a list of texts using text-embedding-004 and L2-normalizes each vector.
    task_type: 'RETRIEVAL_DOCUMENT' for corpus items, 'RETRIEVAL_QUERY' for queries.
    """
    out: List[List[float]] = []
    for t in texts:
        resp = genai.embed_content(model=GEMINI_EMBEDDING_MODEL, content=t, task_type=task_type)
        vec = resp["embedding"]
        vec = _fit_dim(vec, EMBED_DIM)
        vec = _l2_normalize(vec)    # using L2 distance in pgvector → normalize for cosine-like ranking
        out.append(vec)
    return np.asarray(out, dtype=np.float32)

def embed_text_one(text: str, *, task_type: str = "RETRIEVAL_DOCUMENT") -> List[float]:
    return embed_text([text], task_type=task_type)[0].tolist()

# ---- Public: captions & lightweight segmentation via Gemini Vision ----
def caption_image(image_bytes: bytes) -> str:
    """
    One-sentence, literal caption suitable for retrieval.
    """
    model = genai.GenerativeModel(GEMINI_VISION_MODEL)
    img = Image.open(io.BytesIO(image_bytes))
    prompt = (
        "Write ONE plain factual sentence describing the visible objects and scene. "
        "Include brand/model only if clearly readable. No speculation."
    )
    r = model.generate_content([prompt, img])
    return (getattr(r, "text", "") or "").strip()

def segment_image(image_bytes: bytes, max_items: int = 10) -> List[Dict]:
    """
    Returns a list of segments: [{ 'caption': str, 'bbox': [x1,y1,x2,y2] in % 0-100 }]
    """
    model = genai.GenerativeModel(GEMINI_VISION_MODEL)
    img = Image.open(io.BytesIO(image_bytes))
    prompt = (
        "Return JSON ONLY (no code fences). Array of objects with keys: "
        "'caption' (string), 'bbox' (array of four percentages [x1,y1,x2,y2], 0-100). "
        f"Limit to {max_items} items. Example: "
        '[{"caption":"red kettle","bbox":[10,20,45,60]}]'
    )
    r = model.generate_content([prompt, img])
    try:
        payload = _extract_json((r.text or "").strip())
        arr = json.loads(payload)
        # quick schema sanitize
        clean = []
        for s in arr:
            if isinstance(s, dict) and "caption" in s and "bbox" in s and isinstance(s["bbox"], list) and len(s["bbox"]) == 4:
                cap = str(s["caption"]).strip()
                bbox = [float(v) for v in s["bbox"]]
                clean.append({"caption": cap, "bbox": bbox})
        return clean
    except Exception:
        return []

# ---- Public: image embedding via caption → text-embedding (keeps a single space) ----
def embed_image_via_caption(image_bytes: bytes) -> List[float]:
    """
    Converts an image to a retrieval vector by:
    1) captioning with Gemini Vision,
    2) embedding the caption text with text-embedding-004,
    3) L2-normalizing to be comparable under vector_l2_ops.
    """
    cap = caption_image(image_bytes)
    return embed_text_one(cap, task_type="RETRIEVAL_DOCUMENT")

# ---- Public: image embeddings (engines: gemini, siglip) ----
_siglip_state: Dict[str, Optional[object]] = {"model": None, "processor": None, "torch": None}

def _get_siglip():
    """Lazy-load SigLIP model/processor and cache them."""
    if _siglip_state["model"] is None or _siglip_state["processor"] is None or _siglip_state["torch"] is None:
        try:
            from transformers import SiglipProcessor, SiglipModel  # type: ignore
            import torch as _torch  # type: ignore
        except Exception as e:
            raise RuntimeError("SigLIP dependencies not installed. Please install 'transformers' and 'torch'.") from e
        _siglip_state["processor"] = SiglipProcessor.from_pretrained("google/siglip-base-patch16-224")
        _siglip_state["model"] = SiglipModel.from_pretrained("google/siglip-base-patch16-224")
        _siglip_state["torch"] = _torch
    return _siglip_state["model"], _siglip_state["processor"], _siglip_state["torch"]

def embed_image_siglip(image_bytes: bytes) -> List[float]:
    """
    Compute SigLIP image-only embedding and align to EMBED_DIM with L2-normalization.
    """
    model, processor, torch = _get_siglip()
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    inputs = processor(images=img, return_tensors="pt")
    with torch.no_grad():
        feats = model.get_image_features(**inputs)
    vec = feats.squeeze().cpu().numpy().tolist()
    vec = _fit_dim(vec, EMBED_DIM)
    vec = _l2_normalize(vec)
    return vec

def embed_image(image_bytes: bytes, engine: str = "gemini") -> List[float]:
    """
    Unified image embedding interface.
    - engine='gemini': caption with Gemini Vision then text-embedding-004
    - engine='siglip': local SigLIP image features
    Returns an EMBED_DIM-sized, L2-normalized vector.
    """
    e = (engine or "gemini").lower()
    if e == "gemini":
        return embed_image_via_caption(image_bytes)
    if e in ("siglip", "siglip-local", "local"):
        return embed_image_siglip(image_bytes)
    raise ValueError(f"Unsupported engine '{engine}'. Use 'gemini' or 'siglip'.")
