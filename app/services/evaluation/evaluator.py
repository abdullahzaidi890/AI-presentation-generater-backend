"""Deterministic, rule-based quality checks. No AI involved."""
import re

CONCLUSION_WORDS = ("conclusion", "summary", "takeaway", "next step", "recap", "thank", "questions", "wrap")


def _norm(t: str) -> set[str]:
    return set(re.findall(r"\w+", t.lower()))


def _similar(a: str, b: str) -> bool:
    A, B = _norm(a), _norm(b)
    if not A or not B:
        return False
    return len(A & B) / len(A | B) >= 0.8


def _check(id_, label, status, detail, suggestion=""):
    return {"id": id_, "label": label, "status": status, "detail": detail, "suggestion": suggestion}


def evaluate_rules(deck: dict, requested_slides: int | None = None, notes_expected: bool = True) -> dict:
    slides = deck["slides"]
    checks = []
    n = len(slides)

    if requested_slides:
        ok = n == requested_slides
        checks.append(_check("slide_count", "Slide count", "pass" if ok else "warn",
                             f"{n} slides (requested {requested_slides})",
                             "" if ok else "Add or delete slides to match the requested count."))
    else:
        checks.append(_check("slide_count", "Slide count", "pass", f"{n} slides"))

    content = [s for s in slides if s.get("layout") in ("bullets", "two_column", "chart")]
    bad = [i + 1 for i, s in enumerate(content) if not 3 <= len(s.get("bullets", [])) <= 6]
    bad_nums = [slides.index(s) + 1 for s in content if not 3 <= len(s.get("bullets", [])) <= 6]
    checks.append(_check("bullets", "Bullets per slide (3-6)", "pass" if not bad else "warn",
                         "All content slides are within 3-6 bullets" if not bad else f"Slides outside range: {bad_nums}",
                         "" if not bad else "Keep 3-6 bullets per content slide."))

    long_titles = [i + 1 for i, s in enumerate(slides) if len(s["title"]) > 80]
    long_bul = [i + 1 for i, s in enumerate(slides) if any(len(b) > 140 for b in s.get("bullets", []))]
    ok = not long_titles and not long_bul
    detail = "Titles <= 80 and bullets <= 140 characters" if ok else (
        f"Long titles on slides {long_titles}; long bullets on slides {long_bul}")
    checks.append(_check("text_length", "Text length", "pass" if ok else "warn", detail,
                         "" if ok else "Shorten long titles/bullets; slides should be scannable."))

    seen: list[tuple[int, str]] = []
    dups = set()
    for i, s in enumerate(slides):
        for b in [s["title"]] + s.get("bullets", []):
            for j, prev in seen:
                if j != i and _similar(b, prev):
                    dups.add((j + 1, i + 1))
            seen.append((i, b))
    checks.append(_check("repetition", "Repetition", "pass" if not dups else "warn",
                         "No duplicate or near-duplicate text" if not dups else
                         f"Similar text between slides: {sorted(dups)[:5]}",
                         "" if not dups else "Merge or rewrite repeated points."))

    first, last = slides[0], slides[-1]
    has_intro = first.get("layout") == "title" or "intro" in first["title"].lower() or "agenda" in first["title"].lower()
    checks.append(_check("intro", "Introduction present", "pass" if has_intro else "fail",
                         "First slide is an intro/title slide" if has_intro else "First slide is not an intro",
                         "" if has_intro else "Start with a title or introduction slide."))
    has_end = last.get("layout") == "closing" or any(w in last["title"].lower() for w in CONCLUSION_WORDS)
    checks.append(_check("conclusion", "Conclusion present", "pass" if has_end else "fail",
                         "Last slide is a conclusion/summary" if has_end else "Last slide is not a conclusion",
                         "" if has_end else "End with a summary or next steps slide."))

    if notes_expected:
        missing = [i + 1 for i, s in enumerate(slides) if not s.get("speaker_notes", "").strip()]
        checks.append(_check("notes", "Speaker notes", "pass" if not missing else "warn",
                             "Every slide has notes" if not missing else f"Missing notes on slides {missing}",
                             "" if not missing else "Add speaker notes or regenerate those slides."))

    weights = {"pass": 1.0, "warn": 0.5, "fail": 0.0}
    score = round(100 * sum(weights[c["status"]] for c in checks) / len(checks))
    return {"score": score, "checks": checks, "kind": "rule-based (computed)"}
