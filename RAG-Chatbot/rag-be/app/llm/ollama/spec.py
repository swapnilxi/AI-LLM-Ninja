"""Ollama (local, free) — everything you need to know to use it.

Env / Settings:  OLLAMA_BASE_URL, LLM_MODEL   (no API key)
To use:          install Ollama, `ollama pull llama3.2`, LLM_PROVIDER=ollama
Code:            llm.py (native /api/chat NDJSON streaming), chat.py (one-shot helper)
"""
from ..spec import ProviderSpec

SPEC = ProviderSpec(
    id="ollama",
    name="Ollama",
    label="Ollama (local, free)",
    default_model="llama3.2",
    models=("llama3.2", "llama3.1", "qwen2.5", "mistral", "gemma2", "phi3"),
    key_field=None,
    base_url_field="ollama_base_url",
    default_base_url="http://localhost:11434",
    model_env="OLLAMA_MODEL",
    signup_url="https://ollama.com/download",
    notes="A model must be pulled first (`ollama pull <name>`) or you get a 404 'model not found'. "
          "'Fetch list' in the UI shows what is installed. Uses num_predict (not max_tokens) for the cap.",
)
