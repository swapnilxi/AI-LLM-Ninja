"""HTTP endpoints for agent management (mounted by app.main with its registry, auth dependency and profile lookup)."""
from __future__ import annotations

from typing import Callable

from fastapi import APIRouter, Depends, HTTPException

from ..registry import AGENT_ROLES, Registry
from .prompts import MAX_RESEARCHERS
from .schemas import AgentIn, AgentPatch, agent_view
from .team import DEFAULT_TEAM, ROLE_INFO, ensure_default_agents


def build_router(registry: Registry, auth: list[Depends], profile_or_404: Callable[[str], dict]) -> APIRouter:
    router = APIRouter()

    def check_role(role: str) -> None:
        if role not in AGENT_ROLES:
            raise HTTPException(422, f"Unknown role '{role}'. Choose from: {', '.join(AGENT_ROLES)}")

    def agent_or_404(agent_id: str) -> dict:
        a = registry.get_agent(agent_id)
        if a is None:
            raise HTTPException(404, "Agent not found")
        return a

    @router.get("/api/agents", dependencies=auth)
    def list_agents(profile_id: str = ""):
        """All agents, or only one business's (`?profile_id=acme`). `businesses` feeds the filter dropdown."""
        if profile_id:
            profile_or_404(profile_id)
        profiles = [p for p in registry.list_profiles() if p["status"] == "active"]
        names = {p["id"]: p["name"] for p in profiles}
        for p in profiles:  # businesses discovered since startup get their starter team (once)
            ensure_default_agents(registry, p["id"])
        all_agents = registry.list_agents()
        counts: dict[str, int] = {}
        for a in all_agents:
            counts[a["profile_id"]] = counts.get(a["profile_id"], 0) + 1
        return {
            "agents": [agent_view(a, names) for a in all_agents if not profile_id or a["profile_id"] == profile_id],
            "businesses": [{"id": p["id"], "name": p["name"], "is_common": p["is_common"], "agents": counts.get(p["id"], 0)} for p in profiles],
            "roles": ROLE_INFO, "max_researchers": MAX_RESEARCHERS,
        }

    @router.post("/api/agents", dependencies=auth, status_code=201)
    def create_agent(body: AgentIn):
        name = profile_or_404(body.profile_id)["name"]
        check_role(body.role)
        a = registry.add_agent(body.profile_id, body.name.strip(), body.role, description=body.description.strip(),
                               instructions=body.instructions.strip(), focus=body.focus.strip(), model=body.model.strip(), enabled=body.enabled)
        return agent_view(a, {body.profile_id: name})

    @router.patch("/api/agents/{agent_id}", dependencies=auth)
    def patch_agent(agent_id: str, body: AgentPatch):
        a = agent_or_404(agent_id)
        fields = body.model_dump(exclude_none=True)
        if "role" in fields:
            check_role(fields["role"])
        for k in ("name", "description", "instructions", "focus", "model"):
            if k in fields:
                fields[k] = fields[k].strip()
        if fields.get("name") == "":
            raise HTTPException(422, "Name cannot be empty")
        return agent_view(registry.update_agent(agent_id, **fields), {a["profile_id"]: profile_or_404(a["profile_id"])["name"]})

    @router.delete("/api/agents/{agent_id}", dependencies=auth)
    def delete_agent(agent_id: str):
        agent_or_404(agent_id)
        registry.delete_agent(agent_id)
        return {"deleted": agent_id}

    @router.post("/api/profiles/{profile_id}/agents/defaults", dependencies=auth)
    def add_default_agents(profile_id: str):
        """(Re)adds the starter team's missing roles to a business."""
        name = profile_or_404(profile_id)["name"]
        have = {a["role"] for a in registry.list_agents(profile_id)}
        added = [registry.add_agent(profile_id, n, r, description=d, instructions=i, focus=f)
                 for n, r, d, i, f in DEFAULT_TEAM if r not in have]
        registry.mark_agents_seeded(profile_id)
        return {"added": [agent_view(a, {profile_id: name}) for a in added]}

    return router
