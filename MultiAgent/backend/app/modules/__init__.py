"""Feature modules: one vertical slice per product area.

Each module owns everything for its feature:

    app/modules/<name>/
        models.py    SQLAlchemy tables
        schemas.py   request/response shapes
        router.py    HTTP endpoints (exports `router`, or `ROUTERS` when it has several)
        service.py   business logic (plus feature-specific helpers, e.g. scheduler/nl_parser.py)

Shared plumbing lives in `app/core` (config, db, auth deps, security, rate limiting, generic CRUD) and the agent
runtime kernel (LLM providers, tool framework, run context, safe networking) lives in `app/engine`.

Tenancy model
-------------
Organization (tenant) ─┬─ Membership ── User
                       ├─ Project ── (Conversations, Runs, Schedules, project Documents/Memory)
                       ├─ ProviderCredential / Secret / ApiKey / Connection (app connectors)
                       └─ Library resources (Agent, Skill, Tool, Team, Workflow)

Library resources are *project independent*: ``org_id`` is the owning tenant, or NULL for the global
(platform-wide) library that every org can use. A run always executes inside (org, project).
"""
from __future__ import annotations

from collections.abc import Iterator
from importlib import import_module

from fastapi import APIRouter

# Order matters only for OpenAPI grouping.
MODULES: tuple[str, ...] = (
    "auth",
    "orgs",
    "projects",
    "agents",
    "skills",
    "tools",
    "teams",
    "workflows",
    "connectors",
    "knowledge",
    "training",
    "chat",
    "runs",
    "scheduler",
    "tasks",
    "discover",
    "dashboard",
    "transfer",
)


def _optional(path: str):
    try:
        return import_module(path)
    except ModuleNotFoundError as exc:
        if exc.name != path:
            raise
        return None


def load_models() -> None:
    """Import every module's models so their tables are registered on Base.metadata."""
    for name in MODULES:
        _optional(f"app.modules.{name}.models")


def routers() -> Iterator[APIRouter]:
    for name in MODULES:
        mod = _optional(f"app.modules.{name}.router")
        if mod is not None:
            yield from getattr(mod, "ROUTERS", None) or [mod.router]
