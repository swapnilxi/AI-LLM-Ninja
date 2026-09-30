from __future__ import annotations

import json
from typing import Iterator

from ...http import ProviderError, request_json, stream_lines
from ..base import LLM, Message
from .spec import API, SPEC


class GeminiLLM(LLM):
    spec = SPEC

    def _headers(self) -> dict[str, str]:
        if not self.s.gemini_api_key:
            raise ProviderError("Gemini API key is not set (add it in Settings or .env)")
        return {"x-goog-api-key": self.s.gemini_api_key}

    def _payload(self, messages: list[Message]) -> dict:
        system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
        contents = [
            {"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["content"]}]}
            for m in messages
            if m["role"] != "system"
        ]
        gen: dict = {"temperature": self.s.llm_temperature}
        if self.s.llm_max_tokens:
            gen["maxOutputTokens"] = self.s.llm_max_tokens
        body: dict = {"contents": contents, "generationConfig": gen}
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        return body

    def stream(self, messages: list[Message]) -> Iterator[str]:
        model = self.model.removeprefix("models/")
        url = f"{API}/models/{model}:streamGenerateContent?alt=sse"
        for line in stream_lines("POST", url, headers=self._headers(), json=self._payload(messages)):
            if not line.startswith("data:"):
                continue
            obj = json.loads(line[5:])
            if obj.get("promptFeedback", {}).get("blockReason"):
                raise ProviderError(f"Gemini blocked the prompt: {obj['promptFeedback']['blockReason']}")
            for cand in obj.get("candidates", []):
                for part in (cand.get("content") or {}).get("parts", []):
                    if part.get("text") and not part.get("thought"):
                        yield part["text"]

    def list_models(self) -> list[str]:
        data = request_json("GET", f"{API}/models?pageSize=200", headers=self._headers())
        return sorted(
            m["name"].removeprefix("models/")
            for m in data.get("models", [])
            if "generateContent" in m.get("supportedGenerationMethods", [])
        )
