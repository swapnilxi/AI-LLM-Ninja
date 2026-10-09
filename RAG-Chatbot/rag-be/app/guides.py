"""Guides tab: analyze a codebase (this app, or a public GitHub repo) against a RAG best-practice
checklist, and let the UI ask follow-up questions about any single checklist item.

Stateless - no DB, no profile scoping. The checklist content itself is owned by the frontend
(components/Guides.tsx) and sent with every request, so it lives in exactly one place.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import httpx
from pydantic import BaseModel, Field

from .config import BASE_DIR, Settings
from .llm import Message, build_llm

GITHUB_RE = re.compile(r"^https://github\.com/([^/\s]+)/([^/\s]+?)(?:\.git)?(?:/(?:tree|blob)/([^/]+)(?:/(.*))?)?/?$")
CODE_EXT = {".py", ".ts", ".tsx", ".js", ".jsx", ".md", ".mdx", ".toml", ".yaml", ".yml"}
SKIP_DIRS = {"node_modules", ".git", ".next", "__pycache__", "dist", "build", ".venv", "venv", "data", ".turbo"}
MAX_FILES = 14
MAX_FILE_CHARS = 6000
MAX_TOTAL_CHARS = 48000
RELEVANCE_KEYWORDS = (
    ("rag", 8), ("retriev", 8), ("chunk", 8), ("embed", 7), ("agent", 7), ("rerank", 6),
    ("vector", 6), ("prompt", 5), ("index", 4), ("tool", 4), ("eval", 4), ("router", 4), ("cache", 3),
)


class GuidesError(RuntimeError):
    """A user-presentable failure analyzing a repo."""


@dataclass
class SourceFile:
    path: str
    content: str


class ChecklistItem(BaseModel):
    id: str
    title: str
    detail: str
    section: str


class AnalyzeRequest(BaseModel):
    repo_url: str | None = Field(None, max_length=300)
    checklist: list[ChecklistItem] = Field(min_length=1, max_length=80)


class ItemAssessment(BaseModel):
    status: Literal["done", "partial", "missing"]
    note: str


class AnalyzeResponse(BaseModel):
    target: str
    files_reviewed: list[str]
    items: dict[str, ItemAssessment]
    summary: str
    next_steps: list[str]


class ExplainRequest(BaseModel):
    item: ChecklistItem
    analysis_note: str = Field("", max_length=600)
    question: str = Field("", max_length=2000)
    history: list[dict] = Field(default_factory=list, max_length=20)
    stream: bool = True


# ---------------------------------------------------------------- source collection
def _read(path: Path, label: str) -> SourceFile | None:
    try:
        return SourceFile(label, path.read_text(errors="ignore")[:MAX_FILE_CHARS])
    except OSError:
        return None


def local_files() -> list[SourceFile]:
    """The files that actually implement this app's retrieval/generation, not its CRUD plumbing."""
    root = BASE_DIR  # rag-be/
    wanted = [
        (root.parent / "README.md", "README.md"),
        (root / "app/rag.py", "app/rag.py"),
        (root / "app/ingestion/chunker.py", "app/ingestion/chunker.py"),
        (root / "app/ingestion/sync.py", "app/ingestion/sync.py"),
        (root / "app/registry.py", "app/registry.py"),
        (root / "app/vectorstores/base.py", "app/vectorstores/base.py"),
        (root / "app/embeddings/base.py", "app/embeddings/base.py"),
        (root / "app/llm/base.py", "app/llm/base.py"),
        (root / "app/config.py", "app/config.py"),
    ]
    return [f for f in (_read(p, label) for p, label in wanted) if f]


def _parse_github_url(url: str) -> tuple[str, str, str | None, str]:
    m = GITHUB_RE.match(url.strip())
    if not m:
        raise GuidesError("That doesn't look like a GitHub repo URL (expected https://github.com/<owner>/<repo>).")
    owner, repo, branch, subpath = m.groups()
    return owner, repo, branch, subpath or ""


def _github_get(url: str) -> httpx.Response:
    try:
        r = httpx.get(url, timeout=15, headers={"Accept": "application/vnd.github+json", "User-Agent": "rag-chatbot-guides"})
    except httpx.HTTPError as e:
        raise GuidesError(f"Could not reach GitHub: {e}") from e
    if r.status_code == 404:
        raise GuidesError("Repository not found - is it public?")
    if r.status_code == 403:
        raise GuidesError("GitHub API rate limit hit - try again in a few minutes.")
    if r.is_error:
        raise GuidesError(f"GitHub API error ({r.status_code}).")
    return r


def _score(path: str) -> int:
    name = path.lower()
    s = 100 if name.endswith("readme.md") else 0
    s += sum(w for kw, w in RELEVANCE_KEYWORDS if kw in name)
    s -= name.count("/")  # prefer shallower files
    return s


def github_files(url: str) -> tuple[str, list[SourceFile]]:
    owner, repo, branch, subpath = _parse_github_url(url)
    if not branch:
        branch = _github_get(f"https://api.github.com/repos/{owner}/{repo}").json().get("default_branch", "main")
    tree = _github_get(f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1").json()
    paths = [e["path"] for e in tree.get("tree", []) if e.get("type") == "blob"]
    if subpath:
        prefix = subpath.rstrip("/") + "/"
        paths = [p for p in paths if p == subpath or p.startswith(prefix)]
    paths = [p for p in paths if not any(part in SKIP_DIRS for part in p.split("/")) and Path(p).suffix in CODE_EXT]
    paths.sort(key=_score, reverse=True)

    out: list[SourceFile] = []
    total = 0
    for p in paths:
        if len(out) >= MAX_FILES or total >= MAX_TOTAL_CHARS:
            break
        try:
            r = httpx.get(f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{p}", timeout=15)
        except httpx.HTTPError:
            continue
        if r.is_error:
            continue
        text = r.text[:MAX_FILE_CHARS]
        out.append(SourceFile(p, text))
        total += len(text)
    if not out:
        raise GuidesError("Couldn't find any readable source files in that repo.")
    return f"{owner}/{repo}@{branch}", out


# ---------------------------------------------------------------- analysis
def _parse_json_object(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if not m:
            raise GuidesError("The model didn't return a JSON assessment - try again.")
        return json.loads(m.group(0))


def analyze(settings: Settings, repo_url: str | None, checklist: list[ChecklistItem]) -> AnalyzeResponse:
    if repo_url and repo_url.strip():
        target, files = github_files(repo_url.strip())
    else:
        target, files = "this app (rag-be)", local_files()
        if not files:
            raise GuidesError("Could not read this app's own source files to analyze.")

    bundle = "\n\n".join(f"### {f.path}\n```\n{f.content}\n```" for f in files)
    items_spec = "\n".join(f"- {c.id}: {c.title} — {c.detail}" for c in checklist)
    system = (
        "You are a senior RAG (retrieval-augmented generation) systems reviewer. You are given excerpts of a "
        "codebase and a checklist of RAG best practices. For EVERY checklist item, judge whether the codebase "
        "implements it: \"done\" (clearly implemented), \"partial\" (attempted or partially present), or "
        "\"missing\" (no evidence in the excerpts). Only use what's actually shown; if a practice isn't visible, "
        "mark it missing rather than assuming. Respond with ONLY a JSON object, no prose outside it, shaped exactly as:\n"
        '{"items": {"<item id>": {"status": "done|partial|missing", "note": "<one short sentence, name a file if '
        'done/partial>"}, ...}, "summary": "<2-3 sentence overall assessment of this project\'s RAG maturity>", '
        '"next_steps": ["<3-5 highest-impact missing practices, most impactful first>"]}'
    )
    user = f"## Checklist\n{items_spec}\n\n## Codebase excerpts ({target})\n{bundle}"
    llm = build_llm(settings.model_copy(update={"llm_temperature": 0.1}))
    raw = llm.chat([{"role": "system", "content": system}, {"role": "user", "content": user}])
    data = _parse_json_object(raw)

    raw_items = data.get("items") if isinstance(data, dict) else None
    items: dict[str, ItemAssessment] = {}
    for c in checklist:
        v = (raw_items or {}).get(c.id)
        if isinstance(v, dict) and v.get("status") in ("done", "partial", "missing"):
            items[c.id] = ItemAssessment(status=v["status"], note=str(v.get("note", ""))[:400])
        else:
            items[c.id] = ItemAssessment(status="missing", note="Not assessed.")

    summary = str(data.get("summary", "")).strip()[:1000] if isinstance(data, dict) else ""
    next_steps = [str(x).strip()[:240] for x in (data.get("next_steps") or [])][:6] if isinstance(data, dict) else []
    return AnalyzeResponse(target=target, files_reviewed=[f.path for f in files], items=items, summary=summary, next_steps=next_steps)


def explain_messages(body: ExplainRequest) -> list[Message]:
    system = (
        "You are a pragmatic RAG engineering mentor helping someone improve their own retrieval-augmented "
        "generation project. Explain the checklist item clearly and concretely: what it means, why it matters, "
        "and concrete steps to implement it in a typical Python/FastAPI + vector-store RAG stack. Keep the first "
        "answer under ~180 words unless asked for more detail. Use short paragraphs or a brief numbered list, no headings."
    )
    ctx = f"Checklist item: {body.item.title}\n{body.item.detail}\n(Section: {body.item.section})"
    if body.analysis_note:
        ctx += f"\n\nWhat an automated review found in the user's codebase: {body.analysis_note}"
    messages: list[Message] = [{"role": "system", "content": system}, {"role": "user", "content": ctx}]
    for m in body.history[-8:]:
        role, content = m.get("role"), m.get("content")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": str(content)[:4000]})
    messages.append({"role": "user", "content": body.question.strip() or "Explain this and how to implement it."})
    return messages
