from ..config import PROVIDERS, get_settings
from .base import ProviderError, ProviderResult, post_json


class ClaudeProvider:
    name = "claude"

    def is_configured(self) -> bool:
        return bool(get_settings().anthropic_api_key)

    async def generate(self, system: str, user: str, model: str, json_mode: bool) -> ProviderResult:
        s = get_settings()
        if not s.anthropic_api_key:
            raise ProviderError("not_configured", "claude has no API key.")
        cfg = PROVIDERS["claude"]
        sys_prompt = system + ("\nReturn ONLY one JSON object, no other text." if json_mode else "")
        body = {
            "model": model,
            "max_tokens": 8000,
            "system": sys_prompt,
            "messages": [{"role": "user", "content": user}],
        }
        data = await post_json(
            f"{cfg['base_url']}/messages",
            {
                "x-api-key": s.anthropic_api_key,
                "anthropic-version": cfg["anthropic_version"],
                "content-type": "application/json",
            },
            body,
            s.request_timeout_seconds,
        )
        try:
            text = "".join(b.get("text", "") for b in data["content"] if b.get("type") == "text")
        except (KeyError, TypeError) as e:
            raise ProviderError("malformed", "Claude response had an unexpected shape.") from e
        if not text.strip():
            raise ProviderError("malformed", "Claude returned empty text.")
        return ProviderResult(text, self.name, model)
