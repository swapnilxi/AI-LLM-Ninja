"""OpenAI — everything you need to know to use it.

Env / Settings:  OPENAI_API_KEY, OPENAI_BASE_URL (change it to use any OpenAI-compatible server:
LM Studio, vLLM, Azure-style gateways...), LLM_MODEL (or OPENAI_MODEL for the one-shot helper).
To use:          LLM_PROVIDER=openai
Code:            llm.py (API + quirks), chat.py (one-shot helper)
"""
from ..spec import ProviderSpec

SPEC = ProviderSpec(
    id="openai",
    name="OpenAI",
    label="OpenAI (paid)",
    default_model="gpt-4o-mini",
    models=("gpt-4o-mini", "gpt-4o", "gpt-4.1-mini", "gpt-4.1"),
    key_field="openai_api_key",
    base_url_field="openai_base_url",
    default_base_url="https://api.openai.com/v1",
    model_env="OPENAI_MODEL",
    signup_url="https://platform.openai.com/api-keys",
    notes=(
        "Uses max_completion_tokens (max_tokens is deprecated). Reasoning models (o1/o3/o4/gpt-5*) reject "
        "`temperature`, and their hidden reasoning tokens count against the output cap."
    ),
)
