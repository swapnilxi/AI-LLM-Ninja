"""Profile-scoped vector retrieval. There is no unscoped search: every call receives a `RAGContext`."""
from __future__ import annotations

from ..config import Settings
from ..embeddings import build_embedder
from ..vectorstores import Hit, build_store
from .context import RAGContext


def retrieve(settings: Settings, query: str, ctx: RAGContext) -> list[Hit]:
    embedder, store = build_embedder(settings), build_store(settings)
    store.check(embedder.signature)  # fail clearly instead of comparing vectors from different models
    allowed = ctx.allowed_profile_ids
    hits = store.search(embedder.embed_query(query), settings.top_k, allowed)  # filtered inside the search itself
    if any(h.profile_id not in allowed for h in hits):  # invariant guard: must be unreachable
        raise RuntimeError("Vector store returned a chunk outside the requested profile scope")
    return [h for h in hits if h.score >= settings.score_threshold]
