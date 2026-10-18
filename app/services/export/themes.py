"""Design tokens shared by the preview (served via /api/themes), PPTX and PDF export."""
THEMES = {
    "minimal_academic": {"name": "Minimal Academic", "bg": ["#FFFFFF"], "title": "#111827", "text": "#1F2937",
                         "accent": "#1D4ED8", "muted": "#4B5563", "font_heading": "Georgia", "font_body": "Calibri",
                         "pdf_family": "serif"},
    "corporate_professional": {"name": "Corporate Professional", "bg": ["#F8FAFC"], "title": "#0F2A4A",
                               "text": "#1E293B", "accent": "#0E7490", "muted": "#475569",
                               "font_heading": "Calibri", "font_body": "Calibri", "pdf_family": "sans"},
    "modern_gradient": {"name": "Modern Gradient", "bg": ["#4338CA", "#6D28D9"], "title": "#FFFFFF", "text": "#FFFFFF",
                        "accent": "#FDE68A", "muted": "#E0E7FF", "font_heading": "Segoe UI", "font_body": "Segoe UI",
                        "pdf_family": "sans"},
    "creative_studio": {"name": "Creative Studio", "bg": ["#FFF7ED"], "title": "#9A3412", "text": "#292524",
                        "accent": "#C2410C", "muted": "#57534E", "font_heading": "Trebuchet MS",
                        "font_body": "Calibri", "pdf_family": "sans"},
    "technology_ai": {"name": "Technology & AI", "bg": ["#0B1220"], "title": "#E0F2FE", "text": "#CBD5E1",
                      "accent": "#22D3EE", "muted": "#94A3B8", "font_heading": "Consolas", "font_body": "Segoe UI",
                      "pdf_family": "sans"},
    "elegant_dark": {"name": "Elegant Dark", "bg": ["#18181B"], "title": "#FAFAFA", "text": "#E4E4E7",
                     "accent": "#D4AF37", "muted": "#A1A1AA", "font_heading": "Georgia", "font_body": "Calibri",
                     "pdf_family": "serif"},
}


def get_theme(theme_id: str) -> dict:
    return THEMES.get(theme_id, THEMES["minimal_academic"])


def hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
