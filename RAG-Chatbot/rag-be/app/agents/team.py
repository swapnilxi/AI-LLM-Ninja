"""A business's team of agents: role descriptions, the starter team, and who is enabled for a run."""
from __future__ import annotations

from ..rag import RAGContext
from ..registry import Registry
from .prompts import MAX_RESEARCHERS

ROLE_INFO = {
    "planner": "Breaks the question into focused search queries.",
    "researcher": "Retrieves passages and writes notes for its focus area. Several researchers can run.",
    "critic": "Checks the notes for gaps and contradictions before the answer is written.",
    "synthesizer": "Writes the final answer. Without one, the default answering prompt is used.",
}

DEFAULT_TEAM = (
    ("Planner", "planner", "Splits complex questions into focused searches.", "", ""),
    ("Researcher", "researcher", "Finds and summarises the facts relevant to the question.", "", ""),
    ("Fact checker", "critic", "Flags gaps and contradictions in the research.", "", ""),
    ("Answer writer", "synthesizer", "Writes the final, cited answer.", "", ""),
)


def ensure_default_agents(reg: Registry, profile_id: str) -> None:
    """Give a business its starter team once. Deleting agents afterwards is respected (never re-seeded)."""
    if reg.agents_seeded(profile_id):
        return
    if not reg.list_agents(profile_id):
        for name, role, desc, instr, focus in DEFAULT_TEAM:
            reg.add_agent(profile_id, name, role, description=desc, instructions=instr, focus=focus)
    reg.mark_agents_seeded(profile_id)


def team_for(reg: Registry, ctx: RAGContext) -> dict[str, list[dict]]:
    agents = [a for a in reg.list_agents(ctx.profile_id) if a["enabled"]]
    by_role = {r: [a for a in agents if a["role"] == r] for r in ("planner", "researcher", "critic", "synthesizer")}
    by_role["researcher"] = by_role["researcher"][:MAX_RESEARCHERS]
    return by_role
