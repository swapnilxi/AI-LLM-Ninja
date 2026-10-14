"""Who is asking and what they may see: the per-request scope that travels through the whole pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field

from ..registry import COMMON_ID, Registry


class ProfileNotFound(LookupError):
    pass


@dataclass(frozen=True)
class RAGContext:
    """Who is asking and what they may see. Travels through the whole pipeline."""

    profile_id: str
    include_common: bool = True
    profile_name: str = ""
    profile_instructions: str = ""
    common_instructions: str = ""
    names: dict[str, str] = field(default_factory=dict)  # profile_id -> display name, for citations

    @property
    def allowed_profile_ids(self) -> tuple[str, ...]:
        if self.include_common and self.profile_id != COMMON_ID:
            return (self.profile_id, COMMON_ID)
        return (self.profile_id,)

    def scope_of(self, profile_id: str) -> str:
        return "common" if profile_id == COMMON_ID else "profile"


def resolve_context(reg: Registry, profile_id: str) -> RAGContext:
    """Profile resolver: validates the id against SQLite. Raises ProfileNotFound for unknown / removed / missing profiles."""
    p = reg.get_profile(profile_id or "")
    if p is None or p["status"] != "active":
        raise ProfileNotFound(f"Unknown profile '{profile_id}'")
    common = reg.get_profile(COMMON_ID)
    include = bool(p["include_common"]) and not p["is_common"] and common is not None and common["status"] == "active"
    return RAGContext(
        profile_id=p["id"], include_common=include, profile_name=p["name"],
        profile_instructions=p["instructions"].strip(),
        common_instructions=(common["instructions"].strip() if include and common else ""),
        names={p["id"]: p["name"], COMMON_ID: (common["name"] if common else "Common")},
    )
