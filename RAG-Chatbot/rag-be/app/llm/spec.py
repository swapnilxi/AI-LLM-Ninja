"""ProviderSpec: the declarative, per-provider facts (kept dependency-free on purpose).

Every provider folder (app/llm/<provider>/spec.py) declares one SPEC. The registry (app/llm/__init__.py),
the UI catalog and the docs are all generated from these, so "what does provider X need?" has exactly one
answer, in one file.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderSpec:
    id: str                      # value of LLM_PROVIDER
    name: str                    # short display name used in error messages
    label: str                   # long label shown in the UI dropdown
    default_model: str           # used when LLM_MODEL is empty
    models: tuple[str, ...]      # suggestions shown in the UI (the "Fetch list" button shows the real list)
    key_field: str | None        # Settings field holding the API key (env var = FIELD.upper())
    base_url_field: str | None   # Settings field holding the base URL
    default_base_url: str        # must equal the Settings default (tests enforce this)
    model_env: str = ""          # optional env var that overrides the model for the one-shot chat helper
    signup_url: str = ""         # where to get a key
    notes: str = ""              # provider quirks worth knowing

    @property
    def fields(self) -> list[str]:
        """Settings fields the UI should show when this provider is selected."""
        return [f for f in (self.key_field, self.base_url_field) if f]

    def catalog(self) -> dict:
        return {"label": self.label, "default_model": self.default_model, "models": list(self.models), "fields": self.fields}
