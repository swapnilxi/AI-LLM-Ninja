"""Multi-agent answering. Each business (profile) owns a small team of agents that run in a fixed pipeline:

    planner      splits the question into up to 3 focused search queries
    researcher   (0..4) retrieves passages for those queries and writes notes in its own focus area
    critic       reads the notes, flags gaps / contradictions
    synthesizer  writes the final, streamed answer from the passages + notes

Every step is scoped by the same `RAGContext` as the single-agent pipeline, so an agent can only ever see the
passages of its own business (plus Common, when allowed). Helper agents (planner / researcher / critic) degrade
gracefully: if one fails, the run carries on without it. Only the synthesizer's failure aborts the answer.
"""
from __future__ import annotations

import json
import re
from typing import Iterator

from ..config import Settings
from ..llm import Message, build_llm
from ..rag import RAGContext, clean_history, format_context, graph_expand, retrieve, source_payload, system_prompt
from ..registry import Registry
from ..vectorstores import Hit
from .prompts import CRITIC_PROMPT, MAX_SUBQUERIES, PLANNER_PROMPT, RESEARCHER_PROMPT
from .team import team_for


def _json_list(text: str) -> list[str]:
    m = re.search(r"\[.*\]", text, re.S)
    try:
        data = json.loads(m.group(0)) if m else []
    except ValueError:
        return []
    return [x.strip() for x in data if isinstance(x, str) and x.strip()]


def _llm_for(settings: Settings, agent: dict):
    s = settings.model_copy(update={"llm_model": agent["model"]}) if agent["model"] else settings
    return build_llm(s)


def _persona(agent: dict, base: str) -> str:
    extra = agent["instructions"].strip()
    return f"{base}\n\nAdditional instructions for you ({agent['name']}):\n{extra}" if extra else base


def _merge(hit_lists: list[list[Hit]], limit: int) -> list[Hit]:
    seen: dict[tuple[str, str], Hit] = {}
    for hits in hit_lists:
        for h in hits:
            key = (h.document_id, h.text)
            if key not in seen or h.score > seen[key].score:
                seen[key] = h
    return sorted(seen.values(), key=lambda h: -h.score)[:limit]


def _event(agent: dict, status: str, detail: str = "") -> dict:
    return {"type": "agent", "agent_id": agent["id"], "name": agent["name"], "role": agent["role"],
            "status": status, "detail": detail}


def multi_agent_events(settings: Settings, reg: Registry, query: str, history: list[Message], ctx: RAGContext,
                       graph: bool | None = None) -> Iterator[dict]:
    """Same event protocol as `rag.answer_events` plus {"type": "agent", ...} progress events."""
    team = team_for(reg, ctx)
    hist = clean_history(history, settings.history_turns)
    guarded = lambda a, fn: _run_helper(reg, a, fn)  # noqa: E731

    # 1. planner
    queries = [query]
    if team["planner"]:
        a = team["planner"][0]
        yield _event(a, "running")
        out, err = guarded(a, lambda: _llm_for(settings, a).chat(
            [{"role": "system", "content": _persona(a, PLANNER_PROMPT)}, *hist, {"role": "user", "content": query}]))
        planned = _json_list(out)[:MAX_SUBQUERIES] if out else []
        queries = planned or [query]
        yield _event(a, "error" if err else "done", err or " | ".join(queries))

    # 2. researchers (one retrieval + one note per researcher; with none, a plain retrieval)
    hit_lists: list[list[Hit]] = []
    notes: list[tuple[str, str]] = []
    researchers = team["researcher"]
    if not researchers:
        hit_lists.append([h for q in queries for h in retrieve(settings, q, ctx)])
    for a in researchers:
        yield _event(a, "running")
        focus = f" {a['focus'].strip()}" if a["focus"].strip() else ""
        mine = [h for q in queries for h in retrieve(settings, q + focus, ctx)]
        hit_lists.append(mine)
        if not mine:
            reg.record_agent_run(a["id"])
            yield _event(a, "done", "no passages found")
            continue
        out, err = guarded(a, lambda: _llm_for(settings, a).chat([
            {"role": "system", "content": _persona(a, RESEARCHER_PROMPT)},
            {"role": "user", "content": f"<documents>\n{format_context(mine)}\n</documents>\n\nQuestion: {query}"}]))
        if out and "NO RELEVANT FACTS" not in out.upper():
            notes.append((a["name"], out.strip()))
        yield _event(a, "error" if err else "done", err or f"{len(mine)} passages")

    hits = _merge(hit_lists, max(settings.top_k * 2, settings.top_k))
    entities: list[str] = []
    use_graph = settings.graph_rag if graph is None else graph
    if use_graph:
        hits, entities = graph_expand(settings, build_llm(settings), query, hits, ctx)
    yield {"type": "sources", "sources": source_payload(hits, ctx), "search_query": " | ".join(queries), "profile_id": ctx.profile_id,
           "graph": {"enabled": use_graph, "entities": entities}}

    # 3. critic
    review = ""
    if team["critic"] and notes:
        a = team["critic"][0]
        yield _event(a, "running")
        joined = "\n\n".join(f"{n}:\n{t}" for n, t in notes)
        out, err = guarded(a, lambda: _llm_for(settings, a).chat([
            {"role": "system", "content": _persona(a, CRITIC_PROMPT)},
            {"role": "user", "content": f"Question: {query}\n\nResearch notes:\n{joined}"}]))
        if out and "NO ISSUES" not in out.upper():
            review = out.strip()
        yield _event(a, "error" if err else "done", err or ("issues flagged" if review else "no issues"))

    # 4. synthesizer (streams the answer)
    syn = team["synthesizer"][0] if team["synthesizer"] else None
    system = system_prompt(settings, ctx)
    if syn and syn["instructions"].strip():
        system += f"\n\n## Instructions for the answer writer ({syn['name']})\n{syn['instructions'].strip()}"
    if notes:
        system += "\n\n## Research notes (from helper agents; verify against the passages)\n" + "\n\n".join(f"{n}:\n{t}" for n, t in notes)
    if review:
        system += "\n\n## Reviewer remarks\n" + review
    context = format_context(hits) if hits else "(no relevant context was found)"
    messages: list[Message] = [
        {"role": "system", "content": system}, *hist,
        {"role": "user", "content": f"<documents>\n{context}\n</documents>\n\nQuestion: {query}"},
    ]
    llm = _llm_for(settings, syn) if syn else build_llm(settings)
    if syn:
        yield _event(syn, "running")
    try:
        for token in llm.stream(messages):
            yield {"type": "token", "text": token}
    except Exception as e:
        if syn:
            reg.record_agent_run(syn["id"], str(e))
            yield _event(syn, "error", str(e))
        raise
    if syn:
        reg.record_agent_run(syn["id"])
        yield _event(syn, "done")
    yield {"type": "done"}


def _run_helper(reg: Registry, agent: dict, fn) -> tuple[str, str]:
    """Run one helper LLM call; never raises. Returns (output, error)."""
    try:
        out = fn()
    except Exception as e:  # a helper failing must not take the answer down
        reg.record_agent_run(agent["id"], str(e))
        return "", str(e)[:200]
    reg.record_agent_run(agent["id"])
    return out or "", ""
