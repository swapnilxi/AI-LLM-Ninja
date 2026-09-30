"""DeepSeek one-shot chat: `get_deepseek_chat_response(context, user_query)` -> answer string."""
from ..oneshot import ask
from .llm import DeepSeekLLM


async def get_deepseek_chat_response(context: str, user_query: str, model: str = "") -> str:
    return await ask(DeepSeekLLM, context, user_query, model=model)
