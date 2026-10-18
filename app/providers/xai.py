from .openai_compat import OpenAICompatProvider


class XAIProvider(OpenAICompatProvider):
    name = "xai"  # optional, only shown when XAI_API_KEY is set
