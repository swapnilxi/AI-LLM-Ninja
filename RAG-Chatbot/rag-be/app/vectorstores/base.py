from __future__ import annotations

import re
from typing import Sequence
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


class IndexMismatchError(RuntimeError):
    """The existing index was built with a different embedding model / dimension."""


@dataclass
class Chunk:
    profile_id: str
    document_id: str
    source: str  # path relative to the profile folder
    index: int
    text: str
    file_hash: str
    page: int | None = None


@dataclass
class Hit:
    profile_id: str
    document_id: str
    source: str
    index: int
    text: str
    score: float  # cosine similarity, higher is better
    page: int | None = None


@dataclass
class SourceInfo:
    file_hash: str
    chunks: int = 0


@dataclass
class StoreInfo:
    backend: str
    location: str
    chunks: int
    sources: int
    extra: dict = field(default_factory=dict)


def safe_identifier(name: str) -> str:
    """Table / collection names come from user config, so constrain them."""
    ident = re.sub(r"[^A-Za-z0-9_]", "_", name.strip()) or "rag_chunks"
    return ident if not ident[0].isdigit() else f"t_{ident}"


class VectorStore(ABC):
    @abstractmethod
    def ensure(self, dim: int, signature: str) -> None:
        """Create the collection/table if needed. Raise IndexMismatchError if it holds other-model vectors."""

    @abstractmethod
    def check(self, signature: str) -> None:
        """Raise IndexMismatchError if existing vectors came from a different embedder (no-op when empty)."""

    @abstractmethod
    def add(self, chunks: list[Chunk], vectors: list[list[float]], signature: str) -> None: ...

    @abstractmethod
    def search(self, vector: list[float], k: int, profile_ids: Sequence[str]) -> list[Hit]:
        """Nearest chunks among those whose profile_id is in `profile_ids` (filtered inside the query, never after).
        `profile_ids` is mandatory and must not be empty: there is deliberately no unscoped search."""

    @abstractmethod
    def delete_document(self, document_id: str) -> None: ...

    @abstractmethod
    def delete_profile(self, profile_id: str) -> None: ...

    @abstractmethod
    def sources(self) -> dict[str, SourceInfo]:
        """document_id -> info (used for stats only; indexing state lives in SQLite)."""

    @abstractmethod
    def reset(self) -> None:
        """Drop all indexed data."""

    @abstractmethod
    def ping(self) -> StoreInfo:
        """Verify connectivity and return basic stats."""

    def close(self) -> None:  # pragma: no cover - optional
        pass


def require_scope(profile_ids: Sequence[str]) -> list[str]:
    ids = [p for p in profile_ids if p]
    if not ids:
        raise ValueError("A profile scope is required for vector search")
    return ids
