from ..openai_compat import OpenAICompatLLM
from .spec import SPEC


class DeepSeekLLM(OpenAICompatLLM):
    """DeepSeek speaks the standard OpenAI chat protocol; nothing to override."""

    spec = SPEC
