"""Groq — everything you need to know to use it.

Env / Settings:  GROQ_API_KEY, GROQ_BASE_URL, LLM_MODEL (or GROQ_MODEL for the one-shot helper)
To use:          LLM_PROVIDER=groq
Code:            llm.py (API), chat.py (one-shot helper)
"""
from ..spec import ProviderSpec

SPEC = ProviderSpec(
    id="groq",
    name="Groq",
    label="Groq (fast, free tier)",
    default_model="llama-3.3-70b-versatile",
    models=("llama-3.3-70b-versatile", "llama-3.1-8b-instant", "gemma2-9b-it"),
    key_field="groq_api_key",
    base_url_field="groq_base_url",
    default_base_url="https://api.groq.com/openai/v1",
    model_env="GROQ_MODEL",
    signup_url="https://console.groq.com/keys",
    notes="OpenAI-compatible API. Free tier is rate limited (the HTTP layer retries 429s with backoff). "
          "Old default llama3-70b-8192 was retired; use the models above or 'Fetch list' in the UI.",
)
