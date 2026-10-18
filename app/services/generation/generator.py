"""Generation with validation, ONE controlled retry, and honest fallback reporting."""
import logging
from dataclasses import dataclass, field

from ...config import PROVIDERS, get_settings
from ...models.schema import Deck, GenerationSettings, SchemaError, Slide, SlideRegenIn, parse_deck, parse_slide
from ...providers.base import ProviderError
from ...providers.registry import default_model, get_provider
from .prompts import (EVAL_SYSTEM, SLIDE_SYSTEM, SYSTEM_PROMPT, build_deck_prompt, build_slide_prompt)

log = logging.getLogger("generation")


class GenerationError(Exception):
    def __init__(self, message: str, attempts: list[dict], status: int = 502):
        super().__init__(message)
        self.message = message
        self.attempts = attempts
        self.status = status


@dataclass
class Outcome:
    result: object
    provider: str
    model: str
    fallback_used: bool = False
    notices: list[str] = field(default_factory=list)
    attempts: list[dict] = field(default_factory=list)


def provider_order(requested: str) -> list[str]:
    """Requested provider first; then configured fallbacks (never mock unless it was requested)."""
    s = get_settings()
    order = [requested]
    if s.enable_fallback and requested != "mock":
        for name in s.fallback_list:
            p = get_provider(name)
            if name != requested and name != "mock" and p and p.is_configured():
                order.append(name)
    return order


def validate_request(requested: str, model: str) -> str:
    p = get_provider(requested)
    if not p or requested not in PROVIDERS:
        raise GenerationError("Unknown provider.", [], 400)
    if not p.is_configured():
        raise GenerationError(f"{PROVIDERS[requested]['label']} is not configured. Add its key to .env.", [], 400)
    return model or default_model(requested)


async def _call_with_retry(provider, system, user, model, parser, progress):
    """Call provider, validate. On invalid output do exactly ONE retry that includes the validation error."""
    res = await provider.generate(system, user, model, True)
    try:
        return res, parser(res.text)
    except SchemaError as first:
        if progress:
            await progress({"step": "retrying", "detail": "Output was invalid, retrying once"})
        retry_user = (user + "\n\nYour previous answer was invalid: " + str(first)[:500] +
                      "\nReturn ONLY a corrected JSON object that follows the schema exactly.")
        res = await provider.generate(system, retry_user, model, True)
        try:
            return res, parser(res.text)
        except SchemaError as second:
            raise ProviderError("malformed", f"Model returned invalid output twice ({str(second)[:200]})") from second


async def _run(requested, model, system, user, parser, progress=None) -> Outcome:
    model_requested = validate_request(requested, model)
    attempts: list[dict] = []
    for i, name in enumerate(provider_order(requested)):
        provider = get_provider(name)
        use_model = model_requested if name == requested else default_model(name)
        if progress:
            await progress({"step": "generating", "provider": name, "model": use_model})
        try:
            res, parsed = await _call_with_retry(provider, system, user, use_model, parser, progress)
            if progress:
                await progress({"step": "validating"})
            out = Outcome(parsed, name, use_model, fallback_used=(i > 0), attempts=attempts)
            if i > 0:
                failed = attempts[-1]
                out.notices.append(
                    f"{PROVIDERS[requested]['label']} failed ({failed['kind']}). Result produced by "
                    f"{PROVIDERS[name]['label']} instead.")
            return out
        except ProviderError as e:
            log.warning("provider %s failed: %s", name, e.kind)
            attempts.append({"provider": name, "kind": e.kind, "message": e.message})
    last = attempts[-1]
    raise GenerationError(f"Generation failed: {last['message']}", attempts)


async def generate_deck(s: GenerationSettings, document_text: str | None, progress=None) -> Outcome:
    out = await _run(s.provider, s.model, SYSTEM_PROMPT, build_deck_prompt(s, document_text), parse_deck, progress)
    deck: Deck = out.result
    if not s.speaker_notes:
        for sl in deck.slides:
            sl.speaker_notes = ""
    return out


async def regenerate_slide(r: SlideRegenIn) -> Outcome:
    out = await _run(r.provider, r.model, SLIDE_SYSTEM, build_slide_prompt(r), parse_slide)
    new: Slide = out.result
    new.id = r.slide.id  # keep position/identity in the editor
    return out


async def ai_estimate(deck: Deck, provider: str, model: str) -> dict:
    import json

    def parser(text):
        from ...models.schema import extract_json
        d = extract_json(text)
        for k in ("relevance", "logical_flow", "clarity", "topic_coverage"):
            v = d.get(k)
            if not isinstance(v, (int, float)) or not 0 <= v <= 10:
                raise SchemaError(f"{k} must be a number 0-10")
        d["comments"] = [str(c)[:300] for c in d.get("comments", [])][:5]
        return d

    user = "MODE: evaluate\nTOPIC: " + deck.title + "\n" + json.dumps(deck.model_dump(), ensure_ascii=False)[:20000]
    out = await _run(provider, model, EVAL_SYSTEM, user, parser)
    return {"scores": out.result, "provider": out.provider, "model": out.model,
            "label": "AI estimate, not verified"}
