from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar, Iterator

from ..config import Settings
from .spec import ProviderSpec

Message = dict[str, str]  # {"role": "system" | "user" | "assistant", "content": "..."}


class LLM(ABC):
    """Base class of every provider. Subclasses declare `spec` and implement `stream` + `list_models`;
    `chat` is derived from `stream`."""

    spec: ClassVar[ProviderSpec]

    def __init__(self, settings: Settings):
        self.s = settings
        self.model = settings.llm_model or self.spec.default_model

    @abstractmethod
    def stream(self, messages: list[Message]) -> Iterator[str]: ...

    def chat(self, messages: list[Message]) -> str:
        return "".join(self.stream(messages))

    @abstractmethod
    def list_models(self) -> list[str]: ...
