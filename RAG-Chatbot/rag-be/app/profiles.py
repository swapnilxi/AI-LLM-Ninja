"""Profiles <-> filesystem.

Each folder directly below the data root is a profile (`data/company1/` -> profile "company1").
Everything that turns user input into a path goes through `profile_dir` / `safe_join`, so a
request can never reach outside its own profile folder.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

from .registry import (COMMON_ID, DELETED, DISCOVERED, FAILED, INDEXED, PENDING, SLUG_RE, STALE,
                       Registry)
from .utils.filetypes import SUPPORTED


class UnsafePath(ValueError):
    """A path escaped its profile folder, or is otherwise not allowed."""


def slugify(name: str) -> str:
    """'Acme Corp!' -> 'acme-corp'. Raises ValueError if nothing usable is left."""
    slug = re.sub(r"[^a-z0-9_-]+", "-", name.strip().lower()).strip("-_")[:64].strip("-_")
    if not SLUG_RE.match(slug):
        raise ValueError("Profile name must contain letters or digits")
    return slug


def default_name(slug: str) -> str:
    return re.sub(r"[-_]+", " ", slug).strip().title()


def profile_dir(data_root: Path, profile_id: str) -> Path:
    """Folder of a profile. `profile_id` must be a valid slug (never a path)."""
    if not SLUG_RE.match(profile_id):
        raise UnsafePath("Invalid profile id")
    root = data_root.resolve()
    d = (root / profile_id).resolve()
    if d.parent != root:  # e.g. the folder is a symlink pointing elsewhere
        raise UnsafePath("Profile folder must be a real directory inside the data folder")
    return d


def safe_join(base: Path, rel: str) -> Path:
    """Join a user-supplied relative path onto `base`; refuse absolute paths, '..', hidden parts and symlink escapes."""
    rel = (rel or "").replace("\\", "/")
    if rel.startswith("/") or re.match(r"^[A-Za-z]:", rel):
        raise UnsafePath("Absolute paths are not allowed")
    rel = rel.strip("/")
    p = Path(rel)
    if p.is_absolute() or "\x00" in rel or any(part in ("..",) or part.startswith(".") for part in p.parts):
        raise UnsafePath("Invalid path")
    base = base.resolve()
    target = (base / p).resolve()
    if target != base and not target.is_relative_to(base):
        raise UnsafePath("Invalid path")
    return target


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def iter_files(folder: Path):
    """Supported files below `folder` (dotfiles/dot-dirs ignored), as (relative posix path, Path)."""
    if not folder.is_dir():
        return
    for p in sorted(folder.rglob("*")):
        rel = p.relative_to(folder)
        if p.is_file() and not p.is_symlink() and p.suffix.lower() in SUPPORTED and not any(x.startswith(".") for x in rel.parts):
            yield rel.as_posix(), p


def list_folders(folder: Path) -> list[str]:
    if not folder.is_dir():
        return []
    return sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*")
                  if p.is_dir() and not p.is_symlink() and not any(x.startswith(".") for x in p.relative_to(folder).parts))


# ------------------------------------------------------------------ discovery
@dataclass
class DiscoveryResult:
    registered: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    restored: list[str] = field(default_factory=list)
    skipped: dict[str, str] = field(default_factory=dict)  # folder name -> why


def discover_profiles(reg: Registry, data_root: Path) -> DiscoveryResult:
    """Filesystem -> SQLite: register new top-level folders, flag profiles whose folder vanished."""
    with reg.scan_lock:
        return _discover_locked(reg, data_root)


def _discover_locked(reg: Registry, data_root: Path) -> DiscoveryResult:
    res = DiscoveryResult()
    data_root.mkdir(parents=True, exist_ok=True)
    (data_root / COMMON_ID).mkdir(exist_ok=True)
    known = {p["id"]: p for p in reg.list_profiles(include_removed=True)}
    on_disk = set()
    for d in sorted(data_root.iterdir()):
        if not d.is_dir() or d.name.startswith("."):
            continue
        if d.is_symlink():
            res.skipped[d.name] = "symlinks are not followed"
        elif not SLUG_RE.match(d.name):
            res.skipped[d.name] = "folder name must be lowercase letters, digits, '-' or '_'"
        else:
            on_disk.add(d.name)
    for pid in sorted(on_disk):
        p = known.get(pid)
        if p is None:
            reg.create_profile(pid, "Common" if pid == COMMON_ID else default_name(pid),
                               description="Shared knowledge available to every profile." if pid == COMMON_ID else "")
            res.registered.append(pid)
        elif p["status"] == "missing":
            reg.update_profile(pid, status="active")
            res.restored.append(pid)
    for pid, p in known.items():
        if pid not in on_disk and p["status"] == "active":
            reg.update_profile(pid, status="missing")
            res.missing.append(pid)
    return res


# ------------------------------------------------------------------ document scan
@dataclass
class ScanResult:
    new: list[str] = field(default_factory=list)
    modified: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    unchanged: int = 0


def scan_profile(reg: Registry, data_root: Path, profile_id: str, *, embed_sig: str, chunking_version: str,
                 embedding_version: str) -> ScanResult:
    """Filesystem -> SQLite for one profile. Sets DISCOVERED / STALE / DELETED; never touches the vector store.

    A document is only re-hashed when its size or mtime changed, so scanning a big, unchanged folder is cheap.
    """
    with reg.scan_lock:
        return _scan_locked(reg, data_root, profile_id, embed_sig, chunking_version, embedding_version)


def _scan_locked(reg: Registry, data_root: Path, profile_id: str, embed_sig: str, chunking_version: str,
                 embedding_version: str) -> ScanResult:
    res = ScanResult()
    folder = profile_dir(data_root, profile_id)
    files = dict(iter_files(folder))
    docs = {d["relative_path"]: d for d in reg.list_documents(profile_id)}

    for rel, doc in docs.items():
        if rel not in files:
            if doc["status"] != DELETED:
                reg.update_document(doc["id"], status=DELETED)
            res.deleted.append(rel)

    for rel, path in files.items():
        st = path.stat()
        doc = docs.get(rel)
        if doc is None:
            reg.add_document(profile_id, rel, file_path=str(path), file_size=st.st_size, mtime_ns=st.st_mtime_ns,
                             file_hash=file_hash(path), status=DISCOVERED)
            res.new.append(rel)
            continue
        changed = doc["status"] == DELETED or st.st_size != doc["file_size"] or st.st_mtime_ns != doc["mtime_ns"]
        h = file_hash(path) if changed else doc["file_hash"]
        fields: dict = {}
        if changed:
            fields.update(file_size=st.st_size, mtime_ns=st.st_mtime_ns, file_hash=h, file_path=str(path))
        status = doc["status"]
        if status == DELETED:  # the file came back
            status = INDEXED if doc["indexed_hash"] else DISCOVERED
        if status == INDEXED:
            if h != doc["indexed_hash"]:
                status = STALE
                res.modified.append(rel)
            elif (doc["embedding_model"], doc["chunking_version"], doc["embedding_version"]) != (embed_sig, chunking_version, embedding_version):
                status = STALE  # same content, but indexed with another embedding / chunking configuration
        elif status == FAILED and changed:
            status = PENDING  # the file changed since it failed: give it another try
        elif status in (PENDING, STALE, DISCOVERED) and changed and doc["indexed_hash"] and h != doc["indexed_hash"]:
            res.modified.append(rel)
        if status == INDEXED:
            res.unchanged += 1
        if status != doc["status"] or fields:
            reg.update_document(doc["id"], status=status, **fields)
    return res
