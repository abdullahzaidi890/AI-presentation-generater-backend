from .openai_compat import OpenAICompatProvider


class GroqProvider(OpenAICompatProvider):
    # NOTE: Groq (groq.com) is NOT Grok (xAI).
    name = "groq"
