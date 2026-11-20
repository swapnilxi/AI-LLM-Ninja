"""Teams API (library resource)."""


from fastapi import HTTPException

from app.core.common import check_agent_ids
from app.core.crud import crud_router
from app.modules.teams.models import Team
from app.modules.teams.schemas import TeamIn, TeamOut


async def prep_team(session, ctx, data, owner):
    ids = [m["agent_id"] for m in data.get("members") or []]
    extra = [data.get("manager_agent_id"), (data.get("config") or {}).get("aggregator_agent_id"), (data.get("config") or {}).get("router_agent_id")]
    await check_agent_ids(session, ctx, ids + [i for i in extra if i])
    if data["style"] == "supervisor" and not data.get("manager_agent_id"):
        raise HTTPException(400, "Supervisor teams need a manager agent")
    if not ids:
        raise HTTPException(400, "Add at least one member")
    cfg = data.get("config") or {}
    data["config"] = {
        k: cfg[k] for k in ("max_rounds", "termination_keyword", "aggregator_agent_id", "router_agent_id", "max_concurrency") if cfg.get(k) not in (None, "")
    }
    return data


teams_router = crud_router("/teams", Team, TeamIn, TeamOut, prep_team, "team")

ROUTERS = [teams_router]
