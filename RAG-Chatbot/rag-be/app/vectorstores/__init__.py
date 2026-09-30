from __future__ import annotations

import threading

from ..config import Settings
from .base import Chunk, Hit, IndexMismatchError, SourceInfo, StoreInfo, VectorStore

_cache: dict[tuple, VectorStore] = {}
_lock = threading.Lock()


def build_store(settings: Settings) -> VectorStore:
    """Stores are cached per connection target so pools / Chroma clients are reused."""
    if settings.vector_store == "chroma":
        key = ("chroma", settings.chroma_path, settings.vector_table)
    else:
        key = ("postgres", settings.database_url, settings.vector_table)
    with _lock:
        if key not in _cache:
            if settings.vector_store == "chroma":
                from .chroma_store import ChromaStore

                _cache[key] = ChromaStore(settings)
            else:
                from .pgvector_store import PgVectorStore

                _cache[key] = PgVectorStore(settings)
        return _cache[key]


def close_all() -> None:
    with _lock:
        _cache.clear()
    try:
        from .pgvector_store import close_pools

        close_pools()
    except Exception:
        pass


__all__ = ["Chunk", "Hit", "IndexMismatchError", "SourceInfo", "StoreInfo", "VectorStore", "build_store", "close_all"]
