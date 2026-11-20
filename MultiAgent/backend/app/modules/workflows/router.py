"""Workflows API (library resource)."""


from fastapi import Depends, HTTPException

from app.core.common import check_agent_ids, check_team_ids
from app.core.crud import crud_router
from app.core.deps import OrgContext, get_org_ctx
from app.modules.workflows.engine import NODE_TYPES, validate_graph
from app.modules.workflows.models import Workflow
from app.modules.workflows.schemas import WorkflowIn, WorkflowOut


async def prep_workflow(session, ctx, data, owner):
    graph = data.get("graph") or {"nodes": [], "edges": []}
    nodes = graph.get("nodes") or []
    if len(nodes) > 60:
        raise HTTPException(400, "Workflows are limited to 60 nodes")
    agent_ids = [(n.get("data") or {}).get("agent_id") for n in nodes if n.get("type") == "agent"]
    team_ids = [(n.get("data") or {}).get("team_id") for n in nodes if n.get("type") == "team"]
    await check_agent_ids(session, ctx, [i for i in agent_ids if i])
    await check_team_ids(session, ctx, [i for i in team_ids if i])
    for n in nodes:
        if n.get("type") not in NODE_TYPES:
            raise HTTPException(400, f"Unknown node type '{n.get('type')}'")
    data["graph"] = {"nodes": nodes, "edges": graph.get("edges") or [], "viewport": graph.get("viewport")}
    return data


workflows_router = crud_router("/workflows", Workflow, WorkflowIn, WorkflowOut, prep_workflow, "workflow")


@workflows_router.post("/validate")
async def validate_workflow(body: WorkflowIn, ctx: OrgContext = Depends(get_org_ctx)):
    errors = validate_graph(body.graph)
    return {"valid": not errors, "errors": errors}

ROUTERS = [workflows_router]
