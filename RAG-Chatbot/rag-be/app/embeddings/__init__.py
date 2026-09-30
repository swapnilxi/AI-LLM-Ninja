from __future__ import annotations

from ..config import Settings
from .base import Embedder, Vector
from .local import HashEmbedder, SentenceTransformerEmbedder
from .remote import GeminiEmbedder, OllamaEmbedder, OpenAIEmbedder

PROVIDERS: dict[str, type[Embedder]] = {
    "sentence-transformers": SentenceTransformerEmbedder,
    "ollama": OllamaEmbedder,
    "gemini": GeminiEmbedder,
    "openai": OpenAIEmbedder,
    "hash": HashEmbedder,
}


def build_embedder(settings: Settings) -> Embedder:
    # Heavy state (loaded ST models) is cached inside the embedder module, so this is cheap.
    return PROVIDERS[settings.embedding_provider](settings)


__all__ = ["Embedder", "Vector", "PROVIDERS", "build_embedder"]
