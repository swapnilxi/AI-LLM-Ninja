"""Built-in app connectors."""
from __future__ import annotations

import asyncio
import json
import smtplib
import ssl
from email.message import EmailMessage
from typing import Any
from urllib.parse import urljoin, urlsplit

from ..net import BlockedURL, validate_url
from ..tools.base import ToolResult, schema
from .base import READ_ONLY_FIELD, Action, ConfigField, Connector, api_call, fmt


def _policy(ctx):
    return ctx.net_policy() if ctx else None


# ============================================================================ GitHub
def _gh_headers(cfg: dict[str, Any]) -> dict[str, str]:
    h = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if cfg.get("token"):
        h["Authorization"] = f"Bearer {cfg['token']}"
    return h


def _gh(cfg: dict[str, Any]) -> str:
    return (cfg.get("api_base") or "https://api.github.com").rstrip("/")


async def _gh_search_repos(cfg, a, ctx):
    s, b = await api_call("GET", f"{_gh(cfg)}/search/repositories", headers=_gh_headers(cfg), params={"q": a["query"], "per_page": min(int(a.get("limit") or 5), 20)}, policy=_policy(ctx))
    if s >= 400:
        return fmt(s, b)
    items = [{"name": i["full_name"], "url": i["html_url"], "stars": i["stargazers_count"], "description": i.get("description")} for i in b.get("items", [])]
    return ToolResult(json.dumps(items, indent=2), data=items)


async def _gh_search_issues(cfg, a, ctx):
    s, b = await api_call("GET", f"{_gh(cfg)}/search/issues", headers=_gh_headers(cfg), params={"q": a["query"], "per_page": min(int(a.get("limit") or 5), 20)}, policy=_policy(ctx))
    if s >= 400:
        return fmt(s, b)
    items = [{"title": i["title"], "url": i["html_url"], "state": i["state"], "user": i["user"]["login"], "body": (i.get("body") or "")[:400]} for i in b.get("items", [])]
    return ToolResult(json.dumps(items, indent=2), data=items)


async def _gh_get_file(cfg, a, ctx):
    params = {"ref": a["ref"]} if a.get("ref") else None
    h = {**_gh_headers(cfg), "Accept": "application/vnd.github.raw+json"}
    s, b = await api_call("GET", f"{_gh(cfg)}/repos/{a['owner']}/{a['repo']}/contents/{a['path'].lstrip('/')}", headers=h, params=params, policy=_policy(ctx))
    return fmt(s, b, 20000)


async def _gh_list_prs(cfg, a, ctx):
    s, b = await api_call("GET", f"{_gh(cfg)}/repos/{a['owner']}/{a['repo']}/pulls", headers=_gh_headers(cfg), params={"state": a.get("state") or "open", "per_page": 20}, policy=_policy(ctx))
    if s >= 400:
        return fmt(s, b)
    return ToolResult(json.dumps([{"number": p["number"], "title": p["title"], "url": p["html_url"], "user": p["user"]["login"]} for p in b], indent=2))


async def _gh_create_issue(cfg, a, ctx):
    s, b = await api_call("POST", f"{_gh(cfg)}/repos/{a['owner']}/{a['repo']}/issues", headers=_gh_headers(cfg), json={"title": a["title"], "body": a.get("body", "")}, policy=_policy(ctx))
    if s >= 400:
        return fmt(s, b)
    return ToolResult(f"Created issue #{b['number']}: {b['html_url']}")


async def _gh_test(cfg):
    s, b = await api_call("GET", f"{_gh(cfg)}/user" if cfg.get("token") else f"{_gh(cfg)}/rate_limit", headers=_gh_headers(cfg))
    if s >= 400:
        return False, f"GitHub returned {s}"
    return True, f"Connected as {b.get('login')}" if isinstance(b, dict) and b.get("login") else "Connected (anonymous)"


GITHUB = Connector(
    key="github",
    name="GitHub",
    description="Search repositories & issues, read files, list PRs and open issues.",
    icon="github",
    category="Developer",
    docs_url="https://github.com/settings/tokens",
    fields=[
        ConfigField("token", "Personal access token", "password", secret=True, help="Fine-grained token; optional for public data"),
        ConfigField("api_base", "API base URL", "url", placeholder="https://api.github.com", help="For GitHub Enterprise"),
        READ_ONLY_FIELD,
    ],
    actions=[
        Action("search_repositories", "Search GitHub repositories", schema({"query": {"type": "string"}, "limit": {"type": "integer"}}, ["query"]), _gh_search_repos),
        Action("search_issues", "Search GitHub issues and pull requests (GitHub search syntax)", schema({"query": {"type": "string"}, "limit": {"type": "integer"}}, ["query"]), _gh_search_issues),
        Action("get_file", "Read a file from a repository", schema({"owner": {"type": "string"}, "repo": {"type": "string"}, "path": {"type": "string"}, "ref": {"type": "string"}}, ["owner", "repo", "path"]), _gh_get_file),
        Action("list_pull_requests", "List pull requests of a repository", schema({"owner": {"type": "string"}, "repo": {"type": "string"}, "state": {"type": "string", "enum": ["open", "closed", "all"]}}, ["owner", "repo"]), _gh_list_prs),
        Action("create_issue", "Create an issue in a repository", schema({"owner": {"type": "string"}, "repo": {"type": "string"}, "title": {"type": "string"}, "body": {"type": "string"}}, ["owner", "repo", "title"]), _gh_create_issue, write=True),
    ],
    tester=_gh_test,
)


# ============================================================================ Slack
def _slack_h(cfg):
    return {"Authorization": f"Bearer {cfg.get('bot_token', '')}", "Content-Type": "application/json; charset=utf-8"}


async def _slack_post(cfg, a, ctx):
    channel = a.get("channel") or cfg.get("default_channel")
    if not channel:
        return ToolResult("channel is required", True)
    s, b = await api_call("POST", "https://slack.com/api/chat.postMessage", headers=_slack_h(cfg), json={"channel": channel, "text": a["text"][:39000]}, policy=_policy(ctx))
    ok = isinstance(b, dict) and b.get("ok")
    return ToolResult("Message posted" if ok else f"Slack error: {b}", not ok)


async def _slack_channels(cfg, a, ctx):
    s, b = await api_call("GET", "https://slack.com/api/conversations.list", headers=_slack_h(cfg), params={"limit": min(int(a.get("limit") or 50), 200), "exclude_archived": "true"}, policy=_policy(ctx))
    if not (isinstance(b, dict) and b.get("ok")):
        return ToolResult(f"Slack error: {b}", True)
    return ToolResult("\n".join(f"#{c['name']} ({c['id']})" for c in b.get("channels", [])))


async def _slack_history(cfg, a, ctx):
    s, b = await api_call("GET", "https://slack.com/api/conversations.history", headers=_slack_h(cfg), params={"channel": a["channel"], "limit": min(int(a.get("limit") or 20), 100)}, policy=_policy(ctx))
    if not (isinstance(b, dict) and b.get("ok")):
        return ToolResult(f"Slack error: {b}", True)
    return ToolResult("\n".join(f"[{m.get('user', 'bot')}] {m.get('text', '')}" for m in b.get("messages", [])))


async def _slack_test(cfg):
    s, b = await api_call("POST", "https://slack.com/api/auth.test", headers=_slack_h(cfg))
    if isinstance(b, dict) and b.get("ok"):
        return True, f"Connected to {b.get('team')} as {b.get('user')}"
    return False, f"Slack error: {b.get('error') if isinstance(b, dict) else b}"


SLACK = Connector(
    key="slack",
    name="Slack",
    description="Post messages, list channels and read channel history.",
    icon="slack",
    category="Communication",
    docs_url="https://api.slack.com/apps",
    fields=[
        ConfigField("bot_token", "Bot token (xoxb-…)", "password", required=True, secret=True),
        ConfigField("default_channel", "Default channel ID", placeholder="C0123456"),
        READ_ONLY_FIELD,
    ],
    actions=[
        Action("post_message", "Post a message to a Slack channel", schema({"channel": {"type": "string", "description": "Channel ID"}, "text": {"type": "string"}}, ["text"]), _slack_post, write=True),
        Action("list_channels", "List Slack channels", schema({"limit": {"type": "integer"}}), _slack_channels),
        Action("channel_history", "Read recent messages from a channel", schema({"channel": {"type": "string"}, "limit": {"type": "integer"}}, ["channel"]), _slack_history),
    ],
    tester=_slack_test,
)


# ============================================================================ Notion
def _notion_h(cfg):
    return {"Authorization": f"Bearer {cfg.get('token', '')}", "Notion-Version": "2022-06-28", "Content-Type": "application/json"}


def _rich(rt: list[dict[str, Any]]) -> str:
    return "".join(t.get("plain_text", "") for t in rt or [])


async def _notion_search(cfg, a, ctx):
    s, b = await api_call("POST", "https://api.notion.com/v1/search", headers=_notion_h(cfg), json={"query": a["query"], "page_size": 10}, policy=_policy(ctx))
    if s >= 400:
        return fmt(s, b)
    out = []
    for r in b.get("results", []):
        title = ""
        for p in (r.get("properties") or {}).values():
            if p.get("type") == "title":
                title = _rich(p.get("title"))
        out.append({"id": r["id"], "type": r["object"], "title": title or _rich(r.get("title", [])), "url": r.get("url")})
    return ToolResult(json.dumps(out, indent=2), data=out)


async def _notion_get_page(cfg, a, ctx):
    s, b = await api_call("GET", f"https://api.notion.com/v1/blocks/{a['page_id']}/children", headers=_notion_h(cfg), params={"page_size": 100}, policy=_policy(ctx))
    if s >= 400:
        return fmt(s, b)
    lines = []
    for blk in b.get("results", []):
        data = blk.get(blk.get("type", ""), {})
        if isinstance(data, dict) and "rich_text" in data:
            lines.append(_rich(data["rich_text"]))
    return ToolResult("\n".join(lines) or "(page has no text blocks)")


async def _notion_create(cfg, a, ctx):
    paras = [p for p in str(a.get("content", "")).split("\n\n") if p.strip()][:90]
    payload = {
        "parent": {"page_id": a["parent_page_id"]},
        "properties": {"title": {"title": [{"text": {"content": a["title"][:200]}}]}},
        "children": [{"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"text": {"content": p[:1900]}}]}} for p in paras],
    }
    s, b = await api_call("POST", "https://api.notion.com/v1/pages", headers=_notion_h(cfg), json=payload, policy=_policy(ctx))
    return ToolResult(f"Created page {b.get('url')}") if s < 400 else fmt(s, b)


async def _notion_test(cfg):
    s, b = await api_call("GET", "https://api.notion.com/v1/users/me", headers=_notion_h(cfg))
    return (s < 400, f"Connected as {b.get('name')}" if s < 400 else f"Notion returned {s}")


NOTION = Connector(
    key="notion",
    name="Notion",
    description="Search your workspace, read pages and create new pages.",
    icon="notion",
    category="Knowledge",
    docs_url="https://www.notion.so/my-integrations",
    fields=[ConfigField("token", "Integration token", "password", required=True, secret=True), READ_ONLY_FIELD],
    actions=[
        Action("search", "Search Notion pages and databases", schema({"query": {"type": "string"}}, ["query"]), _notion_search),
        Action("get_page", "Read the text content of a Notion page", schema({"page_id": {"type": "string"}}, ["page_id"]), _notion_get_page),
        Action("create_page", "Create a Notion page under a parent page", schema({"parent_page_id": {"type": "string"}, "title": {"type": "string"}, "content": {"type": "string"}}, ["parent_page_id", "title"]), _notion_create, write=True),
    ],
    tester=_notion_test,
)


# ============================================================================ Generic REST API
def _rest_url(cfg: dict[str, Any], path: str) -> str:
    base = cfg.get("base_url", "").rstrip("/") + "/"
    path = str(path or "").lstrip("/")
    if "://" in path or path.startswith("//"):
        raise BlockedURL("path must be relative to the configured base URL")
    url = urljoin(base, path)
    if urlsplit(url).netloc != urlsplit(base).netloc:
        raise BlockedURL("path escapes the configured base URL")
    return url


def _rest_headers(cfg):
    h: dict[str, str] = {}
    if cfg.get("default_headers"):
        try:
            h.update({str(k): str(v) for k, v in json.loads(cfg["default_headers"]).items()})
        except Exception:
            pass
    if cfg.get("auth_value"):
        h[cfg.get("auth_header") or "Authorization"] = cfg["auth_value"]
    return h


async def _rest_request(cfg, a, ctx):
    method = str(a.get("method") or "GET").upper()
    if method not in ("GET", "POST", "PUT", "PATCH", "DELETE"):
        return ToolResult("Unsupported method", True)
    if cfg.get("read_only") and method != "GET":
        return ToolResult("This connection is read-only", True)
    try:
        url = _rest_url(cfg, a.get("path", ""))
        s, b = await api_call(method, url, headers=_rest_headers(cfg), params=a.get("query") if isinstance(a.get("query"), dict) else None, json=a.get("body") if method != "GET" else None, policy=_policy(ctx))
    except BlockedURL as exc:
        return ToolResult(f"Blocked: {exc}", True)
    return fmt(s, b)


async def _rest_test(cfg):
    await validate_url(cfg.get("base_url", ""))
    s, _ = await api_call("GET", _rest_url(cfg, cfg.get("health_path") or ""), headers=_rest_headers(cfg))
    return s < 500, f"Base URL responded with HTTP {s}"


REST = Connector(
    key="rest_api",
    name="REST API",
    description="Connect any HTTP/JSON API with a base URL and auth header. Agents can call relative paths only.",
    icon="globe",
    category="Developer",
    fields=[
        ConfigField("base_url", "Base URL", "url", required=True, placeholder="https://api.example.com/v1"),
        ConfigField("auth_header", "Auth header name", placeholder="Authorization"),
        ConfigField("auth_value", "Auth header value", "password", secret=True, placeholder="Bearer sk-..."),
        ConfigField("default_headers", "Extra headers (JSON)", "textarea", placeholder='{"Accept": "application/json"}'),
        ConfigField("health_path", "Test path", placeholder="/health"),
        READ_ONLY_FIELD,
    ],
    actions=[
        Action(
            "request",
            "Call the connected REST API. `path` is relative to the base URL.",
            schema({"method": {"type": "string", "enum": ["GET", "POST", "PUT", "PATCH", "DELETE"]}, "path": {"type": "string"}, "query": {"type": "object"}, "body": {"type": "object"}}, ["path"]),
            _rest_request,
        )
    ],
    tester=_rest_test,
)


# ============================================================================ Telegram
async def _tg_send(cfg, a, ctx):
    chat = a.get("chat_id") or cfg.get("default_chat_id")
    s, b = await api_call("POST", f"https://api.telegram.org/bot{cfg.get('bot_token', '')}/sendMessage", json={"chat_id": chat, "text": a["text"][:4000]}, policy=_policy(ctx))
    ok = isinstance(b, dict) and b.get("ok")
    return ToolResult("Message sent" if ok else f"Telegram error: {b}", not ok)


async def _tg_test(cfg):
    s, b = await api_call("GET", f"https://api.telegram.org/bot{cfg.get('bot_token', '')}/getMe")
    ok = isinstance(b, dict) and b.get("ok")
    return ok, f"Connected as @{b['result']['username']}" if ok else "Invalid bot token"


TELEGRAM = Connector(
    key="telegram",
    name="Telegram",
    description="Send messages from a Telegram bot.",
    icon="send",
    category="Communication",
    docs_url="https://core.telegram.org/bots#how-do-i-create-a-bot",
    fields=[ConfigField("bot_token", "Bot token", "password", required=True, secret=True), ConfigField("default_chat_id", "Default chat ID")],
    actions=[Action("send_message", "Send a Telegram message", schema({"chat_id": {"type": "string"}, "text": {"type": "string"}}, ["text"]), _tg_send, write=True)],
    tester=_tg_test,
)


# ============================================================================ Discord webhook
async def _dc_send(cfg, a, ctx):
    s, b = await api_call("POST", cfg.get("webhook_url", ""), json={"content": a["content"][:1990]}, policy=_policy(ctx))
    return ToolResult("Message sent" if s < 300 else f"Discord error {s}: {b}", s >= 300)


async def _dc_test(cfg):
    s, b = await api_call("GET", cfg.get("webhook_url", ""))
    return s < 300, f"Webhook '{b.get('name')}' is valid" if s < 300 and isinstance(b, dict) else f"Discord returned {s}"


DISCORD = Connector(
    key="discord",
    name="Discord",
    description="Post messages to a Discord channel via webhook.",
    icon="message-circle",
    category="Communication",
    fields=[ConfigField("webhook_url", "Webhook URL", "password", required=True, secret=True)],
    actions=[Action("send_message", "Post a message to Discord", schema({"content": {"type": "string"}}, ["content"]), _dc_send, write=True)],
    tester=_dc_test,
)


# ============================================================================ Email (SMTP)
async def _smtp_send(cfg, a, ctx):
    host, port = cfg.get("host", ""), int(cfg.get("port") or 587)
    try:
        await validate_url(f"https://{host}:443/")
    except BlockedURL as exc:
        return ToolResult(f"Blocked: {exc}", True)
    to = [x.strip() for x in str(a["to"]).split(",") if x.strip()][:20]
    msg = EmailMessage()
    msg["From"] = cfg.get("from_address") or cfg.get("username")
    msg["To"] = ", ".join(to)
    msg["Subject"] = str(a["subject"])[:300]
    msg.set_content(str(a.get("body", ""))[:100000])

    def send() -> None:
        context = ssl.create_default_context()
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=20, context=context) as s:
                s.login(cfg.get("username", ""), cfg.get("password", ""))
                s.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=20) as s:
                s.starttls(context=context)
                s.login(cfg.get("username", ""), cfg.get("password", ""))
                s.send_message(msg)

    try:
        await asyncio.to_thread(send)
    except Exception as exc:
        return ToolResult(f"Email failed: {exc}", True)
    return ToolResult(f"Email sent to {', '.join(to)}")


async def _smtp_test(cfg):
    host, port = cfg.get("host", ""), int(cfg.get("port") or 587)
    await validate_url(f"https://{host}:443/")

    def check() -> None:
        context = ssl.create_default_context()
        cls = smtplib.SMTP_SSL if port == 465 else smtplib.SMTP
        kwargs = {"context": context} if port == 465 else {}
        with cls(host, port, timeout=15, **kwargs) as s:
            if port != 465:
                s.starttls(context=context)
            s.login(cfg.get("username", ""), cfg.get("password", ""))

    await asyncio.to_thread(check)
    return True, "SMTP login succeeded"


EMAIL = Connector(
    key="email",
    name="Email (SMTP)",
    description="Send emails through any SMTP server (Gmail, Outlook, SES, ...).",
    icon="mail",
    category="Communication",
    fields=[
        ConfigField("host", "SMTP host", required=True, placeholder="smtp.gmail.com"),
        ConfigField("port", "Port", "number", default=587),
        ConfigField("username", "Username", required=True),
        ConfigField("password", "Password / app password", "password", required=True, secret=True),
        ConfigField("from_address", "From address"),
    ],
    actions=[Action("send_email", "Send an email", schema({"to": {"type": "string", "description": "Comma separated"}, "subject": {"type": "string"}, "body": {"type": "string"}}, ["to", "subject", "body"]), _smtp_send, write=True)],
    tester=_smtp_test,
)


# ============================================================================ Linear
async def _linear(cfg, query: str, variables: dict[str, Any], ctx=None):
    return await api_call("POST", "https://api.linear.app/graphql", headers={"Authorization": cfg.get("api_key", ""), "Content-Type": "application/json"}, json={"query": query, "variables": variables}, policy=_policy(ctx))


async def _linear_search(cfg, a, ctx):
    s, b = await _linear(cfg, "query($q:String!){ searchIssues(term:$q, first:10){ nodes{ identifier title url state{name} } } }", {"q": a["query"]}, ctx)
    return fmt(s, b)


async def _linear_create(cfg, a, ctx):
    q = "mutation($t:String!,$title:String!,$d:String){ issueCreate(input:{teamId:$t,title:$title,description:$d}){ success issue{ identifier url } } }"
    s, b = await _linear(cfg, q, {"t": a["team_id"], "title": a["title"], "d": a.get("description", "")}, ctx)
    return fmt(s, b)


async def _linear_test(cfg):
    s, b = await _linear(cfg, "{ viewer { name } }", {})
    ok = s < 400 and isinstance(b, dict) and not b.get("errors")
    return ok, f"Connected as {b['data']['viewer']['name']}" if ok else f"Linear error: {b}"


LINEAR = Connector(
    key="linear",
    name="Linear",
    description="Search and create Linear issues.",
    icon="square-kanban",
    category="Project management",
    fields=[ConfigField("api_key", "API key", "password", required=True, secret=True), READ_ONLY_FIELD],
    actions=[
        Action("search_issues", "Search Linear issues", schema({"query": {"type": "string"}}, ["query"]), _linear_search),
        Action("create_issue", "Create a Linear issue", schema({"team_id": {"type": "string"}, "title": {"type": "string"}, "description": {"type": "string"}}, ["team_id", "title"]), _linear_create, write=True),
    ],
    tester=_linear_test,
)


# ============================================================================ Jira
def _jira(cfg):
    import base64

    tok = base64.b64encode(f"{cfg.get('email', '')}:{cfg.get('api_token', '')}".encode()).decode()
    return cfg.get("base_url", "").rstrip("/"), {"Authorization": f"Basic {tok}", "Accept": "application/json"}


async def _jira_search(cfg, a, ctx):
    base, h = _jira(cfg)
    s, b = await api_call("GET", f"{base}/rest/api/3/search/jql", headers=h, params={"jql": a["jql"], "maxResults": 15, "fields": "summary,status,assignee"}, policy=_policy(ctx))
    if s >= 400:
        return fmt(s, b)
    rows = [{"key": i["key"], "summary": i["fields"].get("summary"), "status": (i["fields"].get("status") or {}).get("name")} for i in b.get("issues", [])]
    return ToolResult(json.dumps(rows, indent=2), data=rows)


async def _jira_create(cfg, a, ctx):
    base, h = _jira(cfg)
    payload = {
        "fields": {
            "project": {"key": a["project_key"]},
            "summary": a["summary"],
            "issuetype": {"name": a.get("issue_type") or "Task"},
            "description": {"type": "doc", "version": 1, "content": [{"type": "paragraph", "content": [{"type": "text", "text": a.get("description") or a["summary"]}]}]},
        }
    }
    s, b = await api_call("POST", f"{base}/rest/api/3/issue", headers={**h, "Content-Type": "application/json"}, json=payload, policy=_policy(ctx))
    return ToolResult(f"Created {b.get('key')}") if s < 400 else fmt(s, b)


async def _jira_test(cfg):
    base, h = _jira(cfg)
    s, b = await api_call("GET", f"{base}/rest/api/3/myself", headers=h)
    return s < 400, f"Connected as {b.get('displayName')}" if s < 400 else f"Jira returned {s}"


JIRA = Connector(
    key="jira",
    name="Jira",
    description="Search issues with JQL and create Jira issues.",
    icon="ticket",
    category="Project management",
    fields=[
        ConfigField("base_url", "Site URL", "url", required=True, placeholder="https://your-team.atlassian.net"),
        ConfigField("email", "Account email", required=True),
        ConfigField("api_token", "API token", "password", required=True, secret=True),
        READ_ONLY_FIELD,
    ],
    actions=[
        Action("search_issues", "Search Jira issues with JQL", schema({"jql": {"type": "string"}}, ["jql"]), _jira_search),
        Action("create_issue", "Create a Jira issue", schema({"project_key": {"type": "string"}, "summary": {"type": "string"}, "description": {"type": "string"}, "issue_type": {"type": "string"}}, ["project_key", "summary"]), _jira_create, write=True),
    ],
    tester=_jira_test,
)

STATIC_CONNECTORS = [GITHUB, SLACK, NOTION, LINEAR, JIRA, REST, TELEGRAM, DISCORD, EMAIL]
