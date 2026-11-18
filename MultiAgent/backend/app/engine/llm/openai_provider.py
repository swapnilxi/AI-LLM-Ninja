"""OpenAI and OpenAI-compatible providers (Groq, Gemini, OpenRouter, DeepSeek, Mistral, Ollama, custom)."""
from __future__ import annotations

import json
import secrets
from collections.abc import AsyncIterator
from typing import Any

import openai
from openai import AsyncOpenAI

from .base import LLMError, LLMProvider, LLMResponse, ModelSettings, StreamEvent, ToolCall, Usage

_REASONING_PREFIXES = ("gpt-5", "o1", "o3", "o4")
_USAGE_STREAM_PROVIDERS = {"openai", "openrouter", "groq", "deepseek", "mistral"}


class OpenAICompatProvider(LLMProvider):
    def __init__(self, key: str, api_key: str, base_url: str, default_headers: dict[str, str] | None = None) -> None:
        self.key = key
        self.client = AsyncOpenAI(
            api_key=api_key or "not-needed",
            base_url=base_url,
            max_retries=2,
            timeout=600,
            default_headers=default_headers or None,
        )

    @staticmethod
    def _convert(system: str, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = [{"role": "system", "content": system}] if system else []
        for m in messages:
            if m["role"] == "user":
                out.append({"role": "user", "content": m.get("content") or ""})
            elif m["role"] == "assistant":
                msg: dict[str, Any] = {"role": "assistant", "content": m.get("content") or None}
                if m.get("tool_calls"):
                    msg["tool_calls"] = [
                        {
                            "id": tc["id"],
                            "type": "function",
                            "function": {"name": tc["name"], "arguments": json.dumps(tc["arguments"])},
                        }
                        for tc in m["tool_calls"]
                    ]
                if msg["content"] is None and not msg.get("tool_calls"):
                    msg["content"] = ""
                out.append(msg)
            elif m["role"] == "tool":
                out.append({"role": "tool", "tool_call_id": m["tool_call_id"], "content": m.get("content") or ""})
        return out

    async def stream(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        settings: ModelSettings,
    ) -> AsyncIterator[StreamEvent]:
        model = settings.model
        bare = model.split("/")[-1]
        kwargs: dict[str, Any] = {"model": model, "messages": self._convert(system, messages), "stream": True}
        if tools:
            kwargs["tools"] = [
                {"type": "function", "function": {"name": t["name"], "description": t["description"][:4000], "parameters": t["parameters"]}}
                for t in tools
            ]
        if self.key == "openai" and bare.startswith(_REASONING_PREFIXES):
            kwargs["max_completion_tokens"] = settings.max_tokens
            effort = {"xhigh": "high", "max": "high"}.get(settings.effort, settings.effort or "medium")
            kwargs["reasoning_effort"] = effort
        else:
            kwargs["max_tokens"] = settings.max_tokens
            if settings.temperature is not None:
                kwargs["temperature"] = settings.temperature
        if self.key in _USAGE_STREAM_PROVIDERS:
            kwargs["stream_options"] = {"include_usage": True}

        text_parts: list[str] = []
        thinking_parts: list[str] = []
        calls: dict[int, dict[str, Any]] = {}
        usage = Usage()
        finish = "end_turn"
        try:
            stream = await self.client.chat.completions.create(**kwargs)
            async for chunk in stream:
                if getattr(chunk, "usage", None):
                    usage = Usage(
                        input_tokens=int(chunk.usage.prompt_tokens or 0),
                        output_tokens=int(chunk.usage.completion_tokens or 0),
                    )
                if not chunk.choices:
                    continue
                choice = chunk.choices[0]
                delta = choice.delta
                if delta is not None:
                    if delta.content:
                        text_parts.append(delta.content)
                        yield StreamEvent("text", delta.content)
                    reasoning = getattr(delta, "reasoning_content", None) or getattr(delta, "reasoning", None)
                    if isinstance(reasoning, str) and reasoning:
                        thinking_parts.append(reasoning)
                        if settings.show_thinking:
                            yield StreamEvent("thinking", reasoning)
                    for tc in delta.tool_calls or []:
                        idx = tc.index if tc.index is not None else len(calls)
                        slot = calls.setdefault(idx, {"id": "", "name": "", "args": ""})
                        if tc.id:
                            slot["id"] = tc.id
                        if tc.function is not None:
                            if tc.function.name:
                                slot["name"] += tc.function.name
                            if tc.function.arguments:
                                slot["args"] += tc.function.arguments
                if choice.finish_reason:
                    finish = choice.finish_reason
        except openai.AuthenticationError as exc:
            raise LLMError(f"{self.key} API key is invalid. Update it in Settings → Model providers.") from exc
        except openai.NotFoundError as exc:
            raise LLMError(f"Model '{model}' was not found on {self.key}") from exc
        except openai.RateLimitError as exc:
            raise LLMError(f"{self.key} rate limit reached - try again shortly") from exc
        except openai.APIStatusError as exc:
            raise LLMError(f"{self.key} API error {exc.status_code}: {str(exc)[:400]}") from exc
        except openai.APIConnectionError as exc:
            raise LLMError(f"Could not reach the {self.key} API") from exc

        tool_calls: list[ToolCall] = []
        for idx in sorted(calls):
            slot = calls[idx]
            if not slot["name"]:
                continue
            try:
                args = json.loads(slot["args"]) if slot["args"].strip() else {}
                if not isinstance(args, dict):
                    args = {"value": args}
            except json.JSONDecodeError:
                args = {"_invalid_json": slot["args"][:2000]}
            tool_calls.append(ToolCall(id=slot["id"] or f"call_{secrets.token_hex(6)}", name=slot["name"], arguments=args))
        if finish == "length" and tool_calls:
            tool_calls = []
        yield StreamEvent(
            "done",
            response=LLMResponse(
                text="".join(text_parts),
                tool_calls=tool_calls,
                stop_reason={"stop": "end_turn", "tool_calls": "tool_use", "length": "max_tokens"}.get(finish, finish),
                usage=usage,
                thinking="".join(thinking_parts),
            ),
        )
