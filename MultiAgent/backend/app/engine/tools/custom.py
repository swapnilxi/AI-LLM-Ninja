"""User-defined tools: HTTP API tools and agent-as-tool."""
from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

from ...db import SessionLocal
from ...models import Agent, Tool
from ..net import BlockedURL, safe_request
from ..templating import TemplateRenderError, render
from .base import RuntimeTool, ToolResult, sanitize_name, schema

if TYPE_CHECKING:
    from ..context import RunContext


def _extract_path(data: Any, path: str) -> Any:
    for part in [p for p in path.split(".") if p]:
        if isinstance(data, list) and part.isdigit():
            data = data[int(part)] if int(part) < len(data) else None
        elif isinstance(data, dict):
            data = data.get(part)
        else:
            return None
    return data


def http_tool(tool: Tool) -> RuntimeTool:
    cfg = dict(tool.config or {})

    async def handler(args: dict[str, Any], ctx: "RunContext") -> ToolResult:
        secrets = await ctx.secrets()
        base_ctx = {
            "secrets": secrets,
            "vars": ctx.project.variables,
            "project": {"id": ctx.project.id, "name": ctx.project.name},
            "org": {"id": ctx.org.id, "name": ctx.org.name},
        }
        try:
            url = render(cfg.get("url", ""), {**base_ctx, "args": {k: quote(str(v), safe="") for k, v in args.items()}})
            tctx = {**base_ctx, "args": args}
            headers = {k: render(str(v), tctx) for k, v in (cfg.get("headers") or {}).items()}
            query = {k: render(str(v), tctx) for k, v in (cfg.get("query") or {}).items()}
            query = {k: v for k, v in query.items() if v != ""}
            body_t = cfg.get("body_template") or ""
            body = render(body_t, tctx) if body_t else None
        except TemplateRenderError as exc:
            return ToolResult(str(exc), True)
        kwargs: dict[str, Any] = {"headers": headers, "params": query or None}
        if body:
            try:
                kwargs["json"] = json.loads(body)
            except json.JSONDecodeError:
                kwargs["content"] = body
        try:
            r = await safe_request(
                cfg.get("method", "GET"),
                url,
                timeout=float(cfg.get("timeout") or 30),
                policy=ctx.net_policy(),
                max_bytes=2 * 1024 * 1024,
                **kwargs,
            )
        except BlockedURL as exc:
            return ToolResult(f"Blocked: {exc}", True)
        except Exception as exc:
            return ToolResult(f"Request failed: {exc}", True)
        text = r.text
        try:
            data = json.loads(text)
            if cfg.get("response_path"):
                data = _extract_path(data, cfg["response_path"])
            text = json.dumps(data, indent=2, ensure_ascii=False)
        except Exception:
            pass
        limit = int(cfg.get("max_chars") or 12000)
        # never echo secrets back to the model
        for v in secrets.values():
            if v and len(v) >= 6:
                text = text.replace(v, "***")
        return ToolResult(f"HTTP {r.status_code}\n{text[:limit]}", is_error=r.status_code >= 400)

    return RuntimeTool(
        name=sanitize_name(tool.name),
        description=tool.description or tool.display_name or tool.name,
        parameters=tool.parameters or schema({}),
        handler=handler,
        source="http",
        category=tool.category or "custom",
        untrusted=True,
        display_name=tool.display_name or tool.name,
        meta={"tool_id": tool.id},
    )


def agent_tool(tool: Tool) -> RuntimeTool:
    target_id = (tool.config or {}).get("agent_id", "")

    async def handler(args: dict[str, Any], ctx: "RunContext") -> ToolResult:
        from ...config import settings
        from ..runner import run_agent

        if ctx.depth >= settings.max_agent_depth:
            return ToolResult("Maximum agent nesting depth reached", True)
        async with SessionLocal() as s:
            agent = await s.get(Agent, target_id)
        if not agent or (agent.org_id and agent.org_id != ctx.org.id):
            return ToolResult("Target agent not found", True)
        task = str(args.get("task") or args.get("input") or json.dumps(args))
        res = await run_agent(ctx.child(agent.id), agent, task)
        return ToolResult(res.text)

    return RuntimeTool(
        name=sanitize_name(tool.name),
        description=tool.description or f"Ask another agent to perform a task",
        parameters=tool.parameters or schema({"task": {"type": "string", "description": "Task for the agent"}}, ["task"]),
        handler=handler,
        source="agent",
        category="agent",
        display_name=tool.display_name or tool.name,
        meta={"tool_id": tool.id, "agent_id": target_id},
    )
