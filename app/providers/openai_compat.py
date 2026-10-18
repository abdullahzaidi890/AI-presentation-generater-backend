from ..config import PROVIDERS, get_settings
from .base import ProviderError, ProviderResult, post_json


class OpenAICompatProvider:
    """Shared code for Groq and xAI (both speak the OpenAI /chat/completions format)."""

    name = ""

    def is_configured(self) -> bool:
        return bool(get_settings().key_for(self.name))

    async def generate(self, system: str, user: str, model: str, json_mode: bool) -> ProviderResult:
        s = get_settings()
        key = s.key_for(self.name)
        if not key:
            raise ProviderError("not_configured", f"{self.name} has no API key.")
        body = {
            "model": model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": 0.4,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        data = await post_json(
            f"{PROVIDERS[self.name]['base_url']}/chat/completions",
            {"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            body,
            s.request_timeout_seconds,
        )
        try:
            text = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as e:
            raise ProviderError("malformed", "Provider response had an unexpected shape.") from e
        if not text.strip():
            raise ProviderError("malformed", "Provider returned empty text.")
        return ProviderResult(text, self.name, model)
