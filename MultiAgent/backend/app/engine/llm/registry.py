"""Model provider catalog + credential resolution (org credentials → server env → error)."""
from __future__ import annotations

import hashlib
from collections import OrderedDict
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...config import settings
from ...models import ProviderCredential
from ...security import decrypt
from .anthropic_provider import AnthropicProvider
from .base import LLMError, LLMProvider
from .mock_provider import MockProvider
from .openai_provider import OpenAICompatProvider

PROVIDERS: dict[str, dict[str, Any]] = {
    "anthropic": {
        "label": "Anthropic Claude",
        "kind": "anthropic",
        "env": "anthropic_api_key",
        "base_url": "",
        "needs_key": True,
        "supports_temperature": False,
        "models": ["claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5", "claude-fable-5-2"],
        "docs": "https://console.anthropic.com/settings/keys",
    },
    "openai": {
        "label": "OpenAI",
        "kind": "openai",
        "env": "openai_api_key",
        "base_url": "https://api.openai.com/v1",
        "needs_key": True,
        "supports_temperature": True,
        "models": ["gpt-5", "gpt-5-mini", "gpt-4.1", "gpt-4o-mini"],
        "docs": "https://platform.openai.com/api-keys",
    },
    "groq": {
        "label": "Groq",
        "kind": "openai",
        "env": "groq_api_key",
        "base_url": "https://api.groq.com/openai/v1",
        "needs_key": True,
        "supports_temperature": True,
        "models": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "openai/gpt-oss-120b", "qwen/qwen3-32b"],
        "docs": "https://console.groq.com/keys",
    },
    "gemini": {
        "label": "Google Gemini",
        "kind": "openai",
        "env": "gemini_api_key",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "needs_key": True,
        "supports_temperature": True,
        "models": ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.5-flash-lite"],
        "docs": "https://aistudio.google.com/apikey",
    },
    "openrouter": {
        "label": "OpenRouter",
        "kind": "openai",
        "env": "openrouter_api_key",
        "base_url": "https://openrouter.ai/api/v1",
        "needs_key": True,
        "supports_temperature": True,
        "models": ["openai/gpt-5-mini", "meta-llama/llama-3.3-70b-instruct", "google/gemini-2.5-flash"],
        "docs": "https://openrouter.ai/keys",
    },
    "deepseek": {
        "label": "DeepSeek",
        "kind": "openai",
        "env": "deepseek_api_key",
        "base_url": "https://api.deepseek.com/v1",
        "needs_key": True,
        "supports_temperature": True,
        "models": ["deepseek-chat", "deepseek-reasoner"],
        "docs": "https://platform.deepseek.com/api_keys",
    },
    "mistral": {
        "label": "Mistral",
        "kind": "openai",
        "env": "mistral_api_key",
        "base_url": "https://api.mistral.ai/v1",
        "needs_key": True,
        "supports_temperature": True,
        "models": ["mistral-large-latest", "mistral-small-latest"],
        "docs": "https://console.mistral.ai/api-keys",
    },
    "ollama": {
        "label": "Ollama (local)",
        "kind": "openai",
        "env": "",
        "base_url": settings.ollama_base_url,
        "needs_key": False,
        "supports_temperature": True,
        "models": ["llama3.1", "qwen2.5", "mistral"],
        "docs": "https://ollama.com",
    },
    "openai_compatible": {
        "label": "Custom (OpenAI-compatible)",
        "kind": "openai",
        "env": "",
        "base_url": "",
        "needs_key": False,
        "supports_temperature": True,
        "models": [],
        "docs": "",
    },
    "mock": {
        "label": "Mock (offline demo)",
        "kind": "mock",
        "env": "",
        "base_url": "",
        "needs_key": False,
        "supports_temperature": False,
        "models": ["mock-smart"],
        "docs": "",
    },
}

_AUTO_ORDER = ["anthropic", "openai", "groq", "gemini", "openrouter", "deepseek", "mistral"]
_cache: OrderedDict[str, LLMProvider] = OrderedDict()


def env_key(provider: str) -> str:
    attr = PROVIDERS.get(provider, {}).get("env")
    return getattr(settings, attr, "") if attr else ""


def default_model_for(provider: str) -> str:
    models = PROVIDERS.get(provider, {}).get("models") or []
    return models[0] if models else ""


async def org_credentials(session: AsyncSession, org_id: str) -> dict[str, ProviderCredential]:
    rows = (await session.execute(select(ProviderCredential).where(ProviderCredential.org_id == org_id))).scalars().all()
    return {r.provider: r for r in rows}


async def resolve_model(session: AsyncSession, org: Any, provider: str | None, model: str | None) -> tuple[str, str]:
    """Resolve 'default' provider/model using org settings → server defaults → configured keys → mock."""
    provider = (provider or "default").strip()
    model = (model or "").strip()
    if provider and provider != "default":
        return provider, model or default_model_for(provider)

    org_settings = (org.settings if hasattr(org, "settings") else org.get("settings", {})) or {}
    if org_settings.get("default_provider"):
        p = org_settings["default_provider"]
        return p, org_settings.get("default_model") or default_model_for(p)
    if settings.default_provider:
        return settings.default_provider, settings.default_model or default_model_for(settings.default_provider)
    org_id = org.id if hasattr(org, "id") else org["id"]
    creds = await org_credentials(session, org_id)
    for p in _AUTO_ORDER:
        if p in creds and creds[p].api_key_enc:
            return p, default_model_for(p)
    for p in _AUTO_ORDER:
        if env_key(p):
            return p, default_model_for(p)
    return "mock", "mock-smart"


async def get_provider(session: AsyncSession, org: Any, provider: str) -> LLMProvider:
    meta = PROVIDERS.get(provider)
    if not meta:
        raise LLMError(f"Unknown model provider '{provider}'")
    org_settings = (org.settings if hasattr(org, "settings") else org.get("settings", {})) or {}
    allowed = org_settings.get("allowed_providers") or []
    if allowed and provider not in allowed and provider != "mock":
        raise LLMError(f"Provider '{provider}' is not allowed by your organization's policy")
    if meta["kind"] == "mock":
        return MockProvider()

    org_id = org.id if hasattr(org, "id") else org["id"]
    cred = (await org_credentials(session, org_id)).get(provider)
    api_key = decrypt(cred.api_key_enc) if cred else ""
    base_url = (cred.base_url if cred and cred.base_url else "") or meta["base_url"]
    if not api_key:
        api_key = env_key(provider)
    if meta["needs_key"] and not api_key:
        raise LLMError(f"No API key configured for {meta['label']}. Add one in Settings → Model providers.")
    if meta["kind"] == "openai" and not base_url:
        raise LLMError(f"{meta['label']} needs a base URL. Set it in Settings → Model providers.")

    cache_key = hashlib.sha256(f"{provider}|{api_key}|{base_url}".encode()).hexdigest()
    if cache_key in _cache:
        _cache.move_to_end(cache_key)
        return _cache[cache_key]
    if meta["kind"] == "anthropic":
        inst: LLMProvider = AnthropicProvider(api_key=api_key, base_url=base_url or None)
    else:
        headers = {"HTTP-Referer": settings.public_base_url, "X-Title": settings.app_name} if provider == "openrouter" else None
        inst = OpenAICompatProvider(provider, api_key=api_key, base_url=base_url, default_headers=headers)
    _cache[cache_key] = inst
    if len(_cache) > 64:
        _cache.popitem(last=False)
    return inst
