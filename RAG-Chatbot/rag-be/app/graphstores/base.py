"""The knowledge graph behind Graph RAG.

Nodes are chunks and the entities they mention; an edge says "this chunk mentions this entity". Two chunks are
neighbours when they share an entity, even if they sit in different documents. The vector store still does the
similarity search; the graph store only answers "what else talks about these entities?".

Every call is scoped by profile ids, exactly like the vector store, so a business never reaches another's chunks.
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Sequence

from ..vectorstores.base import Chunk, Hit

MIN_ENTITY_LEN = 3


def norm_entity(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().lower())


@dataclass(frozen=True)
class Entity:
    norm: str
    label: str  # how it was written the first time (shown in the UI)


@dataclass
class GraphInfo:
    backend: str
    location: str
    chunks: int
    entities: int


class GraphStore(ABC):
    @abstractmethod
    def add(self, rows: Sequence[tuple[Chunk, Sequence[str]]]) -> None:
        """Store chunks (with their text) and link each to its entities. Replaces nothing: call delete_document first."""

    @abstractmethod
    def delete_document(self, document_id: str) -> None: ...

    @abstractmethod
    def delete_profile(self, profile_id: str) -> None: ...

    @abstractmethod
    def reset(self) -> None: ...

    @abstractmethod
    def has_data(self, profile_ids: Sequence[str]) -> bool: ...

    @abstractmethod
    def find_in_text(self, text: str, profile_ids: Sequence[str], limit: int = 8) -> list[Entity]:
        """Known entities that appear in `text` (used on the user's question, which is often lowercase)."""

    @abstractmethod
    def entities_of(self, chunks: Sequence[tuple[str, int]], limit: int = 6) -> list[Entity]:
        """Most frequent entities of the given (document_id, chunk_index) chunks."""

    @abstractmethod
    def neighbors(self, entities: Sequence[Entity], profile_ids: Sequence[str], limit: int,
                  exclude: set[tuple[str, int]], hops: int = 2) -> list[Hit]:
        """Chunks that mention the entities (hop 1) or entities that co-occur with them (hop 2).
        Score is the share of the given entities a chunk mentions (halved for hop 2)."""

    @abstractmethod
    def ping(self) -> GraphInfo: ...

    def close(self) -> None:  # pragma: no cover - optional
        pass
