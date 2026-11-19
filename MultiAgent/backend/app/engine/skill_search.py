"""Find skills (installed, curated, skills.sh registry) and load one on demand.

The registry is skills.sh, the open skills directory behind `npx skills find`. We call its public search API through the
SSRF-safe client (never npx). Loading a skill fetches its SKILL.md from GitHub as *instructions only*: nothing is executed.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..deps import visible
from ..models import Skill
from . import hub
from .knowledge import tokenize
from .net import BlockedURL, NetPolicy, safe_request
from .skill_install import InstallError, Source, fetch_skill, fuzzy_candidates, list_skills, parse_skill_md

log = logging.getLogger("agentforge.skill_search")

REGISTRY_URL = "https://skills.sh/api/search"
_SEARCH_TTL, _PATH_TTL = 600, 900
_search_cache: dict[tuple[str, int], tuple[float, list[dict[str, Any]]]] = {}
_path_cache: dict[str, tuple[float, list[dict[str, str]]]] = {}


def _prune(cache: dict, limit: int = 200) -> None:
    if len(cache) > limit:
        for k in sorted(cache, key=lambda k: cache[k][0])[: len(cache) - limit + 20]:
            cache.pop(k, None)


async def search_registry(query: str, limit: int = 8, policy: NetPolicy | None = None) -> list[dict[str, Any]]:
    """Top skills for a query, most-installed first: [{source, skill, name, installs}]. Raises InstallError if unreachable."""
    query = " ".join((query or "").split())[:100]
    if len(query) < 2:
        return []
    limit = max(1, min(limit, 20))
    key = (query.lower(), limit)
    hit = _search_cache.get(key)
    if hit and time.time() - hit[0] < _SEARCH_TTL:
        return hit[1]
    try:
        r = await safe_request("GET", REGISTRY_URL, params={"q": query, "limit": limit}, headers={"accept": "application/json"}, max_bytes=1024 * 1024, timeout=15, policy=policy)
    except BlockedURL as exc:
        raise InstallError(f"Blocked: {exc}")
    except Exception as exc:
        raise InstallError(f"Could not reach the skills registry ({type(exc).__name__}).")
    if r.status_code >= 400:
        raise InstallError(f"The skills registry returned HTTP {r.status_code}.")
    try:
        rows = r.json().get("skills") or []
    except Exception:
        raise InstallError("The skills registry returned an unreadable response.")
    out = []
    for row in rows:
        source, skill = str(row.get("source") or ""), str(row.get("skillId") or row.get("name") or "")
        if hub.SOURCE_RE.match(source) and hub.SKILL_NAME_RE.match(skill):  # only well-formed GitHub sources are ever surfaced
            out.append({"source": source, "skill": skill, "name": str(row.get("name") or skill)[:120], "installs": int(row.get("installs") or 0)})
    _search_cache[key] = (time.time(), out)
    _prune(_search_cache)
    return out


async def search_installed(session: AsyncSession, org_id: str, query: str, project_skill_ids: list[str], limit: int = 8) -> list[dict[str, Any]]:
    terms = tokenize(query)[:6]
    if not terms:
        return []
    conds = [Skill.name.ilike(f"%{t}%") for t in terms] + [Skill.description.ilike(f"%{t}%") for t in terms]
    rows = (await session.execute(select(Skill).where(visible(Skill, org_id), or_(*conds)).limit(60))).scalars().all()
    scored = []
    for s in rows:
        hay = f"{s.name} {s.description}".lower()
        scored.append((sum(1 for t in terms if t in hay), s))
    scored.sort(key=lambda x: -x[0])
    return [
        {"id": s.id, "name": s.name, "description": (s.description or "")[:160], "in_project": s.id in set(project_skill_ids)}
        for _, s in scored[:limit]
    ]


def curated(query: str, limit: int = 4) -> list[dict[str, Any]]:
    terms = tokenize(query)[:6]
    return hub.search_packs(terms, limit) if terms else []


async def _skill_paths(src: Source, policy: NetPolicy | None) -> list[dict[str, str]]:
    key = src.label
    hit = _path_cache.get(key)
    if hit and time.time() - hit[0] < _PATH_TTL:
        return hit[1]
    found = await list_skills(src, policy)
    _path_cache[key] = (time.time(), found)
    _prune(_path_cache, 50)
    return found


async def fetch_external(source: str, skill: str, policy: NetPolicy | None = None) -> tuple[str, str, str, str]:
    """Download one skill from GitHub. Returns (name, description, instructions, path). Raises InstallError."""
    if not hub.SOURCE_RE.match(source) or not hub.SKILL_NAME_RE.match(skill):
        raise InstallError("Use the form owner/repo@skill-name (e.g. anthropics/skills@frontend-design).")
    owner, repo = source.split("/", 1)
    src = Source(owner, repo)
    last: InstallError | None = None
    # Most repos keep skills at skills/<name>/SKILL.md. Trying these first avoids a rate-limited GitHub API call.
    for path in (f"skills/{skill}/SKILL.md", f"{skill}/SKILL.md", ".claude/skills/%s/SKILL.md" % skill, "SKILL.md" if repo.lower() == skill.lower() else ""):
        if not path:
            continue
        try:
            text = await fetch_skill(src, path, policy)
            return (*parse_skill_md(text, skill), path)
        except InstallError as exc:
            last = exc
            if not str(exc).startswith("Could not download"):  # blocked / unreachable: do not keep guessing
                raise
    tree = await _skill_paths(src, policy)
    found = [f for f in tree if f["name"].lower() == skill.lower()] or (lambda c: c if len(c) == 1 else [])(fuzzy_candidates(skill, tree))
    if not found:
        raise InstallError(f"No skill named '{skill}' in {source}.") from last
    path = found[0]["path"]
    return (*parse_skill_md(await fetch_skill(src, path, policy), skill), path)
