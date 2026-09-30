from ..openai_compat import OpenAICompatLLM
from .spec import SPEC


class GroqLLM(OpenAICompatLLM):
    """Groq speaks the standard OpenAI chat protocol; nothing to override."""

    spec = SPEC
