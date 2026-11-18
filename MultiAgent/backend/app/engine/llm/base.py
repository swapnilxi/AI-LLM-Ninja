"""Provider-neutral LLM types.

Internal message format (a list of dicts):
  {"role": "user", "content": str}
  {"role": "assistant", "content": str, "tool_calls": [ToolCall-as-dict], "raw": provider replay data}
  {"role": "tool", "tool_call_id": str, "name": str, "content": str, "is_error": bool}

`raw` lets a provider replay its own assistant turn byte-for-byte inside one run
(e.g. Anthropic thinking blocks must be passed back unchanged).
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any


class LLMError(Exception):
    """User-facing model/provider error."""


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "arguments": self.arguments}


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class LLMResponse:
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    stop_reason: str = "end_turn"
    usage: Usage = field(default_factory=Usage)
    thinking: str = ""
    raw: Any = None


@dataclass
class StreamEvent:
    type: str  # text | thinking | done
    text: str = ""
    response: LLMResponse | None = None


@dataclass
class ModelSettings:
    model: str
    max_tokens: int = 8000
    temperature: float | None = None
    effort: str = "medium"
    show_thinking: bool = False


class LLMProvider:
    key: str = "base"

    async def stream(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        settings: ModelSettings,
    ) -> AsyncIterator[StreamEvent]:  # pragma: no cover - interface
        raise NotImplementedError
        yield  # type: ignore[unreachable]

    async def complete(self, *, system: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]], settings: ModelSettings) -> LLMResponse:
        final: LLMResponse | None = None
        async for ev in self.stream(system=system, messages=messages, tools=tools, settings=settings):
            if ev.type == "done":
                final = ev.response
        if final is None:
            raise LLMError("Model returned no response")
        return final
