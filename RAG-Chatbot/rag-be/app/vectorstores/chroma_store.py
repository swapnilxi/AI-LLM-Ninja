"""Local, zero-setup vector store (embedded Chroma, persisted on disk)."""
from __future__ import annotations

from collections import defaultdict

from ..config import Settings, resolve_path
from ..http import ProviderError
from .base import Chunk, Hit, IndexMismatchError, SourceInfo, StoreInfo, VectorStore, require_scope, safe_identifier

PAGE = 5000


class ChromaStore(VectorStore):
    def __init__(self, settings: Settings):
        try:
            import chromadb
            from chromadb.config import Settings as ChromaSettings
        except ImportError as e:
            raise ProviderError("chromadb is not installed. Run: pip install chromadb") from e
        self.path = resolve_path(settings.chroma_path)
        self.name = safe_identifier(settings.vector_table)
        self.path.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(self.path), settings=ChromaSettings(anonymized_telemetry=False))

    @property
    def col(self):
        return self.client.get_or_create_collection(self.name, metadata={"hnsw:space": "cosine"})

    def ensure(self, dim: int, signature: str) -> None:
        self.check(signature)

    def check(self, signature: str) -> None:
        col = self.col
        if col.count() == 0:
            return
        sample = col.get(limit=1, include=["metadatas"])["metadatas"][0]
        if "profile_id" not in sample:
            raise IndexMismatchError(
                f"Index '{self.name}' was built before profiles existed. Rebuild the index to add profile metadata."
            )
        if sample.get("embed_sig") != signature:
            raise IndexMismatchError(
                f"Index '{self.name}' was built with '{sample.get('embed_sig')}' but the current embedder is "
                f"'{signature}'. Rebuild the index to switch embedding models."
            )

    def add(self, chunks: list[Chunk], vectors: list[list[float]], signature: str) -> None:
        if not chunks:
            return
        ids, metas = [], []
        for c in chunks:
            ids.append(f"{c.document_id}-{c.index}")
            meta = {"profile_id": c.profile_id, "document_id": c.document_id, "source": c.source,
                    "chunk_index": c.index, "file_hash": c.file_hash, "embed_sig": signature}
            if c.page is not None:
                meta["page"] = c.page
            metas.append(meta)
        col = self.col
        for i in range(0, len(ids), 500):  # stay under Chroma's max batch size
            s = slice(i, i + 500)
            col.upsert(ids=ids[s], embeddings=vectors[s], documents=[c.text for c in chunks[s]], metadatas=metas[s])

    def search(self, vector: list[float], k: int, profile_ids) -> list[Hit]:
        ids = require_scope(profile_ids)
        col = self.col
        if col.count() == 0:
            return []
        where = {"profile_id": ids[0]} if len(ids) == 1 else {"profile_id": {"$in": ids}}
        res = col.query(query_embeddings=[vector], n_results=min(k, col.count()), where=where,
                        include=["documents", "metadatas", "distances"])
        return [
            Hit(m["profile_id"], m["document_id"], m["source"], m["chunk_index"], doc, 1.0 - dist, m.get("page"))
            for doc, m, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0])
        ]

    def delete_document(self, document_id: str) -> None:
        self.col.delete(where={"document_id": document_id})

    def delete_profile(self, profile_id: str) -> None:
        self.col.delete(where={"profile_id": profile_id})

    def sources(self) -> dict[str, SourceInfo]:
        out: dict[str, SourceInfo] = {}
        counts: dict[str, int] = defaultdict(int)
        col, offset = self.col, 0
        while True:
            metas = col.get(limit=PAGE, offset=offset, include=["metadatas"])["metadatas"]
            if not metas:
                break
            for m in metas:
                counts[m["document_id"]] += 1
                out.setdefault(m["document_id"], SourceInfo(m["file_hash"]))
            offset += len(metas)
        for src, n in counts.items():
            out[src].chunks = n
        return out

    def reset(self) -> None:
        try:
            self.client.delete_collection(self.name)
        except Exception:  # collection may not exist yet
            pass

    def ping(self) -> StoreInfo:
        src = self.sources()
        return StoreInfo("chroma", str(self.path), self.col.count(), len(src), {"collection": self.name})
