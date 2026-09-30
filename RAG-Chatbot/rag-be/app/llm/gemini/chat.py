"""Gemini one-shot chat: `get_gemini_chat_response(context, user_query)` -> answer string."""
from ..oneshot import ask
from .llm import GeminiLLM


async def get_gemini_chat_response(context: str, user_query: str, model: str = "") -> str:
    # Gemini "thinking" models spend output tokens on hidden reasoning, so leave the cap off (0).
    return await ask(GeminiLLM, context, user_query, model=model, max_tokens=0)
