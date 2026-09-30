"""DeepSeek — everything you need to know to use it.

Env / Settings:  DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, LLM_MODEL
To use:          LLM_PROVIDER=deepseek
Code:            llm.py (API), chat.py (one-shot helper)
"""
from ..spec import ProviderSpec

SPEC = ProviderSpec(
    id="deepseek",
    name="DeepSeek",
    label="DeepSeek",
    default_model="deepseek-chat",
    models=("deepseek-chat", "deepseek-reasoner"),
    key_field="deepseek_api_key",
    base_url_field="deepseek_base_url",
    default_base_url="https://api.deepseek.com",
    model_env="DEEPSEEK_MODEL",
    signup_url="https://platform.deepseek.com/api_keys",
    notes="OpenAI-compatible API. deepseek-reasoner streams its chain of thought separately; only the final "
          "answer text is shown.",
)
