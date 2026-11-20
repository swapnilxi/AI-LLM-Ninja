from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.core.security import decrypt_json
from app.engine.tools.base import RuntimeTool, ToolResult, sanitize_name
from app.modules.connectors.base import Connector
from app.modules.connectors.catalog import STATIC_CONNECTORS
from app.modules.connectors.mcp_connector import MCP
from app.modules.connectors.models import Connection

if TYPE_CHECKING:
    from app.engine.context import RunContext

CONNECTORS: dict[str, Connector] = {c.key: c for c in [*STATIC_CONNECTORS, MCP]}


def connection_config(conn: Connection) -> dict[str, Any]:
    return {**(conn.public_config or {}), **decrypt_json(conn.config_enc)}


async def connection_tools(conn: Connection) -> list[RuntimeTool]:
    connector = CONNECTORS.get(conn.connector_key)
    if not connector or not conn.enabled:
        return []
    cfg = connection_config(conn)
    actions = await connector.list_actions(cfg, conn.id)
    enabled = set(conn.enabled_tools or [])
    tools = []
    for action in actions:
        if enabled and action.name not in enabled:
            continue
        if action.write and cfg.get("read_only"):
            continue

        async def handler(args: dict[str, Any], ctx: "RunContext", _a=action, _cfg=cfg) -> ToolResult:
            return await _a.handler(_cfg, args, ctx)

        tools.append(
            RuntimeTool(
                name=sanitize_name(f"{conn.connector_key}_{action.name}"),
                description=f"[{connector.name}: {conn.name}] {action.description}",
                parameters=action.parameters,
                handler=handler,
                source=f"connector:{conn.connector_key}",
                category="connector",
                untrusted=True,
                display_name=f"{connector.name} · {action.name}",
                meta={"connection_id": conn.id, "write": action.write},
            )
        )
    return tools
