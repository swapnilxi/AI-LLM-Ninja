"""Retrieval and answering.

    context.py     RAGContext (who is asking / what they may see), resolve_context, ProfileNotFound
    retrieval.py   profile-scoped vector search
    graph.py       Graph RAG expansion along shared entities (backends live in app/graphstores/)
    formatting.py  hits -> prompt context and the UI `sources` payload
    prompts.py     prompts and shared constants
    pipeline.py    the answer pipeline that streams events (rewrite -> retrieve -> graph -> prompt -> LLM)

Vector stores, embedders and graph stores are separate backend packages (app/vectorstores, app/embeddings,
app/graphstores) that this package calls.
"""
from .context import ProfileNotFound, RAGContext, resolve_context
from .formatting import format_context, is_faq, source_payload
from .graph import graph_expand, parse_entities
from .pipeline import answer_events, build_messages, clean_history, system_prompt
from .prompts import ENTITY_PROMPT, FAQ_PREFIX, REWRITE_PROMPT, UNTRUSTED_NOTICE
from .retrieval import retrieve

__all__ = ["ENTITY_PROMPT", "FAQ_PREFIX", "ProfileNotFound", "RAGContext", "REWRITE_PROMPT", "UNTRUSTED_NOTICE",
           "answer_events", "build_messages", "clean_history", "format_context", "graph_expand", "is_faq", "parse_entities",
           "resolve_context", "retrieve", "source_payload", "system_prompt"]
