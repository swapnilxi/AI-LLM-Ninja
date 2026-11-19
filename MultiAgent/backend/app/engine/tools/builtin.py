"""Built-in tools available to every agent (subject to project policy)."""
from __future__ import annotations

import ast
import asyncio
import io
import json
import logging
import math
import operator
import re
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qs, unquote, urljoin, urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from bs4 import BeautifulSoup
from sqlalchemy import or_, select

from ...config import settings
from ...db import SessionLocal
from ...models import Document, Memory
from .. import knowledge
from ..net import BlockedURL, safe_request, validate_url
from . import productivity, skills_tools
from .base import RuntimeTool, ToolResult, schema

if TYPE_CHECKING:
    from ..context import RunContext

log = logging.getLogger("agentforge.tools")


@dataclass
class BuiltinDef:
    key: str
    display_name: str
    description: str
    parameters: dict[str, Any]
    category: str
    untrusted: bool = False

    def runtime(self) -> RuntimeTool:
        return RuntimeTool(
            name=self.key,
            description=self.description,
            parameters=self.parameters,
            handler=HANDLERS[self.key],
            source="builtin",
            category=self.category,
            untrusted=self.untrusted,
            display_name=self.display_name,
        )


# ============================================================================ web search
async def web_search(args: dict[str, Any], ctx: "RunContext") -> ToolResult:
    if not ctx.web_access:
        return ToolResult("Web access is disabled for this project.", True)
    query = str(args.get("query", "")).strip()[:400]
    if not query:
        return ToolResult("query is required", True)
    n = max(1, min(int(args.get("max_results") or 5), 10))
    secrets = await ctx.secrets()
    pref = (ctx.org.settings.get("web_search_provider") or "auto").lower()
    tavily = secrets.get("TAVILY_API_KEY") or settings.tavily_api_key
    brave = secrets.get("BRAVE_API_KEY") or settings.brave_api_key
    results: list[dict[str, str]] = []
    engine = ""
    try:
        if tavily and pref in ("auto", "tavily"):
            r = await safe_request(
                "POST", "https://api.tavily.com/search", json={"api_key": tavily, "query": query, "max_results": n}, timeout=25
            )
            data = r.json() or {}
            results = [{"title": x.get("title", ""), "url": x.get("url", ""), "snippet": x.get("content", "")} for x in data.get("results", [])]
            engine = "tavily"
        elif brave and pref in ("auto", "brave"):
            r = await safe_request(
                "GET",
                "https://api.search.brave.com/res/v1/web/search",
                params={"q": query, "count": n},
                headers={"X-Subscription-Token": brave, "Accept": "application/json"},
            )
            data = r.json() or {}
            results = [
                {"title": x.get("title", ""), "url": x.get("url", ""), "snippet": re.sub("<[^>]+>", "", x.get("description", ""))}
                for x in (data.get("web") or {}).get("results", [])
            ]
            engine = "brave"
    except Exception as exc:  # fall back to keyless search
        log.warning("search provider failed: %s", exc)
    if not results:
        results, engine = await _duckduckgo(query, n)
    policy = ctx.net_policy()
    if policy.blocked_domains:
        from ..net import host_matches

        results = [r for r in results if not host_matches(urlsplit(r["url"]).hostname or "", policy.blocked_domains)]
    if not results:
        return ToolResult(f"No results found for '{query}'.")
    lines = [f"Search results for: {query} (via {engine})"]
    for i, r in enumerate(results[:n], 1):
        snippet = re.sub(r"\s+", " ", r["snippet"]).strip()[:400]
        lines.append(f"{i}. {r['title'].strip()}\n   {r['url']}\n   {snippet}")
    lines.append("Tip: use browse_webpage on a URL to read the full page.")
    return ToolResult("\n".join(lines), data=results[:n])


async def _duckduckgo(query: str, n: int) -> tuple[list[dict[str, str]], str]:
    try:
        from ddgs import DDGS

        def run() -> list[dict[str, Any]]:
            return DDGS(timeout=15).text(query, max_results=n)

        raw = await asyncio.wait_for(asyncio.to_thread(run), timeout=25)
        res = [{"title": x.get("title", ""), "url": x.get("href", ""), "snippet": x.get("body", "")} for x in raw or []]
        if res:
            return res, "duckduckgo"
    except Exception as exc:
        log.info("ddgs failed (%s), trying HTML endpoint", exc)
    try:
        r = await safe_request("POST", "https://html.duckduckgo.com/html/", data={"q": query}, timeout=20)
        soup = BeautifulSoup(r.text, "html.parser")
        out = []
        for res in soup.select(".result")[: n * 2]:
            a = res.select_one(".result__a")
            if not a:
                continue
            href = a.get("href", "")
            if "uddg=" in href:
                href = unquote(parse_qs(urlsplit(href).query).get("uddg", [href])[0])
            snip = res.select_one(".result__snippet")
            out.append({"title": a.get_text(" ", strip=True), "url": href, "snippet": snip.get_text(" ", strip=True) if snip else ""})
        return out[:n], "duckduckgo-html"
    except Exception as exc:
        log.warning("duckduckgo html failed: %s", exc)
        return [], "none"


# ============================================================================ browser
async def browse_webpage(args: dict[str, Any], ctx: "RunContext") -> ToolResult:
    if not ctx.web_access:
        return ToolResult("Web access is disabled for this project.", True)
    url = str(args.get("url", "")).strip()
    if not re.match(r"^https?://", url):
        url = "https://" + url
    max_chars = max(500, min(int(args.get("max_chars") or 8000), 40000))
    render_js = bool(args.get("render_js")) or bool(ctx.project.settings.get("browser_render_js"))
    note = ""
    policy = ctx.net_policy()
    try:
        if render_js:
            rendered = await _render_with_browser(url, policy)
            if rendered is not None:
                final_url, html = rendered
                title, text = knowledge.html_to_text(html)
                return _page_result(final_url, 200, title, text, html, max_chars, args.get("include_links"), "headless browser")
            note = "(JavaScript rendering unavailable - install Playwright; showing static HTML)\n"
        r = await safe_request("GET", url, policy=policy, headers={"accept": "text/html,application/xhtml+xml,*/*;q=0.8"}, max_bytes=4 * 1024 * 1024)
    except BlockedURL as exc:
        return ToolResult(f"Blocked: {exc}", True)
    except Exception as exc:
        return ToolResult(f"Failed to fetch {url}: {exc}", True)
    ctype = r.headers.get("content-type", "")
    if "pdf" in ctype or r.url.lower().endswith(".pdf"):
        try:
            text = knowledge.extract_text("page.pdf", r.content)
        except Exception as exc:
            return ToolResult(f"Could not read PDF: {exc}", True)
        return ToolResult(f"{note}URL: {r.url}\nStatus: {r.status_code}\nType: PDF\n\n{text[:max_chars]}")
    if "html" in ctype or r.text.lstrip()[:15].lower().startswith(("<!doctype", "<html")):
        title, text = knowledge.html_to_text(r.text)
        res = _page_result(r.url, r.status_code, title, text, r.text, max_chars, args.get("include_links"), "http")
        res.content = note + res.content
        return res
    return ToolResult(f"{note}URL: {r.url}\nStatus: {r.status_code}\nType: {ctype}\n\n{r.text[:max_chars]}")


def _page_result(url: str, status: int, title: str, text: str, html: str, max_chars: int, links: Any, via: str) -> ToolResult:
    body = text[:max_chars] + ("\n…[truncated]" if len(text) > max_chars else "")
    out = f"Title: {title}\nURL: {url}\nStatus: {status}\nFetched via: {via}\n\n{body}"
    if links:
        soup = BeautifulSoup(html, "html.parser")
        seen, items = set(), []
        for a in soup.find_all("a", href=True):
            href = urljoin(url, a["href"])
            if href.startswith("http") and href not in seen:
                seen.add(href)
                items.append(f"- {a.get_text(' ', strip=True)[:80]} → {href}")
            if len(items) >= 40:
                break
        out += "\n\nLinks:\n" + "\n".join(items)
    return ToolResult(out)


async def _render_with_browser(url: str, policy: Any) -> tuple[str, str] | None:
    try:
        from playwright.async_api import async_playwright  # optional dependency
    except ImportError:
        return None
    await validate_url(url, policy)
    checked: dict[str, bool] = {}

    async def guard(route: Any) -> None:
        req_url = route.request.url
        if req_url.startswith(("data:", "blob:")):
            await route.continue_()
            return
        host = urlsplit(req_url).hostname or ""
        if host not in checked:
            try:
                await validate_url(req_url, policy)
                checked[host] = True
            except BlockedURL:
                checked[host] = False
        if checked[host]:
            await route.continue_()
        else:
            await route.abort()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            context = await browser.new_context(accept_downloads=False, java_script_enabled=True)
            await context.route("**/*", guard)
            page = await context.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=25000)
            try:
                await page.wait_for_load_state("networkidle", timeout=6000)
            except Exception:
                pass
            return page.url, await page.content()
        finally:
            await browser.close()


# ============================================================================ http
async def http_request(args: dict[str, Any], ctx: "RunContext") -> ToolResult:
    if not ctx.web_access:
        return ToolResult("Web access is disabled for this project.", True)
    method = str(args.get("method") or "GET").upper()
    if method not in ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"):
        return ToolResult("Unsupported method", True)
    headers = args.get("headers") if isinstance(args.get("headers"), dict) else {}
    headers = {str(k): str(v) for k, v in headers.items() if str(k).lower() not in ("host", "cookie")}
    body = args.get("body")
    kwargs: dict[str, Any] = {"headers": headers, "params": args.get("query") if isinstance(args.get("query"), dict) else None}
    if isinstance(body, (dict, list)):
        kwargs["json"] = body
    elif body:
        kwargs["content"] = str(body)
    try:
        r = await safe_request(method, str(args.get("url", "")), policy=ctx.net_policy(), max_bytes=2 * 1024 * 1024, **kwargs)
    except BlockedURL as exc:
        return ToolResult(f"Blocked: {exc}", True)
    except Exception as exc:
        return ToolResult(f"Request failed: {exc}", True)
    text = r.text
    try:
        text = json.dumps(json.loads(text), indent=2)[:12000]
    except Exception:
        if "html" in r.headers.get("content-type", ""):
            text = knowledge.html_to_text(text)[1]
    return ToolResult(f"HTTP {r.status_code} {r.headers.get('content-type', '')}\n\n{text[:12000]}", is_error=r.status_code >= 400)


# ============================================================================ calculator
_BIN = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod, ast.Pow: operator.pow}
_UN = {ast.UAdd: operator.pos, ast.USub: operator.neg}
_FUNCS: dict[str, Any] = {k: getattr(math, k) for k in (
    "sqrt", "log", "log10", "log2", "exp", "sin", "cos", "tan", "asin", "acos", "atan", "floor", "ceil", "fabs", "radians", "degrees", "hypot")}
_FUNCS.update({"abs": abs, "round": round, "min": min, "max": max})
_CONSTS = {"pi": math.pi, "e": math.e, "tau": math.tau}


def _eval(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.Name) and node.id in _CONSTS:
        return _CONSTS[node.id]
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN:
        left, right = _eval(node.left), _eval(node.right)
        if isinstance(node.op, ast.Pow) and (abs(right) > 1000 or abs(left) > 1e12):
            raise ValueError("exponent too large")
        return _BIN[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UN:
        return _UN[type(node.op)](_eval(node.operand))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _FUNCS and not node.keywords:
        if len(node.args) > 10:
            raise ValueError("too many arguments")
        return _FUNCS[node.func.id](*[_eval(a) for a in node.args])
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "factorial":
        n = _eval(node.args[0])
        if n > 500:
            raise ValueError("factorial argument too large")
        return math.factorial(int(n))
    raise ValueError(f"Unsupported expression element: {type(node).__name__}")


async def calculator(args: dict[str, Any], ctx: "RunContext") -> ToolResult:
    expr = str(args.get("expression", "")).strip()
    if not expr or len(expr) > 500:
        return ToolResult("Provide an expression under 500 characters", True)
    clean = re.sub(r"(?<=\d),(?=\d{3}\b)", "", expr).replace("^", "**").replace("×", "*").replace("÷", "/")
    try:
        value = _eval(ast.parse(clean, mode="eval"))
    except ZeroDivisionError:
        return ToolResult("Division by zero", True)
    except Exception as exc:
        return ToolResult(f"Could not evaluate '{expr}': {exc}", True)
    if isinstance(value, float) and value.is_integer() and abs(value) < 1e15:
        value = int(value)
    return ToolResult(f"{expr} = {value}", data=value)


# ============================================================================ datetime
async def current_datetime(args: dict[str, Any], ctx: "RunContext") -> ToolResult:
    tz_name = str(args.get("timezone") or ctx.project.settings.get("timezone") or "UTC")
    try:
        tz = ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError):
        return ToolResult(f"Unknown timezone '{tz_name}'", True)
    now = datetime.now(tz)
    return ToolResult(f"{now.strftime('%A, %d %B %Y %H:%M:%S')} ({tz_name}) | ISO: {now.isoformat()}")


# ============================================================================ knowledge
def _owners(ctx: "RunContext", scope: str) -> list[tuple[str, str]]:
    owners = knowledge.owners_for(ctx.org.id, ctx.project.id, ctx.current_agent_id)
    if scope in ("org", "project", "agent"):
        owners = [o for o in owners if o[0] == scope]
    return owners


async def knowledge_search(args: dict[str, Any], ctx: "RunContext") -> ToolResult:
    query = str(args.get("query", "")).strip()
    top_k = max(1, min(int(args.get("top_k") or 5), 15))
    async with SessionLocal() as s:
        hits = await knowledge.search(s, ctx.org.id, _owners(ctx, str(args.get("scope") or "all")), query, top_k)
    if not hits:
        return ToolResult(f"No matching passages in the attached documents for '{query}'.")
    parts = [f"Top {len(hits)} passages for '{query}':"]
    for i, h in enumerate(hits, 1):
        parts.append(f"[{i}] {h['title']} ({h['scope']} document, id={h['document_id']}, chunk {h['chunk']})\n{h['text'][:1500]}")
    return ToolResult("\n\n".join(parts), data=hits)


async def read_document(args: dict[str, Any], ctx: "RunContext") -> ToolResult:
    doc_id = str(args.get("document_id", ""))
    offset = max(0, int(args.get("offset") or 0))
    owners = _owners(ctx, "all")
    async with SessionLocal() as s:
        doc = await s.get(Document, doc_id)
    if not doc or doc.org_id != ctx.org.id or (doc.owner_type, doc.owner_id) not in owners:
        return ToolResult("Document not found or not accessible in this context", True)
    chunk = doc.content[offset : offset + 15000]
    more = offset + 15000 < len(doc.content)
    return ToolResult(f"# {doc.title}\n(chars {offset}-{offset + len(chunk)} of {len(doc.content)})\n\n{chunk}" + ("\n…[more: call again with a higher offset]" if more else ""))


# ============================================================================ memory
async def memory(args: dict[str, Any], ctx: "RunContext") -> ToolResult:
    action = str(args.get("action") or "list")
    scope = str(args.get("scope") or "project")
    if scope == "agent" and not ctx.current_agent_id:
        scope = "project"
    filt = [Memory.org_id == ctx.org.id, Memory.scope == scope]
    filt.append(Memory.project_id == ctx.project.id if scope == "project" else Memory.agent_id == ctx.current_agent_id)
    async with SessionLocal() as s:
        if action == "save":
            content = str(args.get("content", "")).strip()
            if not content:
                return ToolResult("content is required to save a memory", True)
            count = len((await s.execute(select(Memory.id).where(*filt))).all())
            if count >= 500:
                return ToolResult("Memory limit reached (500). Delete old memories first.", True)
            m = Memory(
                org_id=ctx.org.id,
                scope=scope,
                project_id=ctx.project.id if scope == "project" else None,
                agent_id=ctx.current_agent_id if scope == "agent" else None,
                key=str(args.get("key") or "")[:120],
                content=content[:4000],
                source="agent",
                run_id=ctx.run_id,
            )
            s.add(m)
            await s.commit()
            return ToolResult(f"Saved {scope} memory {m.id}: {content[:200]}")
        if action == "delete":
            m = await s.get(Memory, str(args.get("memory_id", "")))
            if not m or m.org_id != ctx.org.id:
                return ToolResult("Memory not found", True)
            await s.delete(m)
            await s.commit()
            return ToolResult(f"Deleted memory {m.id}")
        stmt = select(Memory).where(*filt).order_by(Memory.created_at.desc()).limit(50)
        if action == "search" and args.get("query"):
            terms = knowledge.tokenize(str(args["query"]))[:6]
            if terms:
                stmt = stmt.where(or_(*[Memory.content.ilike(f"%{t}%") for t in terms] + [Memory.key.ilike(f"%{t}%") for t in terms]))
        rows = (await s.execute(stmt)).scalars().all()
    if not rows:
        return ToolResult(f"No {scope} memories found.")
    return ToolResult("\n".join(f"- ({m.id}) {('[' + m.key + '] ') if m.key else ''}{m.content}" for m in rows))


HANDLERS = {
    "web_search": web_search,
    "browse_webpage": browse_webpage,
    "http_request": http_request,
    "calculator": calculator,
    "current_datetime": current_datetime,
    "knowledge_search": knowledge_search,
    "read_document": read_document,
    "memory": memory,
    **productivity.HANDLERS,
    **skills_tools.HANDLERS,
}

BUILTINS: dict[str, BuiltinDef] = {
    d.key: d
    for d in [
        BuiltinDef(
            "web_search",
            "Web Search",
            "Search the web for current information. Returns titles, URLs and snippets. Use browse_webpage to read a result in full.",
            schema(
                {
                    "query": {"type": "string", "description": "Search query"},
                    "max_results": {"type": "integer", "description": "Number of results (1-10)", "default": 5},
                },
                ["query"],
            ),
            "web",
            untrusted=True,
        ),
        BuiltinDef(
            "browse_webpage",
            "Browser",
            "Open a web page (like a browser) and return its readable text. Set render_js=true for JavaScript-heavy sites. Optionally list links.",
            schema(
                {
                    "url": {"type": "string", "description": "Absolute URL to open"},
                    "render_js": {"type": "boolean", "description": "Render with a headless browser"},
                    "include_links": {"type": "boolean", "description": "Also return links found on the page"},
                    "max_chars": {"type": "integer", "description": "Max characters of text to return"},
                },
                ["url"],
            ),
            "web",
            untrusted=True,
        ),
        BuiltinDef(
            "http_request",
            "HTTP Request",
            "Call a public HTTP API (GET/POST/PUT/PATCH/DELETE) and return the response body.",
            schema(
                {
                    "method": {"type": "string", "enum": ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"]},
                    "url": {"type": "string"},
                    "headers": {"type": "object"},
                    "query": {"type": "object"},
                    "body": {"description": "JSON object or raw string body"},
                },
                ["url"],
            ),
            "web",
            untrusted=True,
        ),
        BuiltinDef(
            "calculator",
            "Calculator",
            "Evaluate a math expression exactly (supports + - * / ** % sqrt log sin cos pi e factorial ...).",
            schema({"expression": {"type": "string", "description": "e.g. (12.5 * 4) / sqrt(16)"}}, ["expression"]),
            "utility",
        ),
        BuiltinDef(
            "current_datetime",
            "Date & Time",
            "Get the current date and time, optionally in a specific IANA timezone.",
            schema({"timezone": {"type": "string", "description": "e.g. Asia/Kolkata, America/New_York"}}),
            "utility",
        ),
        BuiltinDef(
            "knowledge_search",
            "Knowledge Search",
            "Search documents attached to this agent, the current project and the organization. Returns the most relevant passages with document ids.",
            schema(
                {
                    "query": {"type": "string"},
                    "top_k": {"type": "integer", "description": "Number of passages (1-15)"},
                    "scope": {"type": "string", "enum": ["all", "agent", "project", "org"]},
                },
                ["query"],
            ),
            "knowledge",
        ),
        BuiltinDef(
            "read_document",
            "Read Document",
            "Read the full text of an attached document by id (from knowledge_search results).",
            schema({"document_id": {"type": "string"}, "offset": {"type": "integer", "description": "Character offset"}}, ["document_id"]),
            "knowledge",
        ),
        BuiltinDef(
            "memory",
            "Memory",
            "Long-term memory. action=save stores a durable fact; list/search recalls; delete removes by memory_id. "
            "scope=project (shared by all agents in this project) or agent (your private memory across projects).",
            schema(
                {
                    "action": {"type": "string", "enum": ["save", "list", "search", "delete"]},
                    "content": {"type": "string", "description": "Fact to remember (for save)"},
                    "key": {"type": "string", "description": "Optional short label"},
                    "query": {"type": "string", "description": "Search text (for search)"},
                    "scope": {"type": "string", "enum": ["project", "agent"]},
                    "memory_id": {"type": "string", "description": "Memory id (for delete)"},
                },
                ["action"],
            ),
            "memory",
        ),
        BuiltinDef(
            "create_tasks",
            "Create Tasks",
            "Turn text into tracked to-dos for this project (text to task). Use ONLY when the user asks you to track, remember or list action items - never unprompted. "
            "Put each separate action in its own item; add `context` with the background someone needs to do it.",
            schema(
                {
                    "tasks": {
                        "type": "array",
                        "description": "Tasks to create",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string", "description": "Imperative, <= 12 words"},
                                "notes": {"type": "string"},
                                "priority": {"type": "string", "enum": ["low", "normal", "high"]},
                                "due": {"type": "string", "description": "YYYY-MM-DD or a phrase like 'by friday'"},
                                "context": {"type": "string", "description": "Background needed to do this task"},
                            },
                            "required": ["title"],
                        },
                    },
                    "context": {"type": "string", "description": "Background shared by every task in this call"},
                },
                ["tasks"],
            ),
            "productivity",
        ),
        BuiltinDef(
            "list_tasks",
            "List Tasks",
            "List this project's to-dos. status: open (default, not done), todo, doing, done or all.",
            schema({"status": {"type": "string", "enum": ["open", "todo", "doing", "done", "all"]}, "limit": {"type": "integer"}}),
            "productivity",
        ),
        BuiltinDef(
            "update_task",
            "Update Task",
            "Change a to-do by id (from list_tasks / create_tasks): set status todo|doing|done, or edit title, notes, priority, due date.",
            schema(
                {
                    "task_id": {"type": "string"},
                    "status": {"type": "string", "enum": ["todo", "doing", "done"]},
                    "title": {"type": "string"},
                    "notes": {"type": "string"},
                    "priority": {"type": "string", "enum": ["low", "normal", "high"]},
                    "due": {"type": "string"},
                },
                ["task_id"],
            ),
            "productivity",
        ),
        BuiltinDef(
            "schedule_task",
            "Schedule Task",
            "Create a RECURRING automation that runs `task` as this agent on a schedule. Use only when the user explicitly asks for something to run repeatedly "
            "(e.g. 'every weekday at 9am'); confirm the schedule back to them. One-time reminders are not supported.",
            schema(
                {
                    "when": {"type": "string", "description": "Recurring schedule in plain English, e.g. 'every weekday at 9am', 'every 2 hours', 'monthly on the 1st'"},
                    "task": {"type": "string", "description": "What the agent should do on every run"},
                    "name": {"type": "string", "description": "Short name for the automation"},
                    "timezone": {"type": "string", "description": "IANA timezone, e.g. Asia/Kolkata (defaults to the project timezone or UTC)"},
                },
                ["when", "task"],
            ),
            "productivity",
        ),
        BuiltinDef(
            "find_skills",
            "Find Skills",
            "Search for a skill that helps with the current task: skills already installed, the curated catalog and the public skills.sh registry (most-installed first). "
            "Call this when the task needs specialised expertise you lack or the user asks 'is there a skill for X'. Then call use_skill with the best match.",
            schema({"query": {"type": "string", "description": "What you need help with, e.g. 'react performance' or 'pdf forms'"}, "limit": {"type": "integer", "description": "Max registry results (1-15)"}}, ["query"]),
            "skills",
        ),
        BuiltinDef(
            "use_skill",
            "Use Skill",
            "Load a skill's instructions into this conversation and apply them to the task. `skill` is an installed skill's id or name, or a registry ref 'owner/repo@skill-name' from find_skills. "
            "Loaded for this run only; nothing is installed.",
            schema({"skill": {"type": "string", "description": "Installed skill id/name, or owner/repo@skill-name"}}, ["skill"]),
            "skills",
        ),
    ]
}
