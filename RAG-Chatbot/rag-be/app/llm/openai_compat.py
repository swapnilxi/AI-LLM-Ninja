"""Shared implementation of the OpenAI-style chat API (`POST {base}/chat/completions`, SSE streaming).

Not a provider itself: OpenAI, Groq, DeepSeek and OpenRouter each subclass it in their own folder and
override only what differs (see e.g. app/llm/openai/llm.py for the reasoning-model quirks).
"""
from __future__ import annotations

import json
from typing import Iterator

from ..http import ProviderError, request_json, stream_lines
from .base import LLM, Message


class OpenAICompatLLM(LLM):
    @property
    def base_url(self) -> str:
        return getattr(self.s, self.spec.base_url_field).rstrip("/")

    @property
    def api_key(self) -> str:
        return getattr(self.s, self.spec.key_field)

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            raise ProviderError(f"{self.spec.name} API key is not set (add it in Settings or .env)")
        return {"Authorization": f"Bearer {self.api_key}"}

    def _payload(self, messages: list[Message], stream: bool) -> dict:
        body: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": self.s.llm_temperature,
            "stream": stream,
        }
        if self.s.llm_max_tokens:
            body["max_tokens"] = self.s.llm_max_tokens
        return body

    def stream(self, messages: list[Message]) -> Iterator[str]:
        url = f"{self.base_url}/chat/completions"
        for line in stream_lines("POST", url, headers=self._headers(), json=self._payload(messages, True)):
            if not line.startswith("data:"):
                continue  # SSE comments / keep-alives (OpenRouter sends ": OPENROUTER PROCESSING")
            data = line[5:].strip()
            if data == "[DONE]":
                return
            try:
                obj = json.loads(data)
            except ValueError:
                continue
            if "error" in obj:
                raise ProviderError(str(obj["error"].get("message", obj["error"])))
            for choice in obj.get("choices", []):
                text = (choice.get("delta") or {}).get("content")
                if text:
                    yield text

    def list_models(self) -> list[str]:
        data = request_json("GET", f"{self.base_url}/models", headers=self._headers())
        return sorted(m["id"] for m in data.get("data", []))
