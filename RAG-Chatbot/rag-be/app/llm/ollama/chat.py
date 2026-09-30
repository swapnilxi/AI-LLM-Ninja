"""Ollama one-shot chat: `get_ollama_chat_response(context, user_query)` -> answer string."""
from ..oneshot import ask
from .llm import OllamaLLM


async def get_ollama_chat_response(context: str, user_query: str, model: str = "") -> str:
    return await ask(OllamaLLM, context, user_query, model=model)
