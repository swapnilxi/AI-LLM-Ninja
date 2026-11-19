"""One-shot LLM completion with the org's default model (used by the "AI" helpers: tasks, scheduling).

Every helper that calls this must also work offline: when the resolved provider is the mock model, or the
call fails, callers fall back to deterministic rules. `complete()` therefore reports which provider answered.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from .llm.base import LLMError, ModelSettings
from .llm.registry import get_provider, resolve_model

log = logging.getLogger("agentforge.oneshot")


async def complete(session: AsyncSession, org: Any, system: str, prompt: str, *, max_tokens: int = 900) -> tuple[str, str]:
    """Return (text, provider_key). Raises LLMError when no model could be reached."""
    provider_key, model = await resolve_model(session, org, "default", "")
    provider = await get_provider(session, org, provider_key)
    resp = await provider.complete(
        system=system, messages=[{"role": "user", "content": prompt}], tools=[], settings=ModelSettings(model=model, max_tokens=max_tokens, temperature=None)
    )
    return resp.text, provider_key


def parse_json(raw: str, kind: type = list) -> Any:
    """Pull the first JSON array/object out of a model reply (tolerates code fences and chatter). None if absent."""
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", (raw or "").strip(), flags=re.I).strip()
    m = re.search(r"\[.*\]" if kind is list else r"\{.*\}", raw, flags=re.S)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except ValueError:
        return None
    return data if isinstance(data, kind) else None


__all__ = ["complete", "parse_json", "LLMError"]
