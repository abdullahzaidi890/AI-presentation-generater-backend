from ..config import PROVIDERS, get_settings
from .base import ProviderError, ProviderResult, post_json


class GeminiProvider:
    name = "gemini"

    def is_configured(self) -> bool:
        return bool(get_settings().gemini_api_key)

    async def generate(self, system: str, user: str, model: str, json_mode: bool) -> ProviderResult:
        s = get_settings()
        if not s.gemini_api_key:
            raise ProviderError("not_configured", "gemini has no API key.")
        gen_cfg = {"temperature": 0.4}
        if json_mode:
            gen_cfg["responseMimeType"] = "application/json"
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": gen_cfg,
        }
        data = await post_json(
            f"{PROVIDERS['gemini']['base_url']}/models/{model}:generateContent",
            {"x-goog-api-key": s.gemini_api_key, "Content-Type": "application/json"},  # key in header, not URL
            body,
            s.request_timeout_seconds,
        )
        try:
            parts = data["candidates"][0]["content"]["parts"]
            text = "".join(p.get("text", "") for p in parts)
        except (KeyError, IndexError, TypeError) as e:
            raise ProviderError("malformed", "Gemini response had an unexpected shape (maybe blocked).") from e
        if not text.strip():
            raise ProviderError("malformed", "Gemini returned empty text.")
        return ProviderResult(text, self.name, model)
