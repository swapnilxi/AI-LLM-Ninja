"""FastAPI entrypoint. Run:  uvicorn app.main:app --reload --port 8000"""
from __future__ import annotations

import json
import secrets
import shutil
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from . import __version__
from .agents import build_router, ensure_default_agents, multi_agent_events
from .catalog import CATALOG
from .config import BASE_DIR, ConfigManager, load_server_config, resolve_path
from .embeddings import build_embedder
from .embeddings import PROVIDERS as EMBEDDERS
from .guides import AnalyzeRequest, AnalyzeResponse, ExplainRequest, GuidesError
from .guides import analyze as run_guides_analysis
from .guides import explain_messages
from .graphstores import build_graph
from .graphstores import close_all as close_graphs
from .graphstores import forget as graph_forget
from .http import ProviderError
from .ingestion.sync import rebuild_graph
from .ingestion import EMBEDDING_VERSION, SUPPORTED, IndexManager, chunking_version, faq_document_id
from .llm import PROVIDERS, build_llm
from .profiles import (UnsafePath, discover_profiles, list_folders, profile_dir, safe_join, scan_profile,
                       slugify)
from .rag import ProfileNotFound, answer_events, resolve_context, retrieve, source_payload
from .registry import COMMON_ID, DELETED, Registry
from .utils import filetypes
from .vectorstores import IndexMismatchError, build_store, close_all

server = load_server_config()
cfg = ConfigManager(resolve_path(server.settings_file))
registry = Registry(resolve_path(server.db_file))
sync_mgr = IndexManager(registry, lambda: cfg.current)
_stop = threading.Event()


def _auto_sync_loop() -> None:
    last = 0.0
    while not _stop.wait(5):
        interval = cfg.current.auto_sync_interval
        if interval and time.time() - last >= interval:
            last = time.time()
            sync_mgr.enqueue(None)


@asynccontextmanager
async def lifespan(_: FastAPI):
    registry.recover_interrupted()
    discover_profiles(registry, cfg.current.data_dir())  # filesystem -> SQLite (cheap; always done)
    for p in registry.list_profiles():
        ensure_default_agents(registry, p["id"])
    if server.sync_on_startup:
        sync_mgr.enqueue(None)  # runs in the background; failures show up in /api/ingest/status
    threading.Thread(target=_auto_sync_loop, daemon=True).start()
    yield
    _stop.set()
    close_all()
    close_graphs()


app = FastAPI(title="RAG Chatbot API", version=__version__, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=server.cors_origins, allow_methods=["*"], allow_headers=["*"],
)


# ---------------------------------------------------------------- errors / auth
@app.exception_handler(ProviderError)
async def _provider_error(_: Request, e: ProviderError):
    return JSONResponse({"detail": str(e)}, status_code=502)


@app.exception_handler(ProfileNotFound)
async def _no_profile(_: Request, e: ProfileNotFound):
    return JSONResponse({"detail": str(e), "code": "profile_not_found"}, status_code=404)


@app.exception_handler(UnsafePath)
async def _unsafe(_: Request, e: UnsafePath):
    return JSONResponse({"detail": str(e)}, status_code=400)


@app.exception_handler(IndexMismatchError)
async def _mismatch(_: Request, e: IndexMismatchError):
    return JSONResponse({"detail": str(e), "code": "index_mismatch"}, status_code=409)


@app.exception_handler(GuidesError)
async def _guides_error(_: Request, e: GuidesError):
    return JSONResponse({"detail": str(e)}, status_code=422)


def require_auth(request: Request) -> None:
    if not server.admin_token:
        return
    supplied = request.headers.get("x-api-key") or request.headers.get("authorization", "").removeprefix("Bearer ")
    if not secrets.compare_digest(supplied.encode(), server.admin_token.encode()):
        raise HTTPException(401, "Invalid or missing API token")


auth = [Depends(require_auth)]


def _need(flag: bool, what: str) -> None:
    if not flag:
        raise HTTPException(403, f"{what} is disabled on this deployment")


# ---------------------------------------------------------------- meta
@app.get("/")
def root():
    return {"message": "Welcome to the RAG Chatbot API!", "docs": "/docs", "health": "/api/health"}


@app.get("/api/health")
def health():
    db_info = {"ok": False, "backend": None}
    try:
        p = build_store(cfg.current).ping()
        db_info = {"ok": True, "backend": p.backend, "chunks": p.chunks}
    except Exception as e:
        db_info = {"ok": False, "error": str(e)}
    return {"ok": True, "version": __version__, "auth_required": bool(server.admin_token), "db": db_info}


@app.get("/api/catalog", dependencies=auth)
def catalog():
    return CATALOG


@app.get("/api/status", dependencies=auth)
def status():
    s = cfg.current
    try:
        info = build_store(s).ping()
        store = {"ok": True, "backend": info.backend, "location": info.location, "chunks": info.chunks, "sources": info.sources}
    except Exception as e:
        store = {"ok": False, "error": str(e)}
    graph = {"enabled": s.graph_enabled, "backend": s.graph_store}
    if s.graph_enabled:
        try:
            gi = build_graph(s).ping()
            graph.update(ok=True, location=gi.location, chunks=gi.chunks, entities=gi.entities)
        except Exception as e:
            graph.update(ok=False, error=str(e)[:300])
    return {
        "store": store,
        "graph": graph,
        "sync": sync_mgr.status,
        "profiles": len(registry.list_profiles()),
        "flags": {"allow_ui_config": server.allow_ui_config, "allow_ui_upload": server.allow_ui_upload},
        "supported_extensions": sorted(SUPPORTED),
    }


# ---------------------------------------------------------------- config
class ConfigPatch(BaseModel):
    values: dict


@app.get("/api/config", dependencies=auth)
def get_config():
    return {"values": cfg.public(), "ui_overrides": cfg.overridden_keys(), "editable": server.allow_ui_config}


@app.put("/api/config", dependencies=auth)
def put_config(body: ConfigPatch):
    _need(server.allow_ui_config, "Editing configuration from the UI")
    try:
        cfg.update(body.values)
    except ValueError as e:
        raise HTTPException(422, str(e))
    return get_config()


@app.delete("/api/config", dependencies=auth)
def reset_config():
    _need(server.allow_ui_config, "Editing configuration from the UI")
    cfg.reset()
    return get_config()


class TestRequest(BaseModel):
    target: str = Field(pattern="^(llm|embedding|vector_store|graph)$")
    values: dict = {}  # unsaved edits from the form


def _merged(values: dict):
    try:
        return cfg.merged(values)
    except Exception as e:
        raise HTTPException(422, str(e))


@app.post("/api/config/test", dependencies=auth)
def test_config(body: TestRequest):
    """Try candidate settings without saving them."""
    s = _merged(body.values)
    t0 = time.time()
    try:
        if body.target == "llm":
            reply = build_llm(s).chat([{"role": "user", "content": "Reply with the single word: ok"}])
            detail = f"Model replied: {reply.strip()[:80]!r}"
        elif body.target == "embedding":
            e = build_embedder(s)
            detail = f"{e.signature} -> {len(e.embed_query('hello world'))}-dim vectors"
        elif body.target == "graph":
            if s.graph_store == "neo4j":  # fresh connection with the unsaved values; never cached
                from .graphstores.neo4j_graph import Neo4jGraphStore

                g = Neo4jGraphStore(s)
                try:
                    gi = g.ping()
                finally:
                    g.close()
            else:
                gi = build_graph(s).ping()
            detail = f"{gi.backend} @ {gi.location}: {gi.chunks} chunks, {gi.entities} entities"
        else:
            info = build_store(s).ping()
            detail = f"{info.backend} @ {info.location}: {info.chunks} chunks from {info.sources} files"
    except Exception as e:
        return {"ok": False, "detail": str(e), "ms": int((time.time() - t0) * 1000)}
    return {"ok": True, "detail": detail, "ms": int((time.time() - t0) * 1000)}


class ModelsRequest(BaseModel):
    kind: str = Field(pattern="^(llm|embedding)$")
    values: dict = {}


@app.post("/api/models", dependencies=auth)
def list_models(body: ModelsRequest):
    """Ask the provider which models it offers (uses unsaved keys/URLs from the form)."""
    s = _merged(body.values)
    provider = build_llm(s) if body.kind == "llm" else build_embedder(s)
    return {"models": provider.list_models()}


# ---------------------------------------------------------------- profiles
def _profile_or_404(profile_id: str) -> dict:
    p = registry.get_profile(profile_id)
    if p is None or p["status"] == "removed":
        raise ProfileNotFound(f"Unknown profile '{profile_id}'")
    return p


def _folder(profile_id: str) -> Path:
    """Absolute folder of a profile, derived from its (validated) id - never from client input."""
    _profile_or_404(profile_id)
    return profile_dir(cfg.current.data_dir(), profile_id)


def _profile_view(p: dict) -> dict:
    s = cfg.current
    return {
        "id": p["id"], "name": p["name"], "folder": f"{s.data_dir().name}/{p['folder_path']}",
        "description": p["description"], "instructions": p["instructions"], "is_common": p["is_common"],
        "include_common": p["include_common"], "use_faqs": p["use_faqs"], "status": p["status"], "last_sync_at": p["last_sync_at"],
        "created_at": p["created_at"], "stats": registry.stats(p["id"]),
        "indexing": sync_mgr.status["profiles"].get(p["id"]),
    }


def _scan(profile_id: str):
    """Cheap filesystem -> SQLite refresh (stat + hash of changed files only). No embedding, no vector store."""
    s = cfg.current
    return scan_profile(registry, s.data_dir(), profile_id, embed_sig=build_embedder(s).signature,
                        chunking_version=chunking_version(s), embedding_version=EMBEDDING_VERSION)


def _doc_or_404(profile_id: str, document_id: str) -> dict:
    _profile_or_404(profile_id)
    d = registry.get_document(document_id)
    if d is None or d["profile_id"] != profile_id:  # a document id from another profile is simply "not found"
        raise HTTPException(404, "Document not found")
    return d


def _doc_path(profile_id: str, doc: dict) -> Path:
    target = safe_join(_folder(profile_id), doc["relative_path"])
    if not target.is_file():
        raise HTTPException(404, "File not found on disk")
    return target


def _doc_view(d: dict, category_ids: list[str] = ()) -> dict:
    rel = d["relative_path"]
    return {
        "id": d["id"], "filename": d["filename"], "relative_path": rel, "folder": rel.rpartition("/")[0],
        "extension": d["extension"], "size": d["file_size"], "modified": d["mtime_ns"] / 1e9 if d["mtime_ns"] else None,
        "status": d["status"], "chunks": d["chunk_count"], "indexed_at": d["indexed_at"], "error": d["error_message"],
        "embedding_model": d["embedding_model"], "embedding_version": d["embedding_version"],
        "chunking_version": d["chunking_version"], "embedding_dimension": d["embedding_dimension"],
        "category_ids": list(category_ids),
    }


class ProfileCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field("", max_length=1000)
    instructions: str = Field("", max_length=20000)
    include_common: bool = True


class ProfilePatch(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, max_length=1000)
    instructions: str | None = Field(None, max_length=20000)
    include_common: bool | None = None
    use_faqs: bool | None = None


@app.get("/api/profiles", dependencies=auth)
def list_profiles():
    discover_profiles(registry, cfg.current.data_dir())  # pick up folders created outside the app
    return {"profiles": [_profile_view(p) for p in registry.list_profiles()], "sync": sync_mgr.status}


@app.post("/api/profiles", dependencies=auth, status_code=201)
def create_profile(body: ProfileCreate):
    _need(server.allow_ui_config, "Creating profiles from the UI")
    try:
        pid = slugify(body.name)
    except ValueError as e:
        raise HTTPException(422, str(e))
    existing = registry.get_profile(pid)
    if existing and existing["status"] == "active":
        raise HTTPException(409, f"Profile '{pid}' already exists")
    folder = profile_dir(cfg.current.data_dir(), pid)
    folder.mkdir(parents=True, exist_ok=True)
    fields = dict(name=body.name.strip(), description=body.description, instructions=body.instructions,
                  include_common=body.include_common)
    if existing:  # a removed / missing profile with the same folder: bring it back
        registry.update_profile(pid, status="active", **fields)
    else:
        registry.create_profile(pid, fields.pop("name"), **fields)
    sync_mgr.enqueue(pid)
    return _profile_view(registry.get_profile(pid))  # type: ignore[arg-type]


@app.post("/api/profiles/sync", dependencies=auth)
def sync_all_profiles(rebuild: bool = False):
    """Discover profile folders, then scan + index every profile in the background."""
    return {"started": sync_mgr.enqueue(None, rebuild=rebuild), "status": sync_mgr.status}


@app.get("/api/profiles/{profile_id}", dependencies=auth)
def get_profile(profile_id: str):
    if _profile_or_404(profile_id)["status"] == "active":
        _scan(profile_id)
    return _profile_view(_profile_or_404(profile_id))


@app.patch("/api/profiles/{profile_id}", dependencies=auth)
def patch_profile(profile_id: str, body: ProfilePatch):
    _need(server.allow_ui_config, "Editing profiles from the UI")
    _profile_or_404(profile_id)
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if "name" in fields:
        fields["name"] = fields["name"].strip()
    if "use_faqs" in fields:
        registry.update_profile(profile_id, use_faqs=fields.pop("use_faqs"))
        sync_mgr.enqueue(profile_id)  # (un)index this profile's FAQs
    if profile_id == COMMON_ID:
        fields.pop("include_common", None)
    return _profile_view(registry.update_profile(profile_id, **fields))


@app.delete("/api/profiles/{profile_id}", dependencies=auth)
def delete_profile(profile_id: str, delete_files: bool = False, confirm: str = ""):
    """Removes the profile from the app and drops its vector index. Files on disk are kept unless
    `delete_files=true` AND `confirm=<profile id>` are both given."""
    _need(server.allow_ui_config, "Deleting profiles from the UI")
    p = _profile_or_404(profile_id)
    if p["is_common"]:
        raise HTTPException(400, "The common profile cannot be deleted")
    if delete_files:
        _need(server.allow_ui_upload, "Deleting files from the UI")
        if confirm != profile_id:
            raise HTTPException(400, f"Deleting files requires confirm={profile_id}")
    build_store(cfg.current).delete_profile(profile_id)
    graph_forget(cfg.current, profile_id=profile_id)
    registry.purge_profile_documents(profile_id)
    if delete_files:
        folder = profile_dir(cfg.current.data_dir(), profile_id)
        if folder.is_dir():
            shutil.rmtree(folder)
        registry.delete_profile(profile_id)
    else:  # keep the folder; a tombstone stops discovery from registering it again
        registry.update_profile(profile_id, status="removed")
    return {"deleted": profile_id, "files_deleted": delete_files}


@app.post("/api/profiles/{profile_id}/sync", dependencies=auth)
def sync_profile(profile_id: str, rebuild: bool = False):
    _profile_or_404(profile_id)
    return {"started": sync_mgr.enqueue(profile_id, rebuild=rebuild), "status": sync_mgr.status}


@app.delete("/api/profiles/{profile_id}/index", dependencies=auth)
def clear_profile_index(profile_id: str):
    """Drop the vector index of one profile (files and profile stay). Documents become STALE until re-indexed."""
    _profile_or_404(profile_id)
    build_store(cfg.current).delete_profile(profile_id)
    graph_forget(cfg.current, profile_id=profile_id)
    registry.reset_index_state(profile_id)
    return {"cleared": profile_id}


# ---------------------------------------------------------------- documents (always inside one profile)
@app.get("/api/profiles/{profile_id}/documents", dependencies=auth)
def profile_documents(profile_id: str):
    p = _profile_or_404(profile_id)
    if p["status"] == "active":
        _scan(profile_id)
    docs = [d for d in registry.list_documents(profile_id) if d["status"] != DELETED]
    cat_ids = registry.document_category_ids(profile_id)
    return {"profile_id": profile_id, "documents": [_doc_view(d, cat_ids.get(d["id"], [])) for d in docs],
            "folders": list_folders(_folder(profile_id)), "categories": registry.list_categories(profile_id),
            "stats": registry.stats(profile_id), "supported_extensions": sorted(SUPPORTED)}


@app.post("/api/profiles/{profile_id}/documents", dependencies=auth)
async def upload_documents(profile_id: str, files: list[UploadFile] = File(...), folder: str = Form(""), sync: bool = True):
    """Validates every file first (type, size, real header, corrupt PDF/DOCX...), then saves all or none."""
    _need(server.allow_ui_upload, "Uploading from the UI")
    root = _folder(profile_id)
    dest = safe_join(root, folder)
    checked = []
    for f in files:
        content = await f.read(server.max_upload_mb * 1024 * 1024 + 1)
        try:
            checked.append((filetypes.validate_upload(f.filename or "", content, max_mb=server.max_upload_mb), content))
        except filetypes.FileTooLarge as e:
            raise HTTPException(413, str(e))
        except filetypes.FileValidationError as e:
            raise HTTPException(400, str(e))
    dest.mkdir(parents=True, exist_ok=True)
    for name, content in checked:
        (dest / name).write_bytes(content)
    _scan(profile_id)
    started = sync_mgr.enqueue(profile_id) if sync else False
    return {"saved": [(dest / n).relative_to(root).as_posix() for n, _ in checked], "sync_started": started}


@app.post("/api/profiles/{profile_id}/documents/reindex", dependencies=auth)
def reindex_documents(profile_id: str, retry_failed: bool = True):
    """Re-embed every document of the profile (also retries failed ones)."""
    _profile_or_404(profile_id)
    _scan(profile_id)
    build_store(cfg.current).delete_profile(profile_id)
    graph_forget(cfg.current, profile_id=profile_id)
    registry.reset_index_state(profile_id)
    return {"started": sync_mgr.enqueue(profile_id, retry_failed=retry_failed), "status": sync_mgr.status}


@app.get("/api/profiles/{profile_id}/documents/{document_id}", dependencies=auth)
def get_document(profile_id: str, document_id: str):
    doc = _doc_or_404(profile_id, document_id)
    return _doc_view(doc, registry.category_ids_for_document(doc["id"]))


@app.get("/api/profiles/{profile_id}/documents/{document_id}/info", dependencies=auth)
def document_info(profile_id: str, document_id: str):
    """Type-specific metadata: PDF pages/title/scanned?, DOCX author/tables..."""
    return filetypes.describe(_doc_path(profile_id, _doc_or_404(profile_id, document_id)))


@app.get("/api/profiles/{profile_id}/documents/{document_id}/file", dependencies=auth)
def document_file(profile_id: str, document_id: str):
    """Serve the original file (inline) so the UI can open a PDF at a cited page."""
    path = _doc_path(profile_id, _doc_or_404(profile_id, document_id))
    ft = filetypes.file_type(path.name)
    return FileResponse(path, media_type=ft.mime if ft else "application/octet-stream", filename=path.name,
                        content_disposition_type="inline")


@app.post("/api/profiles/{profile_id}/documents/{document_id}/index", dependencies=auth)
def index_document(profile_id: str, document_id: str):
    """Force re-indexing of one document."""
    doc = _doc_or_404(profile_id, document_id)
    build_store(cfg.current).delete_document(doc["id"])
    registry.update_document(doc["id"], status="PENDING", error_message="", chunk_count=0, indexed_hash="")
    return {"started": sync_mgr.enqueue(profile_id), "status": sync_mgr.status}


@app.delete("/api/profiles/{profile_id}/documents/{document_id}", dependencies=auth)
def delete_document(profile_id: str, document_id: str):
    _need(server.allow_ui_upload, "Deleting from the UI")
    doc = _doc_or_404(profile_id, document_id)
    path = safe_join(_folder(profile_id), doc["relative_path"])
    build_store(cfg.current).delete_document(doc["id"])
    registry.delete_document(doc["id"])
    path.unlink(missing_ok=True)
    return {"deleted": doc["relative_path"]}


class DocCategoriesPatch(BaseModel):
    category_ids: list[str] = Field(default_factory=list, max_length=50)


@app.patch("/api/profiles/{profile_id}/documents/{document_id}/categories", dependencies=auth)
def set_document_categories(profile_id: str, document_id: str, body: DocCategoriesPatch):
    """Full replace: the document ends up tagged with exactly these categories (must belong to the same profile)."""
    _need(server.allow_ui_upload, "Editing documents from the UI")
    doc = _doc_or_404(profile_id, document_id)
    valid = {c["id"] for c in registry.list_categories(profile_id)}
    unknown = [cid for cid in body.category_ids if cid not in valid]
    if unknown:
        raise HTTPException(422, f"Unknown category ids for this profile: {unknown}")
    registry.set_document_categories(doc["id"], body.category_ids)
    return _doc_view(doc, registry.category_ids_for_document(doc["id"]))


# ---------------------------------------------------------------- document categories (per profile)
class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)


def _category_or_404(profile_id: str, category_id: str) -> dict:
    _profile_or_404(profile_id)
    c = registry.get_category(category_id)
    if c is None or c["profile_id"] != profile_id:
        raise HTTPException(404, "Category not found")
    return c


@app.get("/api/profiles/{profile_id}/categories", dependencies=auth)
def list_categories(profile_id: str):
    _profile_or_404(profile_id)
    return {"categories": registry.list_categories(profile_id)}


@app.post("/api/profiles/{profile_id}/categories", dependencies=auth, status_code=201)
def create_category(profile_id: str, body: CategoryIn):
    _need(server.allow_ui_upload, "Editing categories from the UI")
    _profile_or_404(profile_id)
    name = body.name.strip()
    if any(c["name"].lower() == name.lower() for c in registry.list_categories(profile_id)):
        raise HTTPException(409, f"Category '{name}' already exists for this profile")
    return registry.create_category(profile_id, name)


@app.patch("/api/profiles/{profile_id}/categories/{category_id}", dependencies=auth)
def rename_category(profile_id: str, category_id: str, body: CategoryIn):
    _need(server.allow_ui_upload, "Editing categories from the UI")
    _category_or_404(profile_id, category_id)
    name = body.name.strip()
    if any(c["id"] != category_id and c["name"].lower() == name.lower() for c in registry.list_categories(profile_id)):
        raise HTTPException(409, f"Category '{name}' already exists for this profile")
    return registry.rename_category(category_id, name)


@app.delete("/api/profiles/{profile_id}/categories/{category_id}", dependencies=auth)
def delete_category(profile_id: str, category_id: str):
    """Deletes the category and un-tags it from every document (the documents themselves are untouched)."""
    _need(server.allow_ui_upload, "Editing categories from the UI")
    _category_or_404(profile_id, category_id)
    registry.delete_category(category_id)
    return {"deleted": category_id}


# ---------------------------------------------------------------- folders
class FolderCreate(BaseModel):
    path: str = Field(min_length=1, max_length=500)


@app.get("/api/profiles/{profile_id}/folders", dependencies=auth)
def get_folders(profile_id: str):
    return {"folders": list_folders(_folder(profile_id))}


@app.post("/api/profiles/{profile_id}/folders", dependencies=auth, status_code=201)
def create_folder(profile_id: str, body: FolderCreate):
    _need(server.allow_ui_upload, "Creating folders from the UI")
    root = _folder(profile_id)
    target = safe_join(root, body.path)
    if target == root:
        raise HTTPException(400, "Invalid folder name")
    target.mkdir(parents=True, exist_ok=True)
    return {"folder": target.relative_to(root).as_posix()}


@app.delete("/api/profiles/{profile_id}/folders/{folder_path:path}", dependencies=auth)
def delete_folder(profile_id: str, folder_path: str, recursive: bool = False, confirm: bool = False):
    """Empty folders are removed directly. A folder with content needs `recursive=true&confirm=true`."""
    _need(server.allow_ui_upload, "Deleting from the UI")
    root = _folder(profile_id)
    target = safe_join(root, folder_path)
    if target == root or not target.is_dir():
        raise HTTPException(404, "Folder not found")
    if any(target.iterdir()):
        if not recursive:
            raise HTTPException(409, "Folder is not empty. Use recursive=true and confirm=true to delete its contents.")
        if not confirm:
            raise HTTPException(400, "Deleting a folder's contents requires confirm=true")
        rel = target.relative_to(root).as_posix() + "/"
        store = build_store(cfg.current)
        for d in registry.list_documents(profile_id):
            if d["relative_path"].startswith(rel):
                store.delete_document(d["id"])
                graph_forget(cfg.current, document_id=d["id"])
                registry.delete_document(d["id"])
        shutil.rmtree(target)
    else:
        target.rmdir()
    return {"deleted": folder_path}


# ---------------------------------------------------------------- FAQs (per profile)
class FaqIn(BaseModel):
    """The JSON schema for import / export is exactly {question, answer}; category and enabled are optional extras."""
    question: str = Field(min_length=1, max_length=500)
    answer: str = Field(min_length=1, max_length=8000)
    category: str = Field("", max_length=60)
    enabled: bool = True


class FaqPatch(BaseModel):
    question: str | None = Field(None, min_length=1, max_length=500)
    answer: str | None = Field(None, min_length=1, max_length=8000)
    category: str | None = Field(None, max_length=60)
    enabled: bool | None = None


class FaqImport(BaseModel):
    faqs: list[FaqIn] = Field(max_length=2000)


def _faq_view(f: dict) -> dict:
    return {k: f[k] for k in ("id", "question", "answer", "category", "enabled", "position", "status", "indexed_at", "error_message", "updated_at")}


def _faq_or_404(profile_id: str, faq_id: str) -> dict:
    _profile_or_404(profile_id)
    f = registry.get_faq(faq_id)
    if f is None or f["profile_id"] != profile_id:
        raise HTTPException(404, "FAQ not found")
    return f


def _norm(q: str) -> str:
    return " ".join(q.lower().split())


@app.get("/api/profiles/{profile_id}/faqs", dependencies=auth)
def list_faqs(profile_id: str):
    p = _profile_or_404(profile_id)
    return {"profile_id": profile_id, "use_faqs": p["use_faqs"], "faqs": [_faq_view(f) for f in registry.list_faqs(profile_id)],
            "stats": registry.stats(profile_id)}


@app.post("/api/profiles/{profile_id}/faqs", dependencies=auth, status_code=201)
def create_faq(profile_id: str, body: FaqIn):
    _need(server.allow_ui_upload, "Editing FAQs from the UI")
    _profile_or_404(profile_id)
    if any(_norm(f["question"]) == _norm(body.question) for f in registry.list_faqs(profile_id)):
        raise HTTPException(409, "A FAQ with this question already exists")
    f = registry.add_faq(profile_id, body.question.strip(), body.answer.strip(), category=body.category.strip(), enabled=body.enabled)
    sync_mgr.enqueue(profile_id)
    return _faq_view(f)


@app.post("/api/profiles/{profile_id}/faqs/import", dependencies=auth)
def import_faqs(profile_id: str, body: FaqImport, mode: str = "append"):
    """`append` adds new questions and skips ones that already exist; `replace` deletes every FAQ of the profile first."""
    _need(server.allow_ui_upload, "Editing FAQs from the UI")
    _profile_or_404(profile_id)
    if mode not in ("append", "replace"):
        raise HTTPException(422, "mode must be 'append' or 'replace'")
    store = build_store(cfg.current)
    if mode == "replace":
        for f in registry.list_faqs(profile_id):
            store.delete_document(faq_document_id(f["id"]))
        registry.delete_faqs(profile_id)
    seen = {_norm(f["question"]) for f in registry.list_faqs(profile_id)}
    added = skipped = 0
    for item in body.faqs:
        key = _norm(item.question)
        if key in seen:
            skipped += 1
            continue
        seen.add(key)
        registry.add_faq(profile_id, item.question.strip(), item.answer.strip(), category=item.category.strip(), enabled=item.enabled)
        added += 1
    sync_mgr.enqueue(profile_id)
    return {"added": added, "skipped_duplicates": skipped, "mode": mode, "total": len(registry.list_faqs(profile_id))}


@app.get("/api/profiles/{profile_id}/faqs/export", dependencies=auth)
def export_faqs(profile_id: str, enabled_only: bool = False):
    """Download as JSON: [{"question": ..., "answer": ...}, ...] (the same schema import accepts)."""
    _profile_or_404(profile_id)
    rows = [{"question": f["question"], "answer": f["answer"]} for f in registry.list_faqs(profile_id) if f["enabled"] or not enabled_only]
    return JSONResponse(rows, headers={"Content-Disposition": f'attachment; filename="{profile_id}-faqs.json"'})


@app.patch("/api/profiles/{profile_id}/faqs/{faq_id}", dependencies=auth)
def update_faq(profile_id: str, faq_id: str, body: FaqPatch):
    _need(server.allow_ui_upload, "Editing FAQs from the UI")
    cur = _faq_or_404(profile_id, faq_id)
    fields = {k: (v.strip() if isinstance(v, str) else v) for k, v in body.model_dump().items() if v is not None}
    if "question" in fields and any(f["id"] != faq_id and _norm(f["question"]) == _norm(fields["question"]) for f in registry.list_faqs(profile_id)):
        raise HTTPException(409, "A FAQ with this question already exists")
    if {"question", "answer"} & set(fields) or ("enabled" in fields and fields["enabled"] != cur["enabled"]):
        fields["status"] = "PENDING"  # content or visibility changed: the indexer re-embeds / removes it
    registry.update_faq(faq_id, **fields)
    sync_mgr.enqueue(profile_id)
    return _faq_view(registry.get_faq(faq_id))  # type: ignore[arg-type]


@app.delete("/api/profiles/{profile_id}/faqs/{faq_id}", dependencies=auth)
def delete_faq(profile_id: str, faq_id: str):
    _need(server.allow_ui_upload, "Editing FAQs from the UI")
    _faq_or_404(profile_id, faq_id)
    build_store(cfg.current).delete_document(faq_document_id(faq_id))
    registry.delete_faq(faq_id)
    return {"deleted": faq_id}


# ---------------------------------------------------------------- ingestion status
@app.post("/api/graph/rebuild", dependencies=auth)
def rebuild_graph_all(profile_id: str = ""):
    """Rebuild the entity graph from already-indexed files (all businesses, or `?profile_id=`). Needed once for documents
    indexed before Graph RAG existed, or after switching graph store / extractor."""
    s = cfg.current
    if not s.graph_enabled:
        raise HTTPException(409, "The graph is disabled (GRAPH_ENABLED=false)")
    ids = [_profile_or_404(profile_id)["id"]] if profile_id else [p["id"] for p in registry.list_profiles() if p["status"] == "active"]
    try:
        chunks = sum(rebuild_graph(registry, s, pid) for pid in ids)
        info = build_graph(s).ping()
    except ProviderError as e:
        raise HTTPException(502, str(e))
    return {"profiles": ids, "chunks": chunks, "graph": {"backend": info.backend, "chunks": info.chunks, "entities": info.entities}}


@app.get("/api/ingest/status", dependencies=auth)
def ingest_status():
    return sync_mgr.status


# ---------------------------------------------------------------- chat
class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    profile_id: str = Field(min_length=1, max_length=64)  # the profile whose documents may be used (resolved server-side)
    message: str = Field(min_length=1, max_length=8000)
    history: list[ChatMessage] = []
    stream: bool = True
    # optional per-request override of the configured LLM (replaces the old /chat-openai/, /chat-groq/)
    provider: str | None = None
    model: str | None = None
    graph_rag: bool | None = None  # None = use the configured default (Settings -> graph_rag)
    multi_agent: bool = False  # run the profile's agent team (planner / researchers / critic / synthesizer)


class ContextRequest(BaseModel):
    profile_id: str = Field(min_length=1, max_length=64)
    query: str = Field(min_length=1, max_length=8000)
    limit: int | None = Field(None, ge=1, le=50)


@app.post("/api/query-context", dependencies=auth)
def query_context(body: ContextRequest):
    """Retrieval only, no LLM: the chunks that would be sent as context."""
    s = cfg.current
    ctx = resolve_context(registry, body.profile_id)
    if body.limit:
        s = s.model_copy(update={"top_k": body.limit})
    hits = retrieve(s, body.query, ctx)
    return {"context": "\n".join(h.text for h in hits), "sources": source_payload(hits, ctx)}


@app.post("/api/chat", dependencies=auth)
def chat(body: ChatRequest):
    s = cfg.current
    ctx = resolve_context(registry, body.profile_id)
    if body.provider or body.model:
        if body.provider and body.provider not in PROVIDERS:
            raise HTTPException(422, f"Unknown provider '{body.provider}'. Choose from: {', '.join(PROVIDERS)}")
        update = {"llm_model": body.model or ""}  # a model name from another provider would be wrong
        if body.provider:
            update["llm_provider"] = body.provider
        s = s.model_copy(update=update)
    history = [m.model_dump() for m in body.history]
    if body.multi_agent:
        ensure_default_agents(registry, ctx.profile_id)
    run = (lambda: multi_agent_events(s, registry, body.message, history, ctx, body.graph_rag)) if body.multi_agent \
        else (lambda: answer_events(s, body.message, history, ctx, body.graph_rag))

    if not body.stream:
        sources, answer = [], []
        for ev in run():
            if ev["type"] == "sources":
                sources = ev["sources"]
            elif ev["type"] == "token":
                answer.append(ev["text"])
        return {"answer": "".join(answer), "sources": sources}

    events = run()
    try:
        first = next(events)  # surface retrieval errors (bad DB, index mismatch) as real HTTP errors
    except StopIteration:
        first = None

    def sse():
        def pack(ev: dict) -> str:
            return f"data: {json.dumps(ev)}\n\n"

        try:
            if first:
                yield pack(first)
            for ev in events:
                yield pack(ev)
        except Exception as e:  # mid-stream LLM failure
            yield pack({"type": "error", "message": str(e)})

    return StreamingResponse(sse(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


app.include_router(build_router(registry, auth, _profile_or_404))  # /api/agents (see app/agents/)


# ---------------------------------------------------------------- guides (RAG best-practice checklist)
@app.post("/api/guides/analyze", dependencies=auth, response_model=AnalyzeResponse)
def guides_analyze(body: AnalyzeRequest):
    """Judge this app's own code, or a public GitHub repo, against the checklist the UI sends."""
    return run_guides_analysis(cfg.current, body.repo_url, body.checklist)


@app.post("/api/guides/explain", dependencies=auth)
def guides_explain(body: ExplainRequest):
    """Explain one checklist item, with optional follow-up questions (history)."""
    llm = build_llm(cfg.current)
    messages = explain_messages(body)
    if not body.stream:
        return {"answer": llm.chat(messages)}

    def sse():
        try:
            for token in llm.stream(messages):
                yield f"data: {json.dumps({'type': 'token', 'text': token})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as e:  # mid-stream LLM failure
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(sse(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


if __name__ == "__main__":  # python -m app.main
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
