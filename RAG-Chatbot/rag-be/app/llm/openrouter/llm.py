from ..openai_compat import OpenAICompatLLM
from .spec import SPEC


class OpenRouterLLM(OpenAICompatLLM):
    spec = SPEC

    def _headers(self) -> dict[str, str]:
        # optional attribution headers OpenRouter shows on its rankings page
        return {**super()._headers(), "X-Title": "RAG Chatbot"}
