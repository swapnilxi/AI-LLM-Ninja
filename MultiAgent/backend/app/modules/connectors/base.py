"""App connector framework.

A Connector is a catalog entry (GitHub, Slack, MCP, ...). An org installs it as a
`Connection` (credentials encrypted at rest). Connections are attached to agents
and/or projects; their actions become tools named `<connector>_<action>`.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any

from ..net import NetPolicy, safe_request
from ..tools.base import ToolResult

if TYPE_CHECKING:
    from ..context import RunContext

ActionHandler = Callable[[dict[str, Any], dict[str, Any], "RunContext | None"], Awaitable[ToolResult]]


@dataclass
class ConfigField:
    key: str
    label: str
    type: str = "text"  # text | password | url | number | textarea | boolean
    required: bool = False
    secret: bool = False
    placeholder: str = ""
    help: str = ""
    default: Any = None


@dataclass
class Action:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: ActionHandler
    write: bool = False  # mutates external state


@dataclass
class Connector:
    key: str
    name: str
    description: str
    icon: str
    category: str
    fields: list[ConfigField]
    actions: list[Action] = field(default_factory=list)
    docs_url: str = ""
    tester: Callable[[dict[str, Any]], Awaitable[tuple[bool, str]]] | None = None
    dynamic: bool = False  # actions discovered at runtime (MCP)

    async def list_actions(self, cfg: dict[str, Any], conn_id: str = "") -> list[Action]:
        return self.actions

    async def test(self, cfg: dict[str, Any]) -> tuple[bool, str]:
        if self.tester is None:
            return True, "Saved (no live test available)"
        try:
            return await self.tester(cfg)
        except Exception as exc:
            return False, f"Connection failed: {exc}"

    def describe(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "name": self.name,
            "description": self.description,
            "icon": self.icon,
            "category": self.category,
            "docs_url": self.docs_url,
            "dynamic": self.dynamic,
            "fields": [asdict(f) for f in self.fields],
            "actions": [{"name": a.name, "description": a.description, "write": a.write} for a in self.actions],
        }


READ_ONLY_FIELD = ConfigField(
    "read_only", "Read-only mode", "boolean", help="Hide actions that create or change data in the app", default=False
)


async def api_call(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
    json: Any = None,
    data: Any = None,
    policy: NetPolicy | None = None,
) -> tuple[int, Any]:
    r = await safe_request(method, url, headers=headers, params=params, json=json, data=data, timeout=30, policy=policy, max_bytes=3 * 1024 * 1024)
    try:
        body: Any = r.json()
    except Exception:
        body = r.text
    return r.status_code, body


def fmt(status: int, body: Any, limit: int = 12000) -> ToolResult:
    import json as _json

    text = body if isinstance(body, str) else _json.dumps(body, indent=2, ensure_ascii=False)
    return ToolResult(f"HTTP {status}\n{text[:limit]}", is_error=status >= 400)
