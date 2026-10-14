"""Indexing: keep the vector store in sync with what SQLite says each profile's documents look like.

    profile folder --scan--> documents table --(new / stale / deleted)--> parse -> chunk -> embed -> vector store

`scan_profile` (app/profiles.py) decides *what* needs work by comparing files with SQLite; this module does
the work and records the outcome (status, embedding + chunking versions, errors) back in SQLite.
Jobs run on one background worker so chat requests never wait for indexing.
"""
from __future__ import annotations

import hashlib
import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Callable

from ..config import Settings
from ..embeddings import build_embedder
from ..graphstores import forget as graph_forget
from ..graphstores import index_chunks as graph_index
from ..profiles import discover_profiles, profile_dir, scan_profile
from ..registry import DELETED, DISCOVERED, FAILED, INDEXED, INDEXING, PENDING, STALE, Registry
from ..vectorstores import Chunk, build_store
from .chunker import chunk_text
from .loaders import SUPPORTED, load_file

EMBEDDING_VERSION = "1"  # bump when the embedding/parsing pipeline changes in a way that invalidates old chunks


def chunking_version(s: Settings) -> str:
    return f"v1:{s.chunk_size}:{s.chunk_overlap}"


@dataclass
class SyncResult:
    added: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    unchanged: int = 0
    chunks: int = 0
    errors: dict[str, str] = field(default_factory=dict)
    seconds: float = 0.0
    faqs: int = 0  # FAQ entries (re)embedded in this run

    def merge(self, other: "SyncResult", prefix: str = "") -> None:
        self.added += [prefix + x for x in other.added]
        self.updated += [prefix + x for x in other.updated]
        self.removed += [prefix + x for x in other.removed]
        self.unchanged += other.unchanged
        self.chunks += other.chunks
        self.faqs += other.faqs
        self.errors.update({prefix + k: v for k, v in other.errors.items()})
        self.seconds = round(self.seconds + other.seconds, 2)


FAQ_PREFIX = "faq-"


def faq_document_id(faq_id: str) -> str:
    """Vector-store document id of a FAQ (distinct from file document ids)."""
    return FAQ_PREFIX + faq_id


def faq_text(question: str, answer: str) -> str:
    return f"Q: {question.strip()}\nA: {answer.strip()}"


def faq_hash(question: str, answer: str) -> str:
    return hashlib.sha256(faq_text(question, answer).encode()).hexdigest()


def sync_faqs(reg: Registry, profile_id: str, embedder, store, res: SyncResult) -> None:
    """One chunk per FAQ. Embeds new / edited FAQs (or ones made with another embedding model) and removes
    the chunks of disabled FAQs, so search only ever sees the FAQs the user has switched on."""
    profile = reg.get_profile(profile_id)
    active = bool(profile and profile["use_faqs"])
    todo = []
    for f in reg.list_faqs(profile_id):
        doc_id = faq_document_id(f["id"])
        if not (active and f["enabled"]):
            if f["status"] != "DISABLED":
                store.delete_document(doc_id)
                reg.update_faq(f["id"], status="DISABLED", indexed_hash="", embedding_model="", error_message="")
            continue
        if f["status"] != "INDEXED" or f["indexed_hash"] != faq_hash(f["question"], f["answer"]) or f["embedding_model"] != embedder.signature:
            todo.append(f)
    for i in range(0, len(todo), 64):
        batch = todo[i : i + 64]
        try:
            vectors = embedder.embed_documents([faq_text(f["question"], f["answer"]) for f in batch])
            for f, vec in zip(batch, vectors):
                doc_id, h = faq_document_id(f["id"]), faq_hash(f["question"], f["answer"])
                store.delete_document(doc_id)
                store.add([Chunk(profile_id, doc_id, "FAQ: " + f["question"][:120], 0, faq_text(f["question"], f["answer"]), h)], [vec], embedder.signature)
                reg.update_faq(f["id"], status="INDEXED", indexed_hash=h, embedding_model=embedder.signature, indexed_at=time.time(), error_message="")
                res.faqs += 1
        except Exception as e:  # noqa: BLE001 - keep going; the FAQ shows FAILED with the reason
            for f in batch:
                reg.update_faq(f["id"], status="FAILED", error_message=str(e)[:500])
                res.errors["FAQ: " + f["question"][:60]] = str(e)


def _graph_llm(settings: Settings):
    if settings.graph_enabled and settings.graph_extractor == "llm":
        from ..llm import build_llm

        return build_llm(settings)
    return None


def rebuild_graph(reg: Registry, settings: Settings, profile_id: str,
                  progress: Callable[[str], None] = lambda _m: None) -> int:
    """(Re)build one profile's graph from its already-indexed files. Re-chunks only (no embeddings, no vector writes),
    so it is cheap with the heuristic extractor. Chunking is deterministic, so chunk ids match the vector store."""
    from ..graphstores import forget

    forget(settings, profile_id=profile_id)
    folder, llm, total = profile_dir(settings.data_dir(), profile_id), _graph_llm(settings), 0
    for doc in reg.list_documents(profile_id, (INDEXED,)):
        path = folder / doc["relative_path"]
        if not path.is_file():
            continue
        progress(f"[{profile_id}] graph: {doc['relative_path']}")
        chunks = [Chunk(profile_id, doc["id"], doc["relative_path"], 0, text, doc["file_hash"], page)
                  for page, section in load_file(path) for text in chunk_text(section, settings.chunk_size, settings.chunk_overlap)]
        for n, c in enumerate(chunks):
            c.index = n
        graph_index(settings, chunks, llm)
        total += len(chunks)
    return total


def index_profile(reg: Registry, settings: Settings, profile_id: str, *, retry_failed: bool = False,
                  progress: Callable[[str], None] = lambda _m: None) -> SyncResult:
    """Scan one profile folder and (re)index whatever changed. Unchanged documents are never re-embedded."""
    t0 = time.time()
    res = SyncResult()
    embedder, store = build_embedder(settings), build_store(settings)
    chunk_ver = chunking_version(settings)
    data_root = settings.data_dir()

    progress("Checking embedding model")
    dim = len(embedder.embed_query("dimension probe"))
    store.ensure(dim, embedder.signature)

    progress(f"[{profile_id}] Scanning files")
    scan = scan_profile(reg, data_root, profile_id, embed_sig=embedder.signature, chunking_version=chunk_ver,
                        embedding_version=EMBEDDING_VERSION)
    res.unchanged = scan.unchanged

    for doc in reg.list_documents(profile_id, (DELETED,)):
        store.delete_document(doc["id"])
        graph_forget(settings, document_id=doc["id"])
        reg.delete_document(doc["id"])
        res.removed.append(doc["relative_path"])

    todo_states = (DISCOVERED, PENDING, STALE) + ((FAILED,) if retry_failed else ())
    todo = reg.list_documents(profile_id, todo_states)
    folder = profile_dir(data_root, profile_id)
    for i, doc in enumerate(todo, start=1):
        rel = doc["relative_path"]
        progress(f"[{profile_id}] [{i}/{len(todo)}] {rel}")
        reg.update_document(doc["id"], status=INDEXING, error_message="")
        try:
            path = folder / rel
            if path.suffix.lower() not in SUPPORTED:
                raise ValueError(f"Unsupported file type: {path.suffix}")
            h = doc["file_hash"]
            chunks = [
                Chunk(profile_id, doc["id"], rel, 0, text, h, page)
                for page, section in load_file(path)
                for text in chunk_text(section, settings.chunk_size, settings.chunk_overlap)
            ]
            for n, c in enumerate(chunks):
                c.index = n
            if not chunks:
                raise ValueError("no extractable text (scanned PDF or empty file?)")
            vectors = embedder.embed_documents([c.text for c in chunks])
            store.delete_document(doc["id"])  # replace, don't append, when a file changed
            store.add(chunks, vectors, embedder.signature)
            graph_forget(settings, document_id=doc["id"])
            graph_index(settings, chunks, _graph_llm(settings))
            reg.update_document(
                doc["id"], status=INDEXED, indexed_hash=h, chunk_count=len(chunks), indexed_at=time.time(),
                embedding_model=embedder.signature, embedding_version=EMBEDDING_VERSION, chunking_version=chunk_ver,
                embedding_dimension=dim, error_message="",
            )
            (res.updated if doc["indexed_hash"] else res.added).append(rel)
            res.chunks += len(chunks)
        except Exception as e:  # one bad file must not abort the whole job
            store.delete_document(doc["id"])
            graph_forget(settings, document_id=doc["id"])
            reg.update_document(doc["id"], status=FAILED, error_message=str(e)[:500], chunk_count=0, indexed_hash="")
            res.errors[rel] = str(e)

    progress(f"[{profile_id}] FAQs")
    sync_faqs(reg, profile_id, embedder, store, res)

    reg.update_profile(profile_id, last_sync_at=time.time())
    res.seconds = round(time.time() - t0, 2)
    return res


# ---------------------------------------------------------------- background jobs
@dataclass
class Job:
    profile_id: str | None  # None = discover + every profile
    rebuild: bool = False
    retry_failed: bool = False


def _blank(state: str = "idle") -> dict:
    return {"state": state, "message": "", "result": None, "error": None, "finished_at": None}


class IndexManager:
    """One background worker draining a queue of index jobs; status is exposed for the UI.

    An `enqueue` for a profile that is already *queued* is coalesced; one made while it is *running* queues a
    follow-up run (so files uploaded mid-job aren't missed).
    """

    def __init__(self, reg: Registry, get_settings: Callable[[], Settings]):
        self.reg, self.get_settings = reg, get_settings
        self._lock = threading.Lock()
        self._queue: list[Job] = []
        self._worker: threading.Thread | None = None
        self._agg = SyncResult()
        self.status: dict = {**_blank(), "profile": None, "queued": [], "profiles": {}}

    @property
    def running(self) -> bool:
        return self.status["state"] == "running"

    def enqueue(self, profile_id: str | None, *, rebuild: bool = False, retry_failed: bool = False) -> bool:
        """Returns True if a new job was queued (False when an identical one was already waiting)."""
        with self._lock:
            for j in self._queue:
                if j.profile_id == profile_id:  # the same target is already waiting
                    j.rebuild |= rebuild
                    j.retry_failed |= retry_failed
                    return False
                if j.profile_id is None and not rebuild:  # a queued full sync already covers a plain profile sync
                    j.retry_failed |= retry_failed
                    return False
            self._queue.append(Job(profile_id, rebuild, retry_failed))
            if not self.running:
                self.status = {**_blank("running"), "message": "Starting", "profile": None, "queued": [],
                               "profiles": self.status.get("profiles", {})}
                self._agg = SyncResult()
            self.status["queued"] = [j.profile_id or "*" for j in self._queue]
            if self._worker is None or not self._worker.is_alive():
                self._worker = threading.Thread(target=self._run, daemon=True)
                self._worker.start()
            return True

    def _progress(self, msg: str) -> None:
        self.status["message"] = msg

    def _run(self) -> None:
        errors: list[str] = []
        while True:
            with self._lock:
                if not self._queue:
                    st = self.status
                    st.update(state="error" if errors else "done", message="Finished", profile=None, queued=[],
                              error="; ".join(errors[:3]) or None, finished_at=time.time(),
                              result=asdict(self._agg))
                    self._worker = None
                    return
                job = self._queue.pop(0)
                self.status["queued"] = [j.profile_id or "*" for j in self._queue]
            try:
                self._do(job)
            except Exception as e:  # noqa: BLE001 - reported through the status, never crashes the worker
                errors.append(str(e))

    def _do(self, job: Job) -> None:
        settings = self.get_settings()
        agg = self._agg
        if job.profile_id is None:
            discover_profiles(self.reg, settings.data_dir())
            if job.rebuild:
                self._progress("Dropping existing index")
                build_store(settings).reset()
                graph_forget(settings, everything=True)
                self.reg.reset_index_state()
            targets = [p["id"] for p in self.reg.list_profiles() if p["status"] == "active"]
        else:
            targets = [job.profile_id]
            if job.rebuild:
                self._progress(f"[{job.profile_id}] Dropping profile index")
                build_store(settings).delete_profile(job.profile_id)
                graph_forget(settings, profile_id=job.profile_id)
                self.reg.reset_index_state(job.profile_id)
        failures: list[str] = []
        for pid in targets:
            p = self.reg.get_profile(pid)
            if not p or p["status"] != "active":
                continue
            self.status["profile"] = pid
            self.status["profiles"][pid] = {**_blank("running"), "message": "Starting"}
            try:
                res = index_profile(self.reg, settings, pid, retry_failed=job.retry_failed or job.rebuild,
                                    progress=lambda m, pid=pid: (self._progress(m), self.status["profiles"][pid].update(message=m)))
                agg.merge(res, prefix="" if len(targets) == 1 else f"{pid}/")
                self.status["profiles"][pid] = {**_blank("done"), "result": asdict(res), "finished_at": time.time()}
            except Exception as e:  # noqa: BLE001
                self.status["profiles"][pid] = {**_blank("error"), "error": str(e), "finished_at": time.time()}
                failures.append(f"{pid}: {e}" if len(targets) > 1 else str(e))
        if failures:
            raise RuntimeError("; ".join(failures))
