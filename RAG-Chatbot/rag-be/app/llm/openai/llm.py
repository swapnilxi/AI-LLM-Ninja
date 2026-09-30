from __future__ import annotations

from ..base import Message
from ..openai_compat import OpenAICompatLLM
from .spec import SPEC

REASONING_PREFIXES = ("o1", "o3", "o4", "gpt-5")


class OpenAILLM(OpenAICompatLLM):
    spec = SPEC

    @staticmethod
    def is_reasoning(model: str) -> bool:
        return model.startswith(REASONING_PREFIXES)

    def _payload(self, messages: list[Message], stream: bool) -> dict:
        body = super()._payload(messages, stream)
        if "max_tokens" in body:  # OpenAI's current name for the output cap
            body["max_completion_tokens"] = body.pop("max_tokens")
        if self.is_reasoning(self.model):
            body.pop("temperature", None)  # reasoning models only accept the default
        return body

    def list_models(self) -> list[str]:
        # /models also returns embeddings, tts, whisper, dall-e...: keep chat-capable families
        return [m for m in super().list_models() if m.startswith(("gpt", "chatgpt", *REASONING_PREFIXES))]
