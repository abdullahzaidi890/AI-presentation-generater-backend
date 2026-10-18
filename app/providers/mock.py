"""Offline provider: valid canned output, no key, no network. Used for tests and demos."""
import json
import re

from .base import ProviderResult


def _field(user: str, key: str, default: str = "") -> str:
    m = re.search(rf"^{key}:\s*(.*)$", user, re.M)
    return m.group(1).strip() if m else default


class MockProvider:
    name = "mock"
    # Tests can set this to force bad output, e.g. ["not json", "{...}"] (consumed in order).
    scripted: list[str] | None = None

    def is_configured(self) -> bool:
        return True

    async def generate(self, system: str, user: str, model: str, json_mode: bool) -> ProviderResult:
        if MockProvider.scripted:
            return ProviderResult(MockProvider.scripted.pop(0), self.name, model or "mock-1")
        mode = _field(user, "MODE", "deck")
        topic = _field(user, "TOPIC", "Your topic")[:80] or "Your topic"
        if mode == "evaluate":
            out = {"relevance": 8, "logical_flow": 7, "clarity": 8, "topic_coverage": 7,
                   "comments": ["Mock estimate: flow is reasonable.", "Mock estimate: add a concrete example."]}
        elif mode == "slide":
            instr = _field(user, "INSTRUCTION")
            out = {"layout": "bullets", "title": f"{topic} - revised",
                   "bullets": ["Revised key point one", "Revised key point two", "Revised key point three"],
                   "speaker_notes": f"Mock regenerated slide. Instruction: {instr or 'none'}",
                   "visual_suggestion": "Simple icon row", "references": []}
        else:
            n = int(_field(user, "SLIDES", "6") or 6)
            lang = _field(user, "LANGUAGE", "English")
            slides = [{"layout": "title", "title": topic, "bullets": ["A short overview presentation"],
                       "speaker_notes": "Welcome the audience and state the goal.", "visual_suggestion": "Clean cover image",
                       "references": []}]
            body = max(n - 2, 1)
            for i in range(body):
                slides.append({
                    "layout": "bullets" if i % 3 else "two_column",
                    "title": f"{topic}: key idea {i + 1}",
                    "bullets": [f"Point {i + 1}.1 about {topic}", f"Point {i + 1}.2 with an example",
                                f"Point {i + 1}.3 and its impact"],
                    "speaker_notes": f"Explain key idea {i + 1} in two or three sentences.",
                    "visual_suggestion": "Simple diagram or chart",
                    "references": []})
            if n >= 2:
                slides.append({"layout": "closing", "title": "Summary and next steps",
                               "bullets": ["Recap the main ideas", "Suggest one next action", "Open for questions"],
                               "speaker_notes": "Summarize and invite questions.", "visual_suggestion": "", "references": []})
            out = {"title": topic, "language": lang, "slides": slides[:n] if n < 2 else slides}
        return ProviderResult(json.dumps(out), self.name, model or "mock-1")
