"""Turning hits into prompt context and into the `sources` payload the UI shows."""
from __future__ import annotations

from ..registry import COMMON_ID
from ..vectorstores import Hit
from .context import RAGContext
from .prompts import FAQ_PREFIX


def is_faq(h: Hit) -> bool:
    return h.document_id.startswith(FAQ_PREFIX)


def _label(h: Hit) -> str:
    if is_faq(h):
        return "FAQ" + (" (common)" if h.profile_id == COMMON_ID else "")
    return f"common/{h.source}" if h.profile_id == COMMON_ID else h.source


def format_context(hits: list[Hit]) -> str:
    blocks = []
    for i, h in enumerate(hits, start=1):
        where = f"{_label(h)}, p.{h.page}" if h.page else _label(h)
        blocks.append(f"[{i}] ({where})\n{h.text}")
    return "\n\n".join(blocks)


def source_payload(hits: list[Hit], ctx: RAGContext) -> list[dict]:
    return [
        {"id": i, "source": h.source, "page": h.page, "score": round(h.score, 4), "text": h.text,
         "profile_id": h.profile_id, "profile_name": ctx.names.get(h.profile_id, h.profile_id),
         "scope": ctx.scope_of(h.profile_id), "document_id": h.document_id,
         "kind": "faq" if is_faq(h) else "document", "faq_id": h.document_id[len(FAQ_PREFIX):] if is_faq(h) else None}
        for i, h in enumerate(hits, start=1)
    ]
