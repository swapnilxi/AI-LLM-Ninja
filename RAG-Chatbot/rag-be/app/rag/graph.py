"""Graph RAG: widen the retrieved passages along the entities they share (see app/graphstores/)."""
from __future__ import annotations

import json
import re

from ..config import Settings
from ..embeddings import build_embedder
from ..graphstores import build_graph
from ..vectorstores import Hit, build_store
from .context import RAGContext
from .prompts import ENTITY_PROMPT, FAQ_PREFIX

GRAPH_HOP_K = 3  # extra chunks pulled in per entity during graph expansion
GRAPH_MAX_HITS = 14  # total chunks kept after expansion, across all entities
GRAPH_MAX_SEEDS = 8  # entities followed in the graph


def parse_entities(text: str) -> list[str]:
    m = re.search(r"\[.*\]", text or "", re.S)
    try:
        data = json.loads(m.group(0)) if m else []
    except ValueError:
        return []
    out: list[str] = []
    for x in data if isinstance(data, list) else []:
        if isinstance(x, str) and x.strip() and x.strip().lower() not in {e.lower() for e in out}:
            out.append(x.strip()[:80])
    return out[:5]


def graph_expand(settings: Settings, llm, query: str, hits: list[Hit], ctx: RAGContext) -> tuple[list[Hit], list[str]]:
    """Graph RAG. Seeds are the entities named in the question plus those of the best passages; the graph store
    (SQLite by default, Neo4j optional) returns chunks that mention them or their co-occurring entities, so facts
    spread over several documents reach the LLM together. Same profile scope as normal retrieval.
    Uses the graph built at index time (no LLM call). If the graph has no data yet, falls back to asking the LLM for
    entities and searching the vector store for each. Never raises: on any failure the original hits are returned."""
    if not hits:
        return hits, []
    allowed = ctx.allowed_profile_ids
    room = GRAPH_MAX_HITS - len(hits)
    seen = {(h.document_id, h.index) for h in hits}
    try:
        graph = build_graph(settings) if settings.graph_enabled else None
        if graph is not None and graph.has_data(allowed):
            seeds = {e.norm: e for e in graph.find_in_text(query, allowed)}
            for e in graph.entities_of([k for k in seen if not k[0].startswith(FAQ_PREFIX)][:3] or [(h.document_id, h.index) for h in hits[:3]]):
                seeds.setdefault(e.norm, e)
            seeds_l = list(seeds.values())[:GRAPH_MAX_SEEDS]
            extra = graph.neighbors(seeds_l, allowed, room, seen, hops=2) if seeds_l else []
            return hits + [h for h in extra if h.profile_id in allowed], [e.label for e in seeds_l]
        return _llm_graph_expand(settings, llm, query, hits, ctx)
    except Exception:
        return hits, []


def _llm_graph_expand(settings: Settings, llm, query: str, hits: list[Hit], ctx: RAGContext) -> tuple[list[Hit], list[str]]:
    seed = "\n\n".join(h.text for h in hits[:3])
    entities = parse_entities(llm.chat([{"role": "system", "content": ENTITY_PROMPT},
                                       {"role": "user", "content": f"Question: {query}\n\nText:\n{seed}"}]))
    if not entities:
        return hits, []
    embedder, store = build_embedder(settings), build_store(settings)
    allowed = ctx.allowed_profile_ids
    seen = {(h.document_id, h.index) for h in hits}
    extra: list[Hit] = []
    for e in entities:
        for h in store.search(embedder.embed_query(e), GRAPH_HOP_K, allowed):
            if h.profile_id in allowed and h.score >= settings.score_threshold and (h.document_id, h.index) not in seen:
                seen.add((h.document_id, h.index))
                extra.append(h)
    return (hits + sorted(extra, key=lambda h: -h.score))[:GRAPH_MAX_HITS], entities
