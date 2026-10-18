"""PDF (ReportLab, 16:9 pages) + print-friendly HTML view."""
import html
import io
import os

from reportlab.lib.colors import Color
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.lib.utils import simpleSplit

from .themes import get_theme, hex_to_rgb

PW, PH = 960.0, 540.0  # points (16:9)
_FONT_CACHE: dict = {}


def _fonts(family: str) -> tuple[str, str, bool]:
    """Return (regular, bold, unicode_ok). Tries a system TTF for wider character support."""
    if family in _FONT_CACHE:
        return _FONT_CACHE[family]
    cands = {
        "sans": [("C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/segoeuib.ttf"),
                 ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
                 ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")],
        "serif": [("C:/Windows/Fonts/georgia.ttf", "C:/Windows/Fonts/georgiab.ttf"),
                  ("C:/Windows/Fonts/times.ttf", "C:/Windows/Fonts/timesbd.ttf"),
                  ("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf")],
    }[family]
    for reg, bold in cands:
        if os.path.exists(reg) and os.path.exists(bold):
            try:
                rn, bn = f"T-{family}-{os.path.basename(reg)}", f"T-{family}-{os.path.basename(bold)}"
                pdfmetrics.registerFont(TTFont(rn, reg))
                pdfmetrics.registerFont(TTFont(bn, bold))
                _FONT_CACHE[family] = (rn, bn, True)
                return _FONT_CACHE[family]
            except Exception:
                continue
    _FONT_CACHE[family] = (("Times-Roman", "Times-Bold", False) if family == "serif" else ("Helvetica", "Helvetica-Bold", False))
    return _FONT_CACHE[family]


def _safe(text: str, unicode_ok: bool) -> str:
    if unicode_ok:
        return text
    return text.encode("latin-1", "replace").decode("latin-1")  # built-in fonts: Latin-1 only


def _col(h, alpha=1):
    r, g, b = hex_to_rgb(h)
    return Color(r / 255, g / 255, b / 255, alpha)


def _background(c, theme):
    if len(theme["bg"]) == 1:
        c.setFillColor(_col(theme["bg"][0]))
        c.rect(0, 0, PW, PH, stroke=0, fill=1)
    else:  # simple vertical gradient with thin strips
        r1, g1, b1 = hex_to_rgb(theme["bg"][0])
        r2, g2, b2 = hex_to_rgb(theme["bg"][1])
        steps = 60
        for i in range(steps):
            t = i / (steps - 1)
            c.setFillColor(Color((r1 + (r2 - r1) * t) / 255, (g1 + (g2 - g1) * t) / 255, (b1 + (b2 - b1) * t) / 255))
            c.rect(0, PH - (i + 1) * PH / steps, PW, PH / steps + 1, stroke=0, fill=1)


def _draw_wrapped(c, text, x, y, width, font, size, color, leading=None, bullet=None, accent=None):
    leading = leading or size * 1.3
    indent = size * 1.1 if bullet else 0
    lines = simpleSplit(text, font, size, width - indent)
    if bullet and accent:
        c.setFillColor(_col(accent))
        c.circle(x + size * 0.3, y + size * 0.3, size * 0.16, stroke=0, fill=1)
    c.setFillColor(_col(color))
    c.setFont(font, size)
    for ln in lines:
        c.drawString(x + indent, y, ln)
        y -= leading
    return y


def build_pdf(deck: dict, theme_id: str, author: str = "") -> bytes:
    theme = get_theme(theme_id)
    reg, bold, uni = _fonts(theme["pdf_family"])
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(PW, PH))
    c.setTitle(_safe(deck.get("title", "Presentation"), uni))
    if author:
        c.setAuthor(_safe(author, uni))
    for s in deck["slides"]:
        _background(c, theme)
        layout = s.get("layout", "bullets")
        title = _safe(s["title"], uni)
        bullets = [_safe(b, uni) for b in s.get("bullets", [])]
        if layout in ("title", "closing"):
            c.setFont(bold, 40)
            lines = simpleSplit(title, bold, 40, PW - 160)
            y = PH / 2 + 40
            c.setFillColor(_col(theme["title"]))
            for ln in lines:
                c.drawCentredString(PW / 2, y, ln)
                y -= 50
            c.setFillColor(_col(theme["accent"]))
            c.rect(PW / 2 - 40, y + 20, 80, 4, stroke=0, fill=1)
            y -= 20
            for b in bullets:
                for ln in simpleSplit(b, reg, 20, PW - 240):
                    c.setFillColor(_col(theme["text"]))
                    c.setFont(reg, 20)
                    c.drawCentredString(PW / 2, y, ln)
                    y -= 28
        elif layout == "quote":
            c.setFont(bold, 24)
            c.setFillColor(_col(theme["title"]))
            c.drawString(60, PH - 80, title[:90])
            y = PH / 2 + 40
            for ln in simpleSplit("“" + (bullets[0] if bullets else "") + "”", reg, 30, PW - 200):
                c.setFillColor(_col(theme["accent"]))
                c.setFont(reg, 30)
                c.drawString(100, y, ln)
                y -= 40
            if len(bullets) > 1:
                _draw_wrapped(c, "— " + bullets[1], 100, y - 20, PW - 200, reg, 18, theme["muted"])
        else:
            tlines = simpleSplit(title, bold, 30, PW - 120)
            y = PH - 75
            for ln in tlines[:2]:
                c.setFont(bold, 30)
                c.setFillColor(_col(theme["title"]))
                c.drawString(60, y, ln)
                y -= 36
            c.setFillColor(_col(theme["accent"]))
            c.rect(60, y - 4, 90, 4, stroke=0, fill=1)
            top = y - 44
            if layout == "two_column":
                mid = (len(bullets) + 1) // 2
                colw = (PW - 150) / 2
                for ci, group in enumerate((bullets[:mid], bullets[mid:])):
                    yy = top
                    for b in group:
                        yy = _draw_wrapped(c, b, 60 + ci * (colw + 30), yy, colw, reg, 17, theme["text"], bullet=True, accent=theme["accent"]) - 10
            elif layout == "chart":
                yy = top
                for b in bullets:
                    yy = _draw_wrapped(c, b, 60, yy, 450, reg, 17, theme["text"], bullet=True, accent=theme["accent"]) - 10
                c.setStrokeColor(_col(theme["accent"]))
                c.setLineWidth(2)
                c.roundRect(540, 80, PW - 600, PH - 200, 14, stroke=1, fill=0)
                _draw_wrapped(c, "Suggested visual: " + _safe(s.get("visual_suggestion") or "chart or diagram", uni),
                              560, PH / 2 - 20, PW - 640, reg, 15, theme["muted"])
            else:
                yy = top
                for b in bullets:
                    yy = _draw_wrapped(c, b, 60, yy, PW - 120, reg, 20, theme["text"], bullet=True, accent=theme["accent"]) - 12
        if author:
            c.setFont(reg, 9)
            c.setFillColor(_col(theme["muted"]))
            c.drawString(40, 16, _safe(f"Created by {author}", uni))
        c.showPage()
    c.save()
    return buf.getvalue()


def build_html(deck: dict, theme_id: str, author: str = "") -> str:
    t = get_theme(theme_id)
    bg = t["bg"][0] if len(t["bg"]) == 1 else f"linear-gradient(135deg,{t['bg'][0]},{t['bg'][1]})"
    esc = html.escape
    parts = []
    for s in deck["slides"]:
        lis = "".join(f"<li>{esc(b)}</li>" for b in s.get("bullets", []))
        notes = f"<p class='notes'><b>Notes:</b> {esc(s['speaker_notes'])}</p>" if s.get("speaker_notes") else ""
        by = f"<p class='by'>Created by {esc(author)}</p>" if author else ""
        parts.append(f"<section class='slide'><h2>{esc(s['title'])}</h2><ul>{lis}</ul>{notes}{by}</section>")
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>{esc(deck['title'])}</title>
<style>
@page {{ size: 13.333in 7.5in; margin: 0 }}
body {{ margin:0; font-family:'{t['font_body']}',Arial,sans-serif; background:#e5e7eb }}
.slide {{ width:13.333in; height:7.5in; box-sizing:border-box; padding:.7in .8in; margin:16px auto; background:{bg};
 color:{t['text']}; page-break-after:always; overflow:hidden; position:relative }}
h2 {{ color:{t['title']}; font-family:'{t['font_heading']}',Georgia,serif; font-size:34px; margin:0 0 24px;
 border-bottom:4px solid {t['accent']}; padding-bottom:12px; display:inline-block }}
li {{ font-size:22px; margin:10px 0 }} li::marker {{ color:{t['accent']} }}
.by {{ position:absolute; bottom:.25in; right:.8in; margin:0; font-size:12px; color:{t['muted']} }}
.notes {{ position:absolute; bottom:.4in; left:.8in; right:.8in; font-size:13px; color:{t['muted']} }}
@media print {{ body {{ background:none }} .slide {{ margin:0; -webkit-print-color-adjust:exact; print-color-adjust:exact }} .notes {{ display:none }} }}
</style></head><body>{''.join(parts)}</body></html>"""
