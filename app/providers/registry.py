from ..config import PROVIDERS, get_settings
from .claude import ClaudeProvider
from .gemini import GeminiProvider
from .groq import GroqProvider
from .mock import MockProvider
from .xai import XAIProvider

_INSTANCES = {"groq": GroqProvider(), "gemini": GeminiProvider(), "claude": ClaudeProvider(),
              "xai": XAIProvider(), "mock": MockProvider()}


def get_provider(name: str):
    return _INSTANCES.get(name)


def models_for(name: str) -> list[str]:
    if name == "xai":
        return [get_settings().xai_model]
    return PROVIDERS[name]["models"]


def default_model(name: str) -> str:
    return models_for(name)[0]


def list_providers() -> list[dict]:
    out = []
    for name, cfg in PROVIDERS.items():
        configured = _INSTANCES[name].is_configured()
        if name == "xai" and not configured:
            continue  # optional provider: only shown when a key exists
        out.append({
            "id": name, "label": cfg["label"], "configured": configured, "models": models_for(name),
            "docs": cfg.get("docs", ""), "key_url": cfg.get("key_url", ""),
            "tooltip": "" if configured else f"Not configured: add the key to .env and restart the backend.",
        })
    return out
