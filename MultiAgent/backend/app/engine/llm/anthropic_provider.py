"""Anthropic (Claude) provider using the official SDK with streaming.

Notes for current Claude models (Opus 5.5 / Sonnet 5.5 / Haiku 5.5 / Fable):
* sampling params (temperature/top_p) are not sent - they are rejected
* thinking is adaptive; depth is controlled with output_config.effort
* forced tool_choice is not used (auto only)
* assistant turns are replayed unchanged within a run (thinking blocks intact);
  across chat turns we only send text, so no stale thinking blocks are replayed
* server-side refusal fallbacks are enabled for models that support them
"""
from __future__ import annotations

import re
from collections.abc import AsyncIterator
from typing import Any

import anthropic
from anthropic import AsyncAnthropic

from .base import LLMError, LLMProvider, LLMResponse, ModelSettings, StreamEvent, ToolCall, Usage

_FALLBACK_BETA = "server-side-fallback-2026-07-01"
_FALLBACK_MODELS = ("claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5", "claude-fable-5-1", "claude-fable-5-2")
_MODEL_RE = re.compile(r"claude-(opus|sonnet|haiku|fable|mythos)-(\d+)(?:-(\d+))?")


def _adaptive_support(model: str) -> tuple[bool, bool]:
    """Returns (supports adaptive thinking + effort, supports xhigh/max effort)."""
    m = _MODEL_RE.search(model)
    if not m:
        return False, False
    family, major, minor = m.group(1), int(m.group(2)), int(m.group(3) or 0)
    if major >= 5:
        return True, True
    if major == 4 and family == "opus" and minor >= 6:
        return True, minor >= 7
    if major == 4 and family == "sonnet" and minor >= 6:
        return True, False
    return False, False


class AnthropicProvider(LLMProvider):
    key = "anthropic"

    def __init__(self, api_key: str, base_url: str | None = None, use_fallbacks: bool = True) -> None:
        self.client = AsyncAnthropic(api_key=api_key, base_url=base_url or None, max_retries=2, timeout=600)
        self.use_fallbacks = use_fallbacks

    # ------------------------------------------------------------------ conversion
    @staticmethod
    def _convert(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []

        def push_user_blocks(blocks: list[Any]) -> None:
            if out and out[-1]["role"] == "user":
                prev = out[-1]["content"]
                if isinstance(prev, str):
                    prev = [{"type": "text", "text": prev}]
                out[-1]["content"] = prev + blocks
            else:
                out.append({"role": "user", "content": blocks})

        for m in messages:
            role = m["role"]
            if role == "user":
                push_user_blocks([{"type": "text", "text": m.get("content") or "(empty)"}])
            elif role == "assistant":
                raw = m.get("raw")
                if isinstance(raw, dict) and raw.get("provider") == "anthropic":
                    content = raw["content"]
                else:
                    content = []
                    if m.get("content"):
                        content.append({"type": "text", "text": m["content"]})
                    for tc in m.get("tool_calls") or []:
                        content.append({"type": "tool_use", "id": tc["id"], "name": tc["name"], "input": tc["arguments"]})
                    if not content:
                        content = [{"type": "text", "text": "(no content)"}]
                out.append({"role": "assistant", "content": content})
            elif role == "tool":
                push_user_blocks(
                    [
                        {
                            "type": "tool_result",
                            "tool_use_id": m["tool_call_id"],
                            "content": m.get("content") or "(empty)",
                            "is_error": bool(m.get("is_error")),
                        }
                    ]
                )
        if out and out[0]["role"] != "user":
            out.insert(0, {"role": "user", "content": "(conversation start)"})
        return out

    # ------------------------------------------------------------------ streaming
    async def stream(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        settings: ModelSettings,
    ) -> AsyncIterator[StreamEvent]:
        kwargs: dict[str, Any] = {
            "model": settings.model,
            "max_tokens": max(1024, min(settings.max_tokens or 8000, 128000)),
            "system": system,
            "messages": self._convert(messages),
        }
        if tools:
            kwargs["tools"] = [
                {"name": t["name"], "description": t["description"][:4000], "input_schema": t["parameters"]} for t in tools
            ]
        adaptive, xhigh = _adaptive_support(settings.model)
        if adaptive:
            kwargs["thinking"] = {"type": "adaptive", "display": "summarized"} if settings.show_thinking else {"type": "adaptive"}
            effort = settings.effort or "medium"
            if not xhigh and effort in ("xhigh", "max"):
                effort = "high"
            kwargs["output_config"] = {"effort": effort}

        use_fallbacks = self.use_fallbacks and settings.model.startswith(_FALLBACK_MODELS)
        try:
            async for ev in self._stream_once(kwargs, use_fallbacks):
                yield ev
        except anthropic.BadRequestError as exc:
            if use_fallbacks and "fallback" in str(exc).lower():
                self.use_fallbacks = False  # account without the beta: retry plainly
                async for ev in self._stream_once(kwargs, False):
                    yield ev
            else:
                raise LLMError(f"Anthropic rejected the request: {_err(exc)}") from exc
        except anthropic.AuthenticationError as exc:
            raise LLMError("Anthropic API key is invalid. Update it in Settings → Model providers.") from exc
        except anthropic.NotFoundError as exc:
            raise LLMError(f"Unknown Anthropic model '{settings.model}'") from exc
        except anthropic.RateLimitError as exc:
            raise LLMError("Anthropic rate limit reached - try again shortly") from exc
        except anthropic.APIStatusError as exc:
            raise LLMError(f"Anthropic API error {exc.status_code}: {_err(exc)}") from exc
        except anthropic.APIConnectionError as exc:
            raise LLMError("Could not reach the Anthropic API") from exc

    async def _stream_once(self, kwargs: dict[str, Any], use_fallbacks: bool) -> AsyncIterator[StreamEvent]:
        if use_fallbacks:
            ctx = self.client.beta.messages.stream(**kwargs, betas=[_FALLBACK_BETA], fallbacks="default")
        else:
            ctx = self.client.messages.stream(**kwargs)
        async with ctx as stream:
            async for event in stream:
                if event.type == "text":
                    yield StreamEvent("text", event.text)
                elif event.type == "thinking":
                    yield StreamEvent("thinking", event.thinking)
            final = await stream.get_final_message()
        yield StreamEvent("done", response=self._parse(final))

    @staticmethod
    def _parse(final: Any) -> LLMResponse:
        blocks = list(final.content)
        # After a mid-output fallback, drop model-internal blocks that precede the last fallback marker.
        fb = [i for i, b in enumerate(blocks) if getattr(b, "type", "") == "fallback"]
        if fb:
            cut = fb[-1]
            blocks = [
                b
                for i, b in enumerate(blocks)
                if i >= cut or getattr(b, "type", "") not in ("thinking", "redacted_thinking", "tool_use", "server_tool_use")
            ]
        text = "".join(getattr(b, "text", "") for b in blocks if getattr(b, "type", "") == "text")
        thinking = "\n".join(getattr(b, "thinking", "") or "" for b in blocks if getattr(b, "type", "") == "thinking").strip()
        stop = final.stop_reason or "end_turn"
        calls = [
            ToolCall(id=b.id, name=b.name, arguments=b.input if isinstance(b.input, dict) else {})
            for b in blocks
            if getattr(b, "type", "") == "tool_use"
        ]
        if stop == "refusal":
            calls = []
            text = text or "The model declined to respond to this request."
        elif stop == "max_tokens" and calls:
            calls = []  # truncated tool input - never execute it
            text = (text + "\n\n[Response truncated: max_tokens reached]").strip()
        usage = Usage(
            input_tokens=int(getattr(final.usage, "input_tokens", 0) or 0)
            + int(getattr(final.usage, "cache_read_input_tokens", 0) or 0)
            + int(getattr(final.usage, "cache_creation_input_tokens", 0) or 0),
            output_tokens=int(getattr(final.usage, "output_tokens", 0) or 0),
        )
        return LLMResponse(
            text=text,
            tool_calls=calls,
            stop_reason=stop,
            usage=usage,
            thinking=thinking,
            raw={"provider": "anthropic", "content": blocks},
        )


def _err(exc: Exception) -> str:
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        return str(body.get("error", {}).get("message") or body)[:500]
    return str(exc)[:500]
