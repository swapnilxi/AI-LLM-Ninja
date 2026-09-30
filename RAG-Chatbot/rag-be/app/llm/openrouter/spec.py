"""OpenRouter — everything you need to know to use it.

Env / Settings:  OPENROUTER_API_KEY, OPENROUTER_BASE_URL, LLM_MODEL
To use:          LLM_PROVIDER=openrouter
Code:            llm.py (API), chat.py (one-shot helper)
"""
from ..spec import ProviderSpec

SPEC = ProviderSpec(
    id="openrouter",
    name="OpenRouter",
    label="OpenRouter (many models, some free)",
    default_model="meta-llama/llama-3.3-70b-instruct:free",
    models=(
        "meta-llama/llama-3.3-70b-instruct:free",
        "deepseek/deepseek-chat-v3-0324:free",
        "google/gemma-3-27b-it:free",
    ),
    key_field="openrouter_api_key",
    base_url_field="openrouter_base_url",
    default_base_url="https://openrouter.ai/api/v1",
    model_env="OPENROUTER_MODEL",
    signup_url="https://openrouter.ai/keys",
    notes="Model ids look like vendor/model. Ids ending in ':free' cost nothing but are rate limited and the "
          "free list changes often: use 'Fetch list' in the UI for what exists today.",
)
