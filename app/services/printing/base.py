"""Shared helpers, PDF base constants, fonts, colors, and utility functions."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.config import BASE_DIR

try:
    from reportlab.lib.units import cm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import (
        Image as RLImage,
        Spacer,
    )

    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


# ---------------------------------------------------------------------------
# Layout & company constants
# ---------------------------------------------------------------------------

PRINT_LAYOUT = {
    "page_width_mm": 210,
    "page_height_mm": 297,
    "page_margin_mm": 10,
    "content_width_mm": 190,
    "paper_height_mm": 277,
    "section_gap_mm": 5,
    "header_padding_mm": 10,
    "body_padding_mm": 10,
    "screen_gap_mm": 4,
    "screen_scale": 1.0,
    "summary_width_px": 320,
}

PDF_PAGE_MARGIN_CM = PRINT_LAYOUT["page_margin_mm"] / 10.0

COMPANY_INFO = {
    "name": "FABOuanes",
    "subtitle": "Fabrication d'aliment de b\u00e9tail",
    "address": "Tala Tegana, Freha, Tizi Ouzou",
    "phones": "0771214948 / 0553183302",
    "email": "ouanesfab@gmail.com",
}

PDF_FONT_REGULAR = "PlusJakartaSans"
PDF_FONT_BOLD = "PlusJakartaSans-Bold"


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _pdf_font_names() -> tuple[str, str]:
    if not REPORTLAB_AVAILABLE:
        return "Helvetica", "Helvetica-Bold"
    fonts_dir = BASE_DIR / "static" / "fonts"
    regular_path = fonts_dir / "PlusJakartaSans-Regular.ttf"
    bold_path = fonts_dir / "PlusJakartaSans-Bold.ttf"
    if not regular_path.exists() or not bold_path.exists():
        return "Helvetica", "Helvetica-Bold"
    try:
        for font_name, font_path in ((PDF_FONT_REGULAR, regular_path), (PDF_FONT_BOLD, bold_path)):
            try:
                pdfmetrics.getFont(font_name)
            except KeyError:
                pdfmetrics.registerFont(TTFont(font_name, str(font_path)))
    except Exception:
        return "Helvetica", "Helvetica-Bold"
    return PDF_FONT_REGULAR, PDF_FONT_BOLD


def _payment_mode_label(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    if normalized == "credit":
        return "Credit"
    if normalized == "cash":
        return "Comptant"
    if normalized == "avance":
        return "Avance"
    if normalized == "versement":
        return "Versement"
    return value or "-"


def _print_defaults(payload: dict[str, Any]) -> dict[str, Any]:
    total = payload.get("total") or 0
    payload.setdefault("company", COMPANY_INFO)
    payload.setdefault("partner_phone", "")
    payload.setdefault("partner_address", "")
    payload.setdefault("payment_mode", "-")
    payload.setdefault("due_date", "")
    payload.setdefault("subtotal", total)
    payload.setdefault("discount", 0)
    payload.setdefault("tax", 0)
    payload.setdefault("grand_total", total)
    return payload


def _fmt_money_pdf(value) -> str:
    try:
        return f"{int(round(float(value))):,} DA".replace(",", " ")
    except (TypeError, ValueError):
        return "0 DA"


def _logo_cell(logo_path: Path, width_cm: float, height_cm: float):
    if logo_path.exists():
        return RLImage(str(logo_path), width=width_cm * cm, height=height_cm * cm)
    
    # Fallback to .webp if the requested .png doesn't exist
    if logo_path.suffix.lower() == '.png':
        webp_path = logo_path.with_suffix('.webp')
        if webp_path.exists():
            return RLImage(str(webp_path), width=width_cm * cm, height=height_cm * cm)
            
    return Spacer(width_cm * cm, height_cm * cm)

