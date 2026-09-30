from __future__ import annotations

import json
from typing import Iterator

from ...http import ProviderError, request_json, stream_lines
from ..base import LLM, Message
from .spec import SPEC


class OllamaLLM(LLM):
    spec = SPEC

    @property
    def base_url(self) -> str:
        return getattr(self.s, self.spec.base_url_field).rstrip("/")

    def stream(self, messages: list[Message]) -> Iterator[str]:
        options: dict = {"temperature": self.s.llm_temperature}
        if self.s.llm_max_tokens:
            options["num_predict"] = self.s.llm_max_tokens
        body = {"model": self.model, "messages": messages, "stream": True, "options": options}
        try:
            for line in stream_lines("POST", f"{self.base_url}/api/chat", json=body):
                obj = json.loads(line)
                if "error" in obj:
                    raise ProviderError(obj["error"])
                text = (obj.get("message") or {}).get("content")
                if text:
                    yield text
                if obj.get("done"):
                    return
        except ProviderError as e:
            if "404" in str(e) and "not found" in str(e).lower():
                raise ProviderError(f"Model '{self.model}' is not installed. Run: ollama pull {self.model}") from e
            raise

    def list_models(self) -> list[str]:
        data = request_json("GET", f"{self.base_url}/api/tags", retries=0)
        return sorted(m["name"] for m in data.get("models", []))
