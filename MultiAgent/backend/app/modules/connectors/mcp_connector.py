"""Remote MCP server connector (Streamable HTTP). Tools are discovered dynamically."""
from __future__ import annotations

import hashlib
import json
import logging
import time
from contextlib import asynccontextmanager
from typing import Any

from ..net import validate_url
from ..tools.base import ToolResult, sanitize_name
from .base import Action, ConfigField, Connector

log = logging.getLogger("agentforge.mcp")
_CACHE: dict[str, tuple[float, list[dict[str, Any]]]] = {}
_TTL = 300


@asynccontextmanager
async def _session(cfg: dict[str, Any]):
    from mcp import ClientSession
    from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client

    url = cfg.get("url", "")
    await validate_url(url)  # SSRF guard before connecting
    headers: dict[str, str] = {}
    if cfg.get("auth_token"):
        headers["Authorization"] = f"Bearer {cfg['auth_token']}"
    if cfg.get("headers"):
        try:
            headers.update({str(k): str(v) for k, v in json.loads(cfg["headers"]).items()})
        except Exception:
            pass
    client = create_mcp_http_client(headers=headers)
    async with client:
        async with streamable_http_client(url, http_client=client, max_sse_event_size=8 * 1024 * 1024) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session


def _schema_of(tool: Any) -> dict[str, Any]:
    sch = getattr(tool, "input_schema", None) or getattr(tool, "inputSchema", None)
    if not isinstance(sch, dict) or sch.get("type") != "object":
        return {"type": "object", "properties": {}}
    return sch


def _exc_message(exc: BaseException) -> str:
    """Unwrap ExceptionGroups (anyio task groups) into a readable message."""
    while hasattr(exc, "exceptions") and getattr(exc, "exceptions"):
        exc = exc.exceptions[0]
    return f"{type(exc).__name__}: {exc}"[:500]


def _key(cfg: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest()


async def _list_tools(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    k = _key(cfg)
    hit = _CACHE.get(k)
    if hit and time.time() - hit[0] < _TTL:
        return hit[1]
    async with _session(cfg) as session:
        result = await session.list_tools()
    tools = [
        {
            "name": t.name,
            "description": (t.description or t.name)[:2000],
            "parameters": _schema_of(t),
        }
        for t in result.tools
    ]
    _CACHE[k] = (time.time(), tools)
    return tools


def _result_text(result: Any) -> tuple[str, bool]:
    parts = []
    for c in getattr(result, "content", None) or []:
        if getattr(c, "type", "") == "text":
            parts.append(c.text)
        elif getattr(c, "type", "") == "resource":
            res = getattr(c, "resource", None)
            parts.append(getattr(res, "text", "") or f"[resource {getattr(res, 'uri', '')}]")
        else:
            parts.append(f"[{getattr(c, 'type', 'content')}]")
    structured = getattr(result, "structured_content", None) or getattr(result, "structuredContent", None)
    if not parts and structured is not None:
        parts.append(json.dumps(structured, indent=2))
    is_err = bool(getattr(result, "is_error", False) or getattr(result, "isError", False))
    return "\n".join(parts) or "(empty result)", is_err


class MCPConnector(Connector):
    async def list_actions(self, cfg: dict[str, Any], conn_id: str = "") -> list[Action]:
        try:
            tools = await _list_tools(cfg)
        except Exception as exc:
            log.warning("MCP list_tools failed: %s", exc)
            return []
        actions = []
        for t in tools:
            remote_name = t["name"]

            async def handler(c: dict[str, Any], args: dict[str, Any], ctx: Any, _name: str = remote_name) -> ToolResult:
                try:
                    async with _session(c) as session:
                        result = await session.call_tool(_name, args)
                except Exception as exc:
                    return ToolResult(f"MCP call failed: {_exc_message(exc)}", True)
                text, is_err = _result_text(result)
                return ToolResult(text, is_err)

            actions.append(Action(sanitize_name(remote_name)[:40], t["description"], t["parameters"], handler))
        return actions


async def _mcp_test(cfg: dict[str, Any]) -> tuple[bool, str]:
    _CACHE.pop(_key(cfg), None)
    try:
        tools = await _list_tools(cfg)
    except Exception as exc:
        return False, f"MCP connection failed: {_exc_message(exc)}"
    return True, f"Connected - {len(tools)} tool(s): {', '.join(t['name'] for t in tools[:12])}"


MCP = MCPConnector(
    key="mcp",
    name="MCP Server",
    description="Connect any remote Model Context Protocol server (Streamable HTTP). Its tools become available to agents.",
    icon="plug",
    category="Developer",
    docs_url="https://modelcontextprotocol.io",
    fields=[
        ConfigField("url", "Server URL", "url", required=True, placeholder="https://mcp.example.com/mcp"),
        ConfigField("auth_token", "Bearer token", "password", secret=True),
        ConfigField("headers", "Extra headers (JSON)", "textarea", secret=True, placeholder='{"X-Api-Key": "..."}'),
    ],
    tester=_mcp_test,
    dynamic=True,
)
