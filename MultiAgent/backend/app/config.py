"""Application settings, loaded from environment variables / .env."""
from __future__ import annotations

import os
import secrets
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(BASE_DIR / ".env"), extra="ignore")

    app_name: str = "AgentForge"
    env: str = "development"  # development | production
    secret_key: str = ""
    database_url: str = f"sqlite+aiosqlite:///{DATA_DIR / 'agentforge.db'}"
    public_base_url: str = "http://localhost:8000"

    # --- HTTP / security -------------------------------------------------
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    trusted_hosts: str = ""  # comma separated; empty = allow all
    trust_proxy_headers: bool = False  # honour X-Forwarded-For (only behind a trusted proxy)
    access_token_minutes: int = 60 * 12
    registration_open: bool = True
    max_request_mb: int = 2  # JSON bodies
    max_upload_mb: int = 15  # document uploads
    allow_private_network: bool = False  # SSRF guard for tools / connectors
    login_max_failures: int = 5
    login_lockout_minutes: int = 15

    # --- Rate limits (requests / window) ---------------------------------
    redis_url: str = ""  # optional shared limiter backend
    rate_limit_global_per_minute: int = 600  # per client IP
    rate_limit_auth_per_minute: int = 10  # login/register per IP
    rate_limit_runs_per_minute: int = 30  # run starts per org
    rate_limit_webhook_per_minute: int = 60  # per webhook token

    # --- Run guardrails ---------------------------------------------------
    max_concurrent_runs_per_org: int = 8
    default_daily_token_limit: int = 2_000_000  # per org, 0 = unlimited
    run_timeout_seconds: int = 900
    tool_timeout_seconds: int = 60
    max_tool_output_chars: int = 20_000
    max_agent_depth: int = 3  # nested agent-as-tool / supervisor delegation

    # --- Defaults ---------------------------------------------------------
    default_provider: str = ""  # empty = auto-detect from configured keys
    default_model: str = ""
    scheduler_enabled: bool = True
    scheduler_interval_seconds: int = 20

    # --- Server-wide provider keys (orgs can override in Settings) ---------
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    groq_api_key: str = ""
    gemini_api_key: str = ""
    openrouter_api_key: str = ""
    deepseek_api_key: str = ""
    mistral_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434/v1"
    tavily_api_key: str = ""
    brave_api_key: str = ""

    extra: dict = Field(default_factory=dict)

    @property
    def is_production(self) -> bool:
        return self.env.lower() == "production"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def trusted_host_list(self) -> list[str]:
        return [h.strip() for h in self.trusted_hosts.split(",") if h.strip()]


def _resolve_secret_key(settings: Settings) -> str:
    if settings.secret_key:
        if settings.is_production and len(settings.secret_key) < 32:
            raise RuntimeError("SECRET_KEY must be at least 32 characters in production")
        return settings.secret_key
    if settings.is_production:
        raise RuntimeError("SECRET_KEY must be set in production")
    # Development: persist a generated key so encrypted secrets survive restarts.
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    key_file = DATA_DIR / ".secret_key"
    if key_file.exists():
        return key_file.read_text().strip()
    key = secrets.token_urlsafe(48)
    key_file.write_text(key)
    try:
        os.chmod(key_file, 0o600)
    except OSError:
        pass
    return key


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.secret_key = _resolve_secret_key(s)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return s


settings = get_settings()
