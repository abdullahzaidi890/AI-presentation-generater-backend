import json
import logging
import re
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response, StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import PROVIDERS, get_settings
from ..db.database import Presentation, get_db
from ..models.schema import (Deck, GenerationSettings, PresentationIn, PresentationRename, SlideRegenIn)
from ..providers.base import ProviderError
from ..providers.registry import default_model, get_provider, list_providers
from ..services.evaluation.evaluator import evaluate_rules
from ..services.export.pdf_export import build_html, build_pdf
from ..services.export.pptx_export import build_pptx
from ..services.export.themes import THEMES
from ..services.generation.generator import GenerationError, ai_estimate, generate_deck, regenerate_slide
from ..services.parsing.parser import DocumentError, parse_document

log = logging.getLogger("api")
router = APIRouter(prefix="/api")


@router.get("/health")
def health():
    return {"status": "ok", "mode": "local single-user mode"}


@router.get("/config")
def app_config():
    return {"author": get_settings().author_name}


@router.get("/providers")
def providers():
    s = get_settings()
    return {"providers": list_providers(), "fallback_enabled": s.enable_fallback, "fallback_order": s.fallback_list}


@router.get("/themes")
def themes():
    return {"themes": [{"id": k, **v} for k, v in THEMES.items()]}


@router.post("/providers/{name}/test")
async def test_provider(name: str):
    """Real connectivity test with a tiny prompt. Reports the truthful result, never the key."""
    p = get_provider(name)
    if not p or name not in PROVIDERS:
        raise HTTPException(404, "Unknown provider")
    if not p.is_configured():
        return {"ok": False, "kind": "not_configured", "message": "No API key configured for this provider."}
    try:
        res = await p.generate("Reply with the single word OK.", "MODE: ping\nSay OK.", default_model(name), False)
        return {"ok": True, "model": res.model, "message": "Connection works."}
    except ProviderError as e:
        return {"ok": False, "kind": e.kind, "message": e.message}


# ---------- generation ----------
@router.post("/generate")
async def generate(
    topic: str = Form(""), slides: int = Form(8), audience: str = Form("General audience"),
    language: str = Form("English"), purpose: str = Form("Inform"), tone: str = Form("Professional"),
    theme: str = Form("minimal_academic"), detail: str = Form("standard"), speaker_notes: bool = Form(True),
    provider: str = Form("mock"), model: str = Form(""), file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    s = get_settings()
    try:
        gs = GenerationSettings(topic=topic.strip(), slides=slides, audience=audience, language=language,
                                purpose=purpose, tone=tone, theme=theme if theme in THEMES else "minimal_academic",
                                detail=detail, speaker_notes=speaker_notes, provider=provider, model=model.strip())
    except ValueError as e:
        raise HTTPException(422, f"Invalid settings: {str(e)[:200]}")
    if len(gs.topic) > 2000:
        raise HTTPException(422, "Topic is too long (max 2000 characters).")
    raw, fname = b"", ""
    if file is not None and file.filename:
        max_bytes = s.max_upload_mb * 1024 * 1024
        raw = await file.read(max_bytes + 1)  # never read more than the limit + 1 byte
        fname = file.filename
    if not gs.topic and not raw:
        raise HTTPException(422, "Enter a topic or upload a document.")

    async def stream():
        def ev(d):
            return json.dumps(d) + "\n"
        events: list[dict] = []

        async def progress(e):
            events.append(e)

        try:
            doc_text, notice = None, []
            if raw:
                yield ev({"step": "reading", "detail": "Reading document"})
                parsed = parse_document(fname, raw, s.max_upload_mb * 1024 * 1024, s.max_context_chars)
                doc_text = parsed.text
                if parsed.truncated:
                    notice.append("The document was long, so a representative part of it was used.")
            import asyncio
            task = asyncio.create_task(generate_deck(gs, doc_text, progress))
            sent = 0
            while not task.done():
                await asyncio.sleep(0.05)
                while sent < len(events):
                    yield ev(events[sent]); sent += 1
            while sent < len(events):
                yield ev(events[sent]); sent += 1
            out = task.result()
            yield ev({"step": "saving"})
            deck: Deck = out.result
            row = Presentation(title=deck.title[:200], content_json=deck.model_dump_json(),
                               settings_json=gs.model_dump_json(), theme=gs.theme, provider=out.provider,
                               model=out.model, fallback_used=out.fallback_used)
            db.add(row); db.commit()
            yield ev({"done": True, "presentation": row.to_dict(), "notices": notice + out.notices,
                      "provider": out.provider, "model": out.model, "fallback_used": out.fallback_used})
        except DocumentError as e:
            yield ev({"error": str(e), "kind": "document"})
        except GenerationError as e:
            yield ev({"error": e.message, "kind": "generation", "attempts": e.attempts})
        except Exception:
            log.exception("generate failed")
            yield ev({"error": "Something went wrong while generating. Check the server log.", "kind": "internal"})

    return StreamingResponse(stream(), media_type="application/x-ndjson")


@router.post("/generate/slide")
async def regen_slide(body: SlideRegenIn):
    try:
        out = await regenerate_slide(body)
    except GenerationError as e:
        raise HTTPException(e.status, e.message)
    return {"slide": out.result.model_dump(), "provider": out.provider, "model": out.model,
            "fallback_used": out.fallback_used, "notices": out.notices}


# ---------- CRUD ----------
def _get(db: Session, pid: str) -> Presentation:
    row = db.get(Presentation, pid)
    if not row:
        raise HTTPException(404, "Presentation not found")
    return row


@router.get("/presentations")
def list_presentations(q: str = "", provider: str = "", db: Session = Depends(get_db)):
    stmt = select(Presentation).order_by(Presentation.updated_at.desc())
    if q:
        stmt = stmt.where(Presentation.title.ilike(f"%{q[:100]}%"))
    if provider:
        stmt = stmt.where(Presentation.provider == provider)
    return {"items": [r.to_dict(with_content=False) for r in db.scalars(stmt)]}


@router.get("/stats")
def stats(db: Session = Depends(get_db)):
    total = db.scalar(select(func.count(Presentation.id))) or 0
    rows = db.scalars(select(Presentation)).all()
    slides = sum(r.to_dict(False)["slide_count"] for r in rows)
    return {"presentations": total, "slides": slides, "providers_used": len({r.provider for r in rows})}


@router.get("/presentations/{pid}")
def get_presentation(pid: str, db: Session = Depends(get_db)):
    return _get(db, pid).to_dict()


@router.post("/presentations")
def create_presentation(body: PresentationIn, db: Session = Depends(get_db)):
    row = Presentation(title=body.title, content_json=body.content.model_dump_json(),
                       settings_json=json.dumps(body.settings), theme=body.theme if body.theme in THEMES else "minimal_academic")
    db.add(row); db.commit()
    return row.to_dict()


@router.put("/presentations/{pid}")
def update_presentation(pid: str, body: PresentationIn, db: Session = Depends(get_db)):
    row = _get(db, pid)
    row.title = body.title
    row.content_json = body.content.model_dump_json()
    row.theme = body.theme if body.theme in THEMES else row.theme
    if body.settings:
        row.settings_json = json.dumps(body.settings)
    db.commit()
    return row.to_dict()


@router.patch("/presentations/{pid}")
def rename_presentation(pid: str, body: PresentationRename, db: Session = Depends(get_db)):
    row = _get(db, pid)
    row.title = body.title
    db.commit()
    return row.to_dict(with_content=False)


@router.post("/presentations/{pid}/duplicate")
def duplicate_presentation(pid: str, db: Session = Depends(get_db)):
    row = _get(db, pid)
    new = Presentation(title=(row.title + " (copy)")[:200], content_json=row.content_json,
                       settings_json=row.settings_json, theme=row.theme, provider=row.provider,
                       model=row.model, fallback_used=row.fallback_used)
    db.add(new); db.commit()
    return new.to_dict(with_content=False)


@router.delete("/presentations/{pid}")
def delete_presentation(pid: str, db: Session = Depends(get_db)):
    row = _get(db, pid)
    db.delete(row); db.commit()
    return {"deleted": True}


# ---------- export / evaluation ----------
def _fname(title: str, ext: str) -> str:
    base = re.sub(r"[^\w\- ]", "", title).strip().replace(" ", "_")[:60] or "presentation"
    return f"{base}.{ext}"


def _disp(title: str, ext: str) -> str:
    return f"attachment; filename=\"presentation.{ext}\"; filename*=UTF-8''{quote(_fname(title, ext))}"


@router.get("/presentations/{pid}/export/pptx")
def export_pptx(pid: str, db: Session = Depends(get_db)):
    row = _get(db, pid)
    try:
        data = build_pptx(json.loads(row.content_json), row.theme, get_settings().author_name)
    except Exception:
        log.exception("pptx export failed")
        raise HTTPException(500, "PPTX export failed.")
    return Response(data, media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    headers={"Content-Disposition": _disp(row.title, "pptx")})


@router.get("/presentations/{pid}/export/pdf")
def export_pdf(pid: str, db: Session = Depends(get_db)):
    row = _get(db, pid)
    try:
        data = build_pdf(json.loads(row.content_json), row.theme, get_settings().author_name)
    except Exception:
        log.exception("pdf export failed")
        raise HTTPException(500, "PDF export failed.")
    return Response(data, media_type="application/pdf", headers={"Content-Disposition": _disp(row.title, "pdf")})


@router.get("/presentations/{pid}/export/html", response_class=HTMLResponse)
def export_html(pid: str, db: Session = Depends(get_db)):
    row = _get(db, pid)
    return HTMLResponse(build_html(json.loads(row.content_json), row.theme, get_settings().author_name))


@router.post("/presentations/{pid}/evaluate")
async def evaluate(pid: str, ai: bool = False, provider: str = "", model: str = "", db: Session = Depends(get_db)):
    row = _get(db, pid)
    deck = json.loads(row.content_json)
    settings = json.loads(row.settings_json or "{}")
    result = evaluate_rules(deck, settings.get("slides"), settings.get("speaker_notes", True))
    result["ai"] = None
    if ai:
        prov = provider or row.provider or "mock"
        try:
            from ..services.generation.generator import validate_request
            validate_request(prov, model)
            result["ai"] = await ai_estimate(Deck.model_validate(deck), prov, model)
        except GenerationError as e:
            result["ai_error"] = e.message
    return result
