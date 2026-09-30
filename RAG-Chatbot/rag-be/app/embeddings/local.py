"""Offline embedders: sentence-transformers (real) and a dependency-free hashing fallback."""
from __future__ import annotations

import hashlib
import re
import threading

from ..http import ProviderError
from .base import Embedder, Vector

_models: dict[str, object] = {}
_lock = threading.Lock()


class SentenceTransformerEmbedder(Embedder):
    provider = "sentence-transformers"
    default_model = "sentence-transformers/all-MiniLM-L6-v2"  # 384-dim, ~90MB, CPU friendly
    batch_size = 64

    def _load(self):
        with _lock:  # model loading is slow and not thread-safe
            if self.model not in _models:
                try:
                    from sentence_transformers import SentenceTransformer
                except ImportError as e:
                    raise ProviderError(
                        "sentence-transformers is not installed. Run: pip install 'rag-be[local]' "
                        "(or choose the gemini / ollama embedding provider)"
                    ) from e
                _models[self.model] = SentenceTransformer(self.model)
            return _models[self.model]

    def _embed(self, texts: list[str], *, query: bool) -> list[Vector]:
        if "e5" in self.model.lower():  # e5 models expect role prefixes
            prefix = "query: " if query else "passage: "
            texts = [prefix + t for t in texts]
        return self._load().encode(texts, normalize_embeddings=True, show_progress_bar=False).tolist()


class HashEmbedder(Embedder):
    """Feature-hashing bag of words. Lexical only, but needs no model or network:
    handy for demos, CI and smoke tests."""

    provider = "hash"
    default_model = "hash-256"
    DIM = 256

    def _embed(self, texts: list[str], *, query: bool) -> list[Vector]:
        out = []
        for text in texts:
            v = [0.0] * self.DIM
            for tok in re.findall(r"\w+", text.lower()):
                h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
                v[h % self.DIM] += 1.0 if (h >> 64) & 1 else -1.0
            out.append(v)
        return out
