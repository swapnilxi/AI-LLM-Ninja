"""LLM providers. One folder per provider, each with the same three files:

    app/llm/<provider>/spec.py   defaults, models, env vars, quirks   <- read this first
    app/llm/<provider>/llm.py    the API code (stream + list_models)
    app/llm/<provider>/chat.py   one-shot helper: get_<provider>_chat_response(context, question)

Shared pieces: base.py (LLM interface), spec.py (ProviderSpec), openai_compat.py (OpenAI-style protocol used
by openai/groq/deepseek/openrouter), oneshot.py (helper behind every chat.py).

To add a provider: copy a folder, edit spec.py/llm.py, add it to PROVIDERS below and to Settings
(app/config.py: llm_provider Literal + its key/base-url fields).
"""
from __future__ import annotations

from ..config import Settings
from .base import LLM, Message
from .spec import ProviderSpec

from .deepseek import DeepSeekLLM  # isort: skip
from .gemini import GeminiLLM
from .groq import GroqLLM
from .ollama import OllamaLLM
from .openai import OpenAILLM
from .openrouter import OpenRouterLLM

PROVIDERS: dict[str, type[LLM]] = {
    cls.spec.id: cls for cls in (OllamaLLM, GeminiLLM, OpenAILLM, GroqLLM, DeepSeekLLM, OpenRouterLLM)
}


def build_llm(settings: Settings) -> LLM:
    """Cheap to construct (no network / model loading), so no caching needed."""
    return PROVIDERS[settings.llm_provider](settings)


def llm_catalog() -> dict:
    """What the UI shows in the LLM dropdown, generated from each provider's spec.py."""
    return {pid: cls.spec.catalog() for pid, cls in PROVIDERS.items()}


__all__ = ["LLM", "Message", "PROVIDERS", "ProviderSpec", "build_llm", "llm_catalog"]
