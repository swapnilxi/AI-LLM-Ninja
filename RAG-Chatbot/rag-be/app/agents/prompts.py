"""Prompts and limits for the agent roles."""
from __future__ import annotations

MAX_SUBQUERIES = 3
MAX_RESEARCHERS = 4

PLANNER_PROMPT = (
    f"You are a query planner for a document search system. Split the user's question into at most {MAX_SUBQUERIES} "
    "short, self-contained search queries that together cover it (one query is fine for a simple question). "
    "Reply with ONLY a JSON array of strings."
)
RESEARCHER_PROMPT = (
    "You are a research agent. Read the numbered passages and write concise bullet-point notes of the facts that help "
    "answer the question, citing passage numbers like [2]. Use only the passages. If nothing is relevant, reply "
    "exactly: NO RELEVANT FACTS."
)
CRITIC_PROMPT = (
    "You are a reviewer. Given a question and research notes, list in at most 4 short bullets any gaps, "
    "contradictions or weak evidence the final answer should be careful about. If the notes look solid, reply "
    "exactly: NO ISSUES."
)
