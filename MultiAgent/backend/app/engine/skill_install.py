"""Install skills from an `npx skills add <source>`-style command, WITHOUT running npx.

Executing npx on the server would run arbitrary third-party code. Instead the command is parsed and the
SKILL.md files are downloaded from GitHub (api.github.com / raw.githubusercontent.com only) through the
SSRF-safe HTTP client, then stored as ordinary skills (instructions only: bundled scripts are never run).
"""
from __future__ import annotations

import re
import shlex
from dataclasses import dataclass, field
from urllib.parse import quote, urlparse

from .net import BlockedURL, safe_request

DEFAULT_REPO = "anthropics/skills"  # where a bare name like `pdf` is looked up
MAX_SKILLS_PER_INSTALL = 20
MAX_FILE_BYTES = 200_000
_NAME = r"[A-Za-z0-9_.-]+"
_REPO_RE = re.compile(rf"^({_NAME})/({_NAME})$")
_SKILL_NAME_RE = re.compile(r"^[A-Za-z0-9 _.\-]{1,120}$")
_PACKAGERS = {"skills", "skill", "add-skill", "install", "add", "i", "get"}


class InstallError(Exception):
    """User-facing problem with the command or the source."""


@dataclass
class Source:
    owner: str
    repo: str
    ref: str = "HEAD"
    subpath: str = ""
    names: list[str] = field(default_factory=list)
    raw_path: str = ""  # direct link to one SKILL.md

    @property
    def label(self) -> str:
        return f"{self.owner}/{self.repo}"


def parse_command(command: str) -> Source:
    text = (command or "").strip()
    if not text or len(text) > 500:
        raise InstallError("Enter a command like: npx skills add anthropics/skills --skill pdf")
    try:
        tokens = shlex.split(text)
    except ValueError:
        raise InstallError("Could not parse the command (unbalanced quotes).")
    if tokens and tokens[0] in ("npx", "bunx", "pnpx", "pnpm", "yarn", "npm"):
        tokens = tokens[1:]
        if tokens and tokens[0] in ("dlx", "exec", "x"):
            tokens = tokens[1:]
    names: list[str] = []
    positional: list[str] = []
    it = iter(tokens)
    for tok in it:
        if tok in ("--skill", "-s"):
            for nxt in it:
                if nxt.startswith("-"):
                    break
                names.append(nxt)
                break
        elif tok.startswith("--skill="):
            names.append(tok.split("=", 1)[1])
        elif tok.startswith("-"):
            continue  # -y, --global, --agent … are meaningless here
        else:
            positional.append(tok)
    while positional and (positional[0].split("@")[0] in _PACKAGERS):
        positional.pop(0)
    if not positional:
        raise InstallError("Missing skill source. Example: npx skills add owner/repo --skill name")
    src_tok = positional[0]
    names += positional[1:]

    if src_tok.startswith(("http://", "https://")):
        return _parse_url(src_tok, names)
    # owner/repo@skill  |  owner/repo/sub/path  |  owner/repo  |  bare-name
    if "@" in src_tok and "/" in src_tok:
        src_tok, _, at = src_tok.partition("@")
        names.append(at)
    parts = src_tok.strip("/").split("/")
    if len(parts) == 1:
        owner, repo = DEFAULT_REPO.split("/")
        names.append(parts[0])
        src = Source(owner, repo)
    else:
        src = Source(parts[0], parts[1], subpath="/".join(parts[2:]))
    _check_repo(src)
    src.names = _clean_names(names)
    return src


def _check_repo(src: Source) -> None:
    bad = lambda p: set(p) <= {"."}  # noqa: E731  ("." / ".." path tricks)
    if not _REPO_RE.match(f"{src.owner}/{src.repo}") or bad(src.owner) or bad(src.repo) or ".." in src.subpath.split("/") or ".." in src.raw_path.split("/"):
        raise InstallError("Source must look like owner/repo or a GitHub URL.")


def _clean_names(names: list[str]) -> list[str]:
    out = []
    for n in names:
        n = n.strip()
        if n and n not in out:
            if not _SKILL_NAME_RE.match(n):
                raise InstallError(f"Invalid skill name '{n[:40]}'.")
            out.append(n)
    return out


def _parse_url(url: str, names: list[str]) -> Source:
    u = urlparse(url)
    host, parts = (u.hostname or "").lower(), [p for p in u.path.split("/") if p]
    if host == "raw.githubusercontent.com" and len(parts) >= 4 and parts[-1].lower() == "skill.md":
        owner, repo, ref = parts[0], parts[1], parts[2]
        return Source(owner, repo, ref=ref, raw_path="/".join(parts[3:]), names=_clean_names(names))
    if host in ("github.com", "www.github.com") and len(parts) >= 2:
        owner, repo = parts[0], parts[1].removesuffix(".git")
        ref, sub = "HEAD", ""
        if len(parts) >= 4 and parts[2] in ("tree", "blob"):
            ref, sub = parts[3], "/".join(parts[4:])
        src = Source(owner, repo, ref=ref, subpath=sub, names=_clean_names(names))
        if sub.lower().endswith("skill.md"):
            src.raw_path, src.subpath = sub, ""
        _check_repo(src)
        return src
    raise InstallError("Only GitHub sources are supported (owner/repo or a github.com URL).")


async def _get(url: str, max_bytes: int):
    try:
        r = await safe_request("GET", url, headers={"accept": "application/vnd.github+json, text/plain"}, max_bytes=max_bytes, timeout=20)
    except BlockedURL as exc:
        raise InstallError(f"Blocked: {exc}")
    except Exception as exc:
        raise InstallError(f"Could not reach GitHub: {exc}")
    return r


async def list_skills(src: Source) -> list[dict[str, str]]:
    """Return [{path, name}] for every SKILL.md the command refers to."""
    if src.raw_path:
        return [{"path": src.raw_path, "name": src.raw_path.rsplit("/", 2)[-2] if "/" in src.raw_path else src.repo}]
    url = f"https://api.github.com/repos/{src.owner}/{src.repo}/git/trees/{quote(src.ref, safe='')}?recursive=1"
    r = await _get(url, 8 * 1024 * 1024)
    if r.status_code == 404:
        raise InstallError(f"Repository {src.label} was not found (or is private).")
    if r.status_code in (403, 429):
        raise InstallError("GitHub rate limit reached. Try again in a few minutes.")
    if r.status_code >= 400:
        raise InstallError(f"GitHub returned HTTP {r.status_code}.")
    tree = r.json().get("tree", [])
    found = []
    for node in tree:
        path = str(node.get("path", ""))
        if node.get("type") != "blob" or not path.lower().endswith("skill.md") or (path.lower() != "skill.md" and not path.lower().endswith("/skill.md")):
            continue
        if src.subpath and not (path == src.subpath or path.startswith(src.subpath.rstrip("/") + "/")):
            continue
        if "node_modules/" in path or path.startswith("."):
            continue
        folder = path.rsplit("/", 1)[0] if "/" in path else ""
        found.append({"path": path, "name": folder.rsplit("/", 1)[-1] if folder else src.repo})
    if src.names:
        wanted = {n.lower() for n in src.names}
        picked = [f for f in found if f["name"].lower() in wanted]
        missing = wanted - {f["name"].lower() for f in picked}
        if missing and not picked:
            raise InstallError(f"No skill named {', '.join(sorted(missing))} in {src.label}. Available: {', '.join(sorted({f['name'] for f in found})[:15]) or 'none'}.")
        found = picked
    if not found:
        raise InstallError(f"No SKILL.md found in {src.label}{('/' + src.subpath) if src.subpath else ''}.")
    return sorted(found, key=lambda f: f["path"])[:200]


async def fetch_skill(src: Source, path: str) -> str:
    url = f"https://raw.githubusercontent.com/{src.owner}/{src.repo}/{quote(src.ref, safe='')}/{quote(path)}"
    r = await _get(url, MAX_FILE_BYTES + 1)
    if r.status_code >= 400:
        raise InstallError(f"Could not download {path} (HTTP {r.status_code}).")
    if len(r.content) > MAX_FILE_BYTES or r.truncated:
        raise InstallError(f"{path} is larger than {MAX_FILE_BYTES // 1000} KB.")
    return r.text


def parse_skill_md(text: str, fallback_name: str = "Imported skill") -> tuple[str, str, str]:
    """(name, description, instructions) from a SKILL.md with optional YAML-ish front matter."""
    text = text.strip()
    name, desc, instructions = "", "", text
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", text, flags=re.S)
    if m:
        front, instructions = m.group(1), m.group(2).strip()
        for line in front.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                if k.strip().lower() == "name":
                    name = v.strip().strip("'\"")
                elif k.strip().lower() == "description":
                    desc = v.strip().strip("'\"")
    if not name:
        h = re.search(r"^#\s+(.+)$", instructions, flags=re.M)
        name = h.group(1).strip() if h else fallback_name
    return name, desc, instructions
