"""Request/response schemas shared by every module (with input limits as a safeguard)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

Role = Literal["owner", "admin", "member", "viewer"]


TargetType = Literal["agent", "team", "workflow"]


Style = Literal["sequential", "parallel", "supervisor", "router", "round_robin"]


Effort = Literal["low", "medium", "high", "xhigh", "max"]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)
