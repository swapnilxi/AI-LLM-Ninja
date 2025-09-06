# app/embed.py
import os
from typing import List
import numpy as np
from PIL import Image
import torch
import open_clip

# DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
# DTYPE = torch.float16 if DEVICE == "cuda" else torch.float32
DEVICE = "mps" if torch.backends.mps.is_available() else "cpu"
DTYPE = torch.float32  

# Default: SigLIP so400m patch14-384 (1152-dim)
MODEL_NAME = os.getenv("EMBED_MODEL_NAME", "siglip-so400m-patch14-384")
PRETRAINED = os.getenv("EMBED_PRETRAINED", "webli")

_model = None
_preprocess = None
_tokenizer = None

def _lazy_load():
    global _model, _preprocess, _tokenizer
    if _model is None:
        model, _, preprocess = open_clip.create_model_and_transforms(
            MODEL_NAME, pretrained=PRETRAINED, device=DEVICE
        )
        model = model.to(DEVICE)
        if DTYPE == torch.float16:
            model = model.half()
        tokenizer = open_clip.get_tokenizer(MODEL_NAME)
        _model, _preprocess, _tokenizer = model, preprocess, tokenizer

def embed_text(texts: List[str]) -> np.ndarray:
    _lazy_load()
    with torch.inference_mode():
        tokens = _tokenizer(texts).to(DEVICE)
        feats = _model.encode_text(tokens)
        feats = feats.to(torch.float32)
        feats /= feats.norm(dim=-1, keepdim=True).clamp(min=1e-6)
    return feats.cpu().numpy()

def embed_images(pils: List[Image.Image]) -> np.ndarray:
    _lazy_load()
    imgs = torch.stack([_preprocess(im.convert("RGB")) for im in pils])
    imgs = imgs.to(DEVICE, dtype=DTYPE)
    with torch.inference_mode():
        feats = _model.encode_image(imgs)
        feats = feats.to(torch.float32)
        feats /= feats.norm(dim=-1, keepdim=True).clamp(min=1e-6)
    return feats.cpu().numpy()

def embed_text_one(text: str) -> List[float]:
    return embed_text([text])[0].tolist()

def embed_image_one(pil: Image.Image) -> List[float]:
    return embed_images([pil])[0].tolist()

def embedding_dim() -> int:
    vec = embed_text(["probe"])[0]
    return int(vec.shape[-1])
