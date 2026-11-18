"""Sandboxed Jinja templating used by workflows and custom HTTP tools."""
from __future__ import annotations

import json
from typing import Any

from jinja2 import ChainableUndefined
from jinja2.exceptions import SecurityError, TemplateError
from jinja2.sandbox import ImmutableSandboxedEnvironment

_env = ImmutableSandboxedEnvironment(autoescape=False, undefined=ChainableUndefined, trim_blocks=False)
_env.filters["tojson"] = lambda v: json.dumps(v, ensure_ascii=False, default=str)
_env.filters["truncate_chars"] = lambda v, n=1000: str(v)[: int(n)]

MAX_TEMPLATE = 50_000


class TemplateRenderError(Exception):
    pass


def render(template: str, context: dict[str, Any]) -> str:
    if not template:
        return ""
    if len(template) > MAX_TEMPLATE:
        raise TemplateRenderError("Template too large")
    try:
        out = _env.from_string(template).render(**context)
    except (TemplateError, SecurityError) as exc:
        raise TemplateRenderError(f"Template error: {exc}") from exc
    return out[:500_000]


def evaluate(expression: str, context: dict[str, Any]) -> Any:
    if not expression.strip():
        return True
    try:
        return _env.compile_expression(expression, undefined_to_none=True)(**context)
    except (TemplateError, SecurityError) as exc:
        raise TemplateRenderError(f"Condition error: {exc}") from exc
