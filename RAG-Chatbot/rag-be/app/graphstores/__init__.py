from __future__ import annotations

import logging
import threading
from typing import Sequence

from ..config import Settings
from ..vectorstores.base import Chunk
from .base import Entity, GraphInfo, GraphStore
from .extract import extract_entities, heuristic_entities

log = logging.getLogger(__name__)
_cache: dict[tuple, GraphStore] = {}
_lock = threading.Lock()


def build_graph(settings: Settings) -> GraphStore:
    """SQLite (local file, the default) or Neo4j (GRAPH_STORE=neo4j). Cached per connection target."""
    if settings.graph_store == "neo4j":
        key = ("neo4j", settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password, settings.neo4j_database)
    else:
        key = ("sqlite", settings.graph_db_path)
    with _lock:
        if key not in _cache:
            if settings.graph_store == "neo4j":
                from .neo4j_graph import Neo4jGraphStore

                _cache[key] = Neo4jGraphStore(settings)
            else:
                from .sqlite_graph import SqliteGraphStore

                _cache[key] = SqliteGraphStore(settings)
        return _cache[key]


def index_chunks(settings: Settings, chunks: Sequence[Chunk], llm=None) -> None:
    """Add chunks (and their entities) to the graph. Never raises: a graph problem must not fail document indexing."""
    if not settings.graph_enabled or not chunks:
        return
    try:
        build_graph(settings).add([(c, extract_entities(c.text, settings, llm)) for c in chunks])
    except Exception as e:
        log.warning("graph indexing skipped: %s", e)


def forget(settings: Settings, *, document_id: str | None = None, profile_id: str | None = None, everything: bool = False) -> None:
    """Remove graph data alongside the vector data. Never raises."""
    if not settings.graph_enabled:
        return
    try:
        g = build_graph(settings)
        if everything:
            g.reset()
        elif document_id:
            g.delete_document(document_id)
        elif profile_id:
            g.delete_profile(profile_id)
    except Exception as e:
        log.warning("graph cleanup skipped: %s", e)


def close_all() -> None:
    with _lock:
        for g in _cache.values():
            try:
                g.close()
            except Exception:
                pass
        _cache.clear()


__all__ = ["Entity", "GraphInfo", "GraphStore", "build_graph", "close_all", "extract_entities", "forget",
           "heuristic_entities", "index_chunks"]
