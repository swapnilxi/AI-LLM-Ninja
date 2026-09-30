"""OpenAI one-shot chat: `get_openai_chat_response(context, user_query)` -> answer string.

Thin wrapper over OpenAILLM (llm.py) via the shared helper in app/llm/oneshot.py, so it uses the app's
config (OPENAI_API_KEY / OPENAI_BASE_URL / OPENAI_MODEL in .env or the Settings page) instead of the old
global `openai.api_key` and a hard-coded gpt-3.5-turbo.

Fixed vs. the original:
  * reasoning models (o-series, gpt-5*) no longer get `temperature` or a small token cap; their hidden
    reasoning tokens count against the cap, so 512 used to produce an EMPTY answer;
  * `max_tokens` -> `max_completion_tokens`;
  * no dependency on the `openai` SDK, and the blocking call runs off the event loop.
"""
import os

from ..oneshot import ask
from .llm import OpenAILLM
from .spec import SPEC

SYSTEM_PROMPT = "Use the following context to answer:\n{context}"


async def get_openai_chat_response(context: str, user_query: str, model: str = "") -> str:
    chosen = model or os.getenv(SPEC.model_env, "") or SPEC.default_model
    return await ask(
        OpenAILLM, context, user_query,
        system_prompt=SYSTEM_PROMPT,
        model=chosen,
        max_tokens=0 if OpenAILLM.is_reasoning(chosen) else 512,  # 0 = no cap
    )
