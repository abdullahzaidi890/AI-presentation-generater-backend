"""Central configuration. Model IDs / endpoints live ONLY here (see PROVIDERS)."""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    groq_api_key: str = ""
    gemini_api_key: str = ""
    anthropic_api_key: str = ""
    xai_api_key: str = ""
    xai_model: str = "grok-4"
    author_name: str = "Syed Abdullah"  # shown in the UI and as a small footer in exports; set AUTHOR_NAME in .env to change

    fallback_order: str = "groq,gemini,claude"
    enable_fallback: bool = True
    request_timeout_seconds: float = 30.0
    max_upload_mb: int = 10
    max_context_chars: int = 24000
    database_url: str = f"sqlite:///{(ROOT / 'data' / 'app.db').as_posix()}"
    frontend_origin: str = "http://localhost:5173"

    def key_for(self, provider: str) -> str:
        return {
            "groq": self.groq_api_key,
            "gemini": self.gemini_api_key,
            "claude": self.anthropic_api_key,
            "xai": self.xai_api_key,
        }.get(provider, "")

    @property
    def fallback_list(self) -> list[str]:
        return [p.strip() for p in self.fallback_order.split(",") if p.strip()]


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


# Model IDs and endpoints. Verified against official docs (see README "Doc links").
PROVIDERS: dict[str, dict] = {
    "groq": {
        "label": "Groq",
        "base_url": "https://api.groq.com/openai/v1",  # OpenAI-compatible
        "models": ["openai/gpt-oss-120b"],
        "docs": "https://console.groq.com/docs/models",
        "key_url": "https://console.groq.com/keys",
    },
    "gemini": {
        "label": "Google Gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "models": ["gemini-3.5-flash"],
        "docs": "https://ai.google.dev/gemini-api/docs/models",
        "key_url": "https://aistudio.google.com/apikey",
    },
    "claude": {
        "label": "Anthropic Claude",
        "base_url": "https://api.anthropic.com/v1",
        "anthropic_version": "2023-06-01",
        "models": ["claude-sonnet-5-5", "claude-haiku-5-5"],
        "docs": "https://docs.claude.com/en/docs/about-claude/models/overview",
        "key_url": "https://console.anthropic.com/settings/keys",
    },
    "xai": {
        "label": "xAI Grok (optional)",
        "base_url": "https://api.x.ai/v1",
        "models": [],  # filled from XAI_MODEL; NOT verified by the author - check docs
        "docs": "https://docs.x.ai/docs/models",
        "key_url": "https://console.x.ai",
    },
    "mock": {
        "label": "Mock (offline demo)",
        "models": ["mock-1"],
        "docs": "",
        "key_url": "",
    },
}
