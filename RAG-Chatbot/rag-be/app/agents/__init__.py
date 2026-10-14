"""Multi-agent answering and agent management.

    prompts.py        role prompts + limits
    team.py           role descriptions, starter team, which agents run for a business
    orchestrator.py   the planner -> researchers -> critic -> synthesizer pipeline (streams events)
    schemas.py        request bodies / JSON view
    routes.py         /api/agents endpoints (build_router)
"""
from .orchestrator import multi_agent_events
from .prompts import MAX_RESEARCHERS
from .routes import build_router
from .team import DEFAULT_TEAM, ROLE_INFO, ensure_default_agents, team_for

__all__ = ["DEFAULT_TEAM", "MAX_RESEARCHERS", "ROLE_INFO", "build_router", "ensure_default_agents", "multi_agent_events", "team_for"]
