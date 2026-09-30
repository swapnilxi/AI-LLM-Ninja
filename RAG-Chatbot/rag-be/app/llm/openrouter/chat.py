"""OpenRouter one-shot chat: `get_openrouter_chat_response(context, user_query)` -> answer string."""
from ..oneshot import ask
from .llm import OpenRouterLLM


async def get_openrouter_chat_response(context: str, user_query: str, model: str = "") -> str:
    return await ask(OpenRouterLLM, context, user_query, model=model)
