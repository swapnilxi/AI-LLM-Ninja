"""One-shot helper shared by every provider's chat.py: (context, question) -> answer string."""
from __future__ import annotations

import asyncio
import os

from ..config import current_settings
from .base import LLM

DEFAULT_SYSTEM_PROMPT = "Use the following context to answer:\n{context}"


async def ask(
    provider: type[LLM],
    context: str,
    user_query: str,
    *,
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    max_tokens: int = 512,
    model: str = "",
) -> str:
    """Model precedence: explicit `model` > the provider's model_env variable > provider default.
    Keys and base URLs come from the normal config (.env or the Settings page)."""
    spec = provider.spec
    settings = current_settings().model_copy(update={
        "llm_provider": spec.id,
        "llm_model": model or (os.getenv(spec.model_env, "") if spec.model_env else ""),
        "llm_max_tokens": max_tokens,
    })
    messages = [
        {"role": "system", "content": system_prompt.format(context=context)},
        {"role": "user", "content": user_query},
    ]
    # provider clients are blocking; keep the event loop free
    return (await asyncio.to_thread(provider(settings).chat, messages)).strip()
