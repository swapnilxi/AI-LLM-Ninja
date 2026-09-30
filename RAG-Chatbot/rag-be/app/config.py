"""Layered configuration.

Precedence (lowest -> highest):
    1. defaults declared on `Settings`
    2. environment / `.env`
    3. UI overrides persisted in `data/settings.json`

`Settings` holds everything a user may tune from the UI. Deployment-level
switches that must never be changed from a browser live in `ServerConfig`
(environment only).
"""
from __future__ import annotations

import json
import os
import re
import threading
from pathlib import Path
from typing import Any, Literal

from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError, model_validator

BASE_DIR = Path(__file__).resolve().parent.parent  # rag-be/
load_dotenv(BASE_DIR / ".env")

DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful assistant that answers questions using ONLY the provided context.\n"
    "- Cite the context snippets you used with their bracket numbers, e.g. [1], [2].\n"
    "- If the context does not contain the answer, say you don't know instead of guessing.\n"
    "- Be concise and accurate."
)

SECRET_FIELDS = {
    "gemini_api_key", "deepseek_api_key", "openrouter_api_key", "openai_api_key", "groq_api_key", "database_url",
}
MASK = "••••"


class Settings(BaseModel):
    # ---- LLM -------------------------------------------------------------
    llm_provider: Literal["ollama", "gemini", "deepseek", "openrouter", "openai", "groq"] = "gemini"
    llm_model: str = ""  # empty -> provider default
    llm_temperature: float = Field(0.2, ge=0, le=2)
    llm_max_tokens: int = Field(0, ge=0)  # 0 -> provider default

    # ---- Embeddings ------------------------------------------------------
    embedding_provider: Literal["sentence-transformers", "ollama", "gemini", "openai", "hash"] = (
        "sentence-transformers"
    )
    embedding_model: str = ""  # empty -> provider default
    embedding_dimensions: int = Field(0, ge=0)  # 0 -> provider default (gemini only)

    # ---- Vector store ----------------------------------------------------
    vector_store: Literal["chroma", "postgres"] = "chroma"
    chroma_path: str = "data/chroma"
    database_url: str = ""  # local Postgres or Neon (needs pgvector)
    vector_table: str = "rag_chunks"  # table / collection name

    # ---- RAG behaviour ---------------------------------------------------
    chunk_size: int = Field(800, ge=100, le=8000)
    chunk_overlap: int = Field(120, ge=0)
    top_k: int = Field(5, ge=1, le=50)
    score_threshold: float = Field(0.0, ge=0, le=1)
    history_turns: int = Field(4, ge=0, le=20)
    query_rewrite: bool = False
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    rag_data_dir: str = "../rag-data"  # each folder directly inside is one profile
    auto_sync_interval: int = Field(0, ge=0)  # seconds; 0 = only sync on demand

    # ---- Credentials / endpoints ----------------------------------------
    ollama_base_url: str = "http://localhost:11434"
    gemini_api_key: str = ""
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"  # also works for any OpenAI-compatible server
    groq_api_key: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"

    @model_validator(mode="after")
    def _check_overlap(self) -> "Settings":
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        return self

    def data_dir(self) -> Path:
        return resolve_path(self.rag_data_dir)


class ServerConfig(BaseModel):
    """Deployment-level switches. Environment only, never editable via API."""

    allow_ui_config: bool = True
    allow_ui_upload: bool = True
    admin_token: str = ""
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    settings_file: str = "data/settings.json"
    db_file: str = "data/app.db"  # SQLite: profiles + document/indexing state
    max_upload_mb: int = 25
    sync_on_startup: bool = True


def resolve_path(p: str) -> Path:
    path = Path(p).expanduser()
    return path if path.is_absolute() else (BASE_DIR / path).resolve()


def _coerce_env(name: str, raw: str) -> Any:
    return raw  # pydantic coerces str -> int/float/bool for us


def env_values() -> dict[str, Any]:
    return {
        name: _coerce_env(name, os.environ[name.upper()])
        for name in Settings.model_fields
        if os.environ.get(name.upper(), "") != ""
    }


def load_server_config() -> ServerConfig:
    kw: dict[str, Any] = {}
    for name in ServerConfig.model_fields:
        raw = os.environ.get(name.upper())
        if raw in (None, ""):
            continue
        kw[name] = [o.strip() for o in raw.split(",") if o.strip()] if name == "cors_origins" else raw
    return ServerConfig(**kw)


def mask_secret(name: str, value: str) -> str:
    if not value:
        return ""
    if name == "database_url":  # keep host/db visible, hide the password
        return re.sub(r"(://[^:/@]+):[^@]*@", rf"\1:{MASK}@", value)
    return MASK + value[-4:] if len(value) > 8 else MASK


class ConfigManager:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.RLock()
        self._overrides: dict[str, Any] = self._load()

    # -- persistence -----------------------------------------------------
    def _load(self) -> dict[str, Any]:
        try:
            data = json.loads(self.path.read_text())
            return {k: v for k, v in data.items() if k in Settings.model_fields}
        except (OSError, ValueError):
            return {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._overrides, indent=2))
        os.chmod(tmp, 0o600)  # may hold API keys
        tmp.replace(self.path)

    # -- reads -----------------------------------------------------------
    @property
    def current(self) -> Settings:
        with self._lock:
            return Settings(**{**env_values(), **self._overrides})

    def overridden_keys(self) -> list[str]:
        with self._lock:
            return sorted(self._overrides)

    def merged(self, patch: dict[str, Any] | None) -> Settings:
        """Current settings + an unsaved patch (used for 'test connection')."""
        base = self.current.model_dump()
        return Settings(**{**base, **self._clean_patch(patch or {}, drop_masked=True)})

    def public(self) -> dict[str, Any]:
        """Settings safe to send to a browser: secrets masked."""
        data = self.current.model_dump()
        for name in SECRET_FIELDS:
            data[name] = mask_secret(name, data[name])
        return data

    # -- writes ----------------------------------------------------------
    @staticmethod
    def _clean_patch(patch: dict[str, Any], drop_masked: bool) -> dict[str, Any]:
        out = {}
        for k, v in patch.items():
            if k not in Settings.model_fields:
                continue
            if k in SECRET_FIELDS and isinstance(v, str) and MASK in v:
                if drop_masked:
                    continue  # the UI echoed a masked value back: keep the real one
            out[k] = v
        return out

    def update(self, patch: dict[str, Any]) -> Settings:
        with self._lock:
            clean = self._clean_patch(patch, drop_masked=True)
            new = dict(self._overrides)
            for k, v in clean.items():
                if v is None or (k in SECRET_FIELDS and v == ""):
                    new.pop(k, None)  # empty secret -> fall back to env
                else:
                    new[k] = v
            try:
                Settings(**{**env_values(), **new})  # validate before persisting
            except ValidationError as e:
                raise ValueError(_format_validation(e)) from e
            self._overrides = new
            self._save()
            return self.current

    def reset(self) -> Settings:
        with self._lock:
            self._overrides = {}
            self._save()
            return self.current


def current_settings() -> Settings:
    """Effective settings (defaults < .env < UI overrides) for code outside the FastAPI app
    (scripts, helpers). Re-reads the overrides file, so it is always up to date."""
    return ConfigManager(resolve_path(load_server_config().settings_file)).current


def _format_validation(e: ValidationError) -> str:
    return "; ".join(f"{'.'.join(map(str, err['loc']))}: {err['msg']}" for err in e.errors())
