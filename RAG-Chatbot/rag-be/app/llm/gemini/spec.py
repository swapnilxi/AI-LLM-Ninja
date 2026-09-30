"""Google Gemini — everything you need to know to use it.

Env / Settings:  GEMINI_API_KEY, LLM_MODEL
To use:          LLM_PROVIDER=gemini
Code:            llm.py (native Gemini REST API, not OpenAI-compatible), chat.py (one-shot helper)
"""
from ..spec import ProviderSpec

API = "https://generativelanguage.googleapis.com/v1beta"

SPEC = ProviderSpec(
    id="gemini",
    name="Gemini",
    label="Google Gemini (free tier)",
    default_model="gemini-flash-latest",
    models=("gemini-flash-latest", "gemini-flash-lite-latest", "gemini-2.5-flash", "gemini-2.5-pro"),
    key_field="gemini_api_key",
    base_url_field=None,
    default_base_url=API,
    model_env="GEMINI_MODEL",
    signup_url="https://aistudio.google.com/apikey",
    notes="Own message format: the system prompt goes in `systemInstruction` and the assistant role is called "
          "'model'. The key is sent in the x-goog-api-key header (never in the URL). '-latest' aliases avoid "
          "hard-coding model versions that Google later retires. 'Thinking' parts are not shown.",
)
