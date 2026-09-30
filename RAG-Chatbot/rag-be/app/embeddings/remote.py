"""Embedders that call an HTTP API: Gemini (online) and Ollama (local server)."""
from __future__ import annotations

from ..http import ProviderError, request_json
from .base import Embedder, Vector

GEMINI_API = "https://generativelanguage.googleapis.com/v1beta"


class GeminiEmbedder(Embedder):
    provider = "gemini"
    default_model = "gemini-embedding-001"
    batch_size = 50

    def __init__(self, settings):
        super().__init__(settings)
        # 768 keeps pgvector HNSW indexes usable (limit 2000) and storage small; native size is 3072.
        if not settings.embedding_dimensions:
            settings = settings.model_copy(update={"embedding_dimensions": 768})
            self.s = settings

    def _headers(self) -> dict[str, str]:
        if not self.s.gemini_api_key:
            raise ProviderError("Gemini API key is not set (add it in Settings or .env)")
        return {"x-goog-api-key": self.s.gemini_api_key}

    def _embed(self, texts: list[str], *, query: bool) -> list[Vector]:
        model = self.model.removeprefix("models/")
        task = "RETRIEVAL_QUERY" if query else "RETRIEVAL_DOCUMENT"
        reqs = [
            {
                "model": f"models/{model}",
                "content": {"parts": [{"text": t}]},
                "taskType": task,
                "outputDimensionality": self.s.embedding_dimensions,
            }
            for t in texts
        ]
        data = request_json(
            "POST", f"{GEMINI_API}/models/{model}:batchEmbedContents", headers=self._headers(), json={"requests": reqs}
        )
        return [e["values"] for e in data["embeddings"]]

    def list_models(self) -> list[str]:
        data = request_json("GET", f"{GEMINI_API}/models?pageSize=200", headers=self._headers())
        return sorted(
            m["name"].removeprefix("models/")
            for m in data.get("models", [])
            if "embedContent" in m.get("supportedGenerationMethods", [])
        )


class OpenAIEmbedder(Embedder):
    provider = "openai"
    default_model = "text-embedding-3-small"  # 1536-dim; supports `dimensions` shortening
    batch_size = 100

    def _embed(self, texts: list[str], *, query: bool) -> list[Vector]:
        if not self.s.openai_api_key:
            raise ProviderError("OpenAI API key is not set (add it in Settings or .env)")
        body: dict = {"model": self.model, "input": texts}
        if self.s.embedding_dimensions and self.model.startswith("text-embedding-3"):
            body["dimensions"] = self.s.embedding_dimensions
        data = request_json(
            "POST", f"{self.s.openai_base_url.rstrip('/')}/embeddings",
            headers={"Authorization": f"Bearer {self.s.openai_api_key}"}, json=body,
        )
        return [d["embedding"] for d in sorted(data["data"], key=lambda d: d["index"])]

    def list_models(self) -> list[str]:
        data = request_json(
            "GET", f"{self.s.openai_base_url.rstrip('/')}/models",
            headers={"Authorization": f"Bearer {self.s.openai_api_key}"},
        )
        return sorted(m["id"] for m in data.get("data", []) if "embedding" in m["id"])


class OllamaEmbedder(Embedder):
    provider = "ollama"
    default_model = "nomic-embed-text"

    @property
    def base_url(self) -> str:
        return self.s.ollama_base_url.rstrip("/")

    def _embed(self, texts: list[str], *, query: bool) -> list[Vector]:
        try:
            data = request_json("POST", f"{self.base_url}/api/embed", json={"model": self.model, "input": texts})
        except ProviderError as e:
            if "not found" in str(e).lower():
                raise ProviderError(f"Model '{self.model}' is not installed. Run: ollama pull {self.model}") from e
            raise
        return data["embeddings"]

    def list_models(self) -> list[str]:
        data = request_json("GET", f"{self.base_url}/api/tags", retries=0)
        return sorted(m["name"] for m in data.get("models", []))
