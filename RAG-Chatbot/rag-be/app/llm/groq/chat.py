"""Groq one-shot chat: `get_groq_chat_response(context, user_query)` -> answer string.

Thin wrapper over GroqLLM (llm.py) via app/llm/oneshot.py; key and model come from the normal config
(GROQ_API_KEY / GROQ_MODEL in .env, or the Settings page).

Fixed vs. the original: it crashed on import (a module-level `messages` list used an undefined `context`),
called the blocking `requests.post` inside an `async def`, and hard-coded a retired model.
"""
from ..oneshot import ask
from .llm import GroqLLM

SYSTEM_PROMPT = (
    "Answer as an expert using ONLY the following context. "
    "If unsure, say 'I don't know.'\n\n"
    "Context:\n{context}"
)


async def get_groq_chat_response(context: str, user_query: str, model: str = "") -> str:
    return await ask(GroqLLM, context, user_query, system_prompt=SYSTEM_PROMPT, model=model)
