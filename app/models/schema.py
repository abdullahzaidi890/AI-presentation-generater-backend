"""Slide JSON schema = single source of truth (mirrored in frontend/src/types/schema.ts)."""
import json
import re
import uuid
from typing import Literal

from pydantic import BaseModel, Field, field_validator

Layout = Literal["title", "bullets", "two_column", "quote", "chart", "closing"]
LAYOUTS = ["title", "bullets", "two_column", "quote", "chart", "closing"]


class Slide(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    layout: Layout = "bullets"
    title: str = Field(max_length=200)
    bullets: list[str] = Field(default_factory=list, max_length=10)
    speaker_notes: str = Field(default="", max_length=4000)
    visual_suggestion: str = Field(default="", max_length=600)
    references: list[str] = Field(default_factory=list, max_length=10)

    @field_validator("bullets", "references")
    @classmethod
    def _strings(cls, v: list[str]) -> list[str]:
        out = []
        for item in v:
            if not isinstance(item, str):
                raise ValueError("list items must be strings")
            if len(item) > 400:
                raise ValueError("list item too long (>400 chars)")
            out.append(item)
        return out


class Deck(BaseModel):
    title: str = Field(max_length=200)
    language: str = Field(default="English", max_length=60)
    slides: list[Slide] = Field(min_length=1, max_length=40)


class GenerationSettings(BaseModel):
    topic: str = ""
    slides: int = Field(default=8, ge=3, le=30)
    audience: str = Field(default="General audience", max_length=200)
    language: str = Field(default="English", max_length=60)
    purpose: str = Field(default="Inform", max_length=200)
    tone: str = Field(default="Professional", max_length=100)
    theme: str = "minimal_academic"
    detail: Literal["brief", "standard", "detailed"] = "standard"
    speaker_notes: bool = True
    provider: str = "mock"
    model: str = ""


class PresentationIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: Deck
    settings: dict = Field(default_factory=dict)
    theme: str = "minimal_academic"


class PresentationRename(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class SlideRegenIn(BaseModel):
    deck_title: str = Field(max_length=200)
    slide: Slide
    instruction: str = Field(default="", max_length=500)
    provider: str
    model: str = ""
    language: str = "English"
    other_titles: list[str] = Field(default_factory=list, max_length=40)


class SchemaError(ValueError):
    pass


def extract_json(text: str) -> dict:
    """Strip code fences and parse the first JSON object. No silent fixing beyond that."""
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*", "", t)
    t = re.sub(r"\s*```$", "", t)
    start, end = t.find("{"), t.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise SchemaError("Response contained no JSON object")
    try:
        data = json.loads(t[start : end + 1])
    except json.JSONDecodeError as e:
        raise SchemaError(f"Invalid JSON: {e.msg} at position {e.pos}") from e
    if not isinstance(data, dict):
        raise SchemaError("Top-level JSON must be an object")
    return data


def parse_deck(text: str) -> Deck:
    from pydantic import ValidationError

    data = extract_json(text)
    try:
        deck = Deck.model_validate(data)
    except ValidationError as e:
        raise SchemaError(_short_errors(e)) from e
    for s in deck.slides:  # never trust model-provided ids
        s.id = str(uuid.uuid4())
    return deck


def parse_slide(text: str) -> Slide:
    from pydantic import ValidationError

    data = extract_json(text)
    if "slide" in data and isinstance(data["slide"], dict):
        data = data["slide"]
    try:
        slide = Slide.model_validate(data)
    except ValidationError as e:
        raise SchemaError(_short_errors(e)) from e
    slide.id = str(uuid.uuid4())
    return slide


def _short_errors(e) -> str:
    parts = []
    for err in e.errors()[:6]:
        loc = ".".join(str(x) for x in err["loc"])
        parts.append(f"{loc}: {err['msg']}")
    return "; ".join(parts)
