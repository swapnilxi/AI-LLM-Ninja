"""The RAG pipeline: (optional rewrite) -> embed query -> profile-scoped retrieve -> (optional graph) -> prompt -> stream answer."""
from __future__ import annotations

from typing import Iterator

from ..config import Settings
from ..llm import Message, build_llm
from ..vectorstores import Hit
from .context import RAGContext
from .formatting import format_context, source_payload
from .graph import graph_expand
from .prompts import REWRITE_PROMPT, UNTRUSTED_NOTICE
from .retrieval import retrieve


def clean_history(history: list[Message], turns: int) -> list[Message]:
    msgs = [m for m in history if m.get("role") in ("user", "assistant") and m.get("content")]
    return msgs[-2 * turns :] if turns else []


def system_prompt(settings: Settings, ctx: RAGContext) -> str:
    parts = [settings.system_prompt.strip(), UNTRUSTED_NOTICE]
    if ctx.common_instructions:
        parts.append("## Common instructions\n" + ctx.common_instructions)
    if ctx.profile_instructions:
        parts.append(f"## Instructions for the profile \"{ctx.profile_name or ctx.profile_id}\"\n" + ctx.profile_instructions)
    return "\n\n".join(parts)


def build_messages(settings: Settings, query: str, hits: list[Hit], history: list[Message], ctx: RAGContext) -> list[Message]:
    context = format_context(hits) if hits else "(no relevant context was found)"
    return [
        {"role": "system", "content": system_prompt(settings, ctx)},
        *clean_history(history, settings.history_turns),
        {"role": "user", "content": f"<documents>\n{context}\n</documents>\n\nQuestion: {query}"},
    ]


def answer_events(settings: Settings, query: str, history: list[Message], ctx: RAGContext, graph: bool | None = None) -> Iterator[dict]:
    """Yields {"type": "sources"|"token"|"done", ...}. Errors propagate as exceptions."""
    llm = build_llm(settings)
    search_query = query
    hist = clean_history(history, settings.history_turns)
    if settings.query_rewrite and hist:
        search_query = llm.chat([{"role": "system", "content": REWRITE_PROMPT}, *hist, {"role": "user", "content": query}]).strip() or query
    hits = retrieve(settings, search_query, ctx)
    entities: list[str] = []
    use_graph = settings.graph_rag if graph is None else graph
    if use_graph:
        hits, entities = graph_expand(settings, llm, search_query, hits, ctx)
    yield {"type": "sources", "sources": source_payload(hits, ctx), "search_query": search_query, "profile_id": ctx.profile_id,
           "graph": {"enabled": use_graph, "entities": entities}}
    for token in llm.stream(build_messages(settings, query, hits, history, ctx)):
        yield {"type": "token", "text": token}
    yield {"type": "done"}
