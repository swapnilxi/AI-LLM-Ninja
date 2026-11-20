"""Tools API (library resource)."""


from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base import new_id
from app.core.common import check_agent_ids
from app.core.crud import crud_router
from app.core.db import get_session
from app.core.deps import OrgContext, get_project, get_visible, require_role
from app.engine.context import OrgSnap, ProjectSnap, RunContext
from app.engine.tools.builtin import BUILTINS
from app.engine.tools.registry import runtime_for
from app.modules.tools.models import Tool
from app.modules.tools.schemas import ToolIn, ToolOut, ToolTest


async def prep_tool(session, ctx, data, owner):
    cfg = data.get("config") or {}
    if data["kind"] == "http":
        url = str(cfg.get("url", ""))
        if not url.startswith(("https://", "http://")):
            raise HTTPException(400, "HTTP tools need config.url starting with http(s)://")
        cfg["method"] = str(cfg.get("method") or "GET").upper()
        if cfg["method"] not in ("GET", "POST", "PUT", "PATCH", "DELETE"):
            raise HTTPException(400, "Unsupported HTTP method")
        if not isinstance(cfg.get("headers") or {}, dict) or not isinstance(cfg.get("query") or {}, dict):
            raise HTTPException(400, "headers and query must be objects")
    elif data["kind"] == "agent":
        await check_agent_ids(session, ctx, [cfg.get("agent_id", "")])
        if not data["parameters"].get("properties"):
            data["parameters"] = {"type": "object", "properties": {"task": {"type": "string", "description": "Task for the agent"}}, "required": ["task"]}
    if data["name"] in BUILTINS:
        raise HTTPException(400, "That name is reserved for a built-in tool")
    data["config"] = cfg
    return data


tools_router = crud_router("/tools", Tool, ToolIn, ToolOut, prep_tool, "tool")


@tools_router.post("/{tool_id}/test")
async def test_tool(tool_id: str, body: ToolTest, ctx: OrgContext = Depends(require_role("member")), session: AsyncSession = Depends(get_session)):
    tool = await get_visible(session, Tool, tool_id, ctx.org_id)
    project = await get_project(session, body.project_id, ctx.org_id)
    rt = runtime_for(tool)
    if rt is None:
        raise HTTPException(400, "Tool cannot be executed")
    rctx = RunContext(run_id=new_id("test"), org=OrgSnap.of(ctx.org), project=ProjectSnap.of(project), user_id=ctx.user.id, trigger="test")
    from app.engine.tools.base import validate_args

    if err := validate_args(rt.parameters, body.arguments):
        return {"ok": False, "output": err}
    if rt.category == "web" and not rctx.web_access:
        return {"ok": False, "output": "Web access is disabled for this project"}
    res = await rt.handler(body.arguments, rctx)
    return {"ok": not res.is_error, "output": res.content[:20000]}

ROUTERS = [tools_router]
