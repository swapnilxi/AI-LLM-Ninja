from __future__ import annotations

import math
from abc import ABC, abstractmethod

from ..config import Settings

Vector = list[float]


def normalize(v: Vector) -> Vector:
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


class Embedder(ABC):
    provider = ""
    default_model = ""
    batch_size = 32

    def __init__(self, settings: Settings):
        self.s = settings
        self.model = settings.embedding_model or self.default_model

    @property
    def signature(self) -> str:
        """Identifies the vector space. Vectors from different signatures must never be mixed."""
        dims = self.s.embedding_dimensions if self.provider in ("gemini", "openai") else 0
        return f"{self.provider}|{self.model}|{dims}"

    @abstractmethod
    def _embed(self, texts: list[str], *, query: bool) -> list[Vector]: ...

    def embed_documents(self, texts: list[str]) -> list[Vector]:
        out: list[Vector] = []
        for i in range(0, len(texts), self.batch_size):
            out.extend(normalize(v) for v in self._embed(texts[i : i + self.batch_size], query=False))
        return out

    def embed_query(self, text: str) -> Vector:
        return normalize(self._embed([text], query=True)[0])

    def list_models(self) -> list[str]:
        return []
