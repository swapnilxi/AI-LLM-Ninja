"""Request bodies and the JSON view of an agent."""
from __future__ import annotations

from pydantic import BaseModel, Field

class AgentIn(BaseModel):
    profile_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=60)
    role: str
    description: str = Field("", max_length=300)
    instructions: str = Field("", max_length=8000)
    focus: str = Field("", max_length=200)
    model: str = Field("", max_length=100)
    enabled: bool = True


class AgentPatch(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=60)
    role: str | None = None
    description: str | None = Field(None, max_length=300)
    instructions: str | None = Field(None, max_length=8000)
    focus: str | None = Field(None, max_length=200)
    model: str | None = Field(None, max_length=100)
    enabled: bool | None = None


def agent_view(a: dict, names: dict[str, str]) -> dict:
    return {**{k: a[k] for k in ("id", "profile_id", "name", "role", "description", "instructions", "focus", "model",
                                 "enabled", "position", "run_count", "error_count", "last_run_at", "last_error", "updated_at")},
            "profile_name": names.get(a["profile_id"], a["profile_id"])}
