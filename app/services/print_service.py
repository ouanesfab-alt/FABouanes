from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

from app.core.config import BASE_DIR
from app.core.db_access import query_db

try:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import HRFlowable, Image as RLImage, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


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


def _purchase_line_to_doc_line(row) -> dict[str, Any]:
    unit = row["display_unit"] or row["base_unit"] or "kg"
    return {
        "item_name": row["item_name"],
        "quantity": row["display_quantity"],
        "unit": unit,
        "unit_price": row["display_unit_price"],
        "total": row["total"],
    }


def _sale_line_to_doc_line(row, item_name: str) -> dict[str, Any]:
    return {
        "item_name": item_name,
        "quantity": row["quantity"],
        "unit": row["unit"],
        "unit_price": row["unit_price"],
        "total": row["total"],
    }


def _sale_document_subtitle(lines: list[dict[str, Any]]) -> str:
    kinds = {str(line.get("kind") or "") for line in lines}
    if kinds == {"finished"}:
        return "Vente produit final"
    if kinds == {"raw"}:
        return "Vente matière première"
    return "Vente multi-produits"


def build_print_payload(doc_type: str, item_id: int):
    if doc_type == "purchase":
        pointer = query_db("SELECT id, document_id FROM purchases WHERE id = %s", (item_id,), one=True)
        if pointer and pointer["document_id"]:
            return build_print_payload("purchase_document", int(pointer["document_id"]))
        row = query_db(
            """
            SELECT p.*, 
                   CASE 
                       WHEN p.finished_product_id IS NOT NULL THEN fp.name
                       ELSE COALESCE(NULLIF(p.custom_item_name, ''), rm.name)
                   END AS item_name, 
                   CASE 
                       WHEN p.finished_product_id IS NOT NULL THEN fp.default_unit
                       ELSE rm.unit
                   END AS base_unit, 
                   CASE 
                       WHEN p.finished_product_id IS NOT NULL THEN COALESCE(p.unit, fp.default_unit, 'kg')
                       ELSE COALESCE(p.unit, rm.unit, 'kg')
                   END AS display_unit,
                   CASE
                       WHEN lower(COALESCE(p.unit, fp.default_unit, rm.unit, 'kg')) = 'sac' THEN p.quantity / 50.0
                       WHEN lower(COALESCE(p.unit, fp.default_unit, rm.unit, 'kg')) IN ('qt', 'quintal') THEN p.quantity / 100.0
                       ELSE p.quantity
                   END AS display_quantity,
                   CASE
                       WHEN lower(COALESCE(p.unit, fp.default_unit, rm.unit, 'kg')) = 'sac' THEN p.unit_price * 50.0
                       WHEN lower(COALESCE(p.unit, fp.default_unit, rm.unit, 'kg')) IN ('qt', 'quintal') THEN p.unit_price * 100.0
                       ELSE p.unit_price
                   END AS display_unit_price,
                   s.name AS partner_name, s.phone AS partner_phone, s.address AS partner_address
            FROM purchases p
            LEFT JOIN raw_materials rm ON rm.id = p.raw_material_id
            LEFT JOIN finished_products fp ON fp.id = p.finished_product_id
            LEFT JOIN suppliers s ON s.id = p.supplier_id
            WHERE p.id = %s
            """,
            (item_id,),
            one=True,
        )
        if not row:
            return None
        lines = [_purchase_line_to_doc_line(row)]
        return _print_defaults({
            "title": "Bon d'achat",
            "subtitle": "Achat matière première",
            "number": f"ACH-{row['id']:06d}",
            "date": row["purchase_date"],
            "partner_label": "Fournisseur",
            "partner_name": row["partner_name"] or "Non renseigné",
            "partner_phone": row["partner_phone"] or "",
            "partner_address": row["partner_address"] or "",
            "item_label": "Matière",
            "item_name": row["item_name"],
            "quantity": row["display_quantity"],
            "unit": row["display_unit"],
            "unit_price": row["display_unit_price"],
            "total": row["total"],
            "paid": None,
            "due": None,
            "notes": row["notes"] or "",
            "lines": lines,
        })

    if doc_type == "purchase_document":
        doc = query_db(
            """
            SELECT pd.*, s.name AS partner_name, s.phone AS partner_phone, s.address AS partner_address
            FROM purchase_documents pd
            LEFT JOIN suppliers s ON s.id = pd.supplier_id
            WHERE pd.id = %s
            """,
            (item_id,),
            one=True,
        )
        if not doc:
            return None
        line_rows = query_db(
            """
            SELECT p.*, 
                   CASE 
                       WHEN p.finished_product_id IS NOT NULL THEN fp.name
                       ELSE COALESCE(NULLIF(p.custom_item_name, ''), rm.name)
                   END AS item_name, 
                   CASE 
                       WHEN p.finished_product_id IS NOT NULL THEN fp.default_unit
                       ELSE rm.unit
                   END AS base_unit, 
                   CASE 
                       WHEN p.finished_product_id IS NOT NULL THEN COALESCE(p.unit, fp.default_unit, 'kg')
                       ELSE COALESCE(p.unit, rm.unit, 'kg')
                   END AS display_unit,
                   CASE
                       WHEN lower(COALESCE(p.unit, fp.default_unit, rm.unit, 'kg')) = 'sac' THEN p.quantity / 50.0
                       WHEN lower(COALESCE(p.unit, fp.default_unit, rm.unit, 'kg')) IN ('qt', 'quintal') THEN p.quantity / 100.0
                       ELSE p.quantity
                   END AS display_quantity,
                   CASE
                       WHEN lower(COALESCE(p.unit, fp.default_unit, rm.unit, 'kg')) = 'sac' THEN p.unit_price * 50.0
                       WHEN lower(COALESCE(p.unit, fp.default_unit, rm.unit, 'kg')) IN ('qt', 'quintal') THEN p.unit_price * 100.0
                       ELSE p.unit_price
                   END AS display_unit_price
            FROM purchases p
            LEFT JOIN raw_materials rm ON rm.id = p.raw_material_id
            LEFT JOIN finished_products fp ON fp.id = p.finished_product_id
            WHERE p.document_id = %s
            ORDER BY p.id ASC
            """,
            (item_id,),
        )
        if not line_rows:
            return None
        lines = [_purchase_line_to_doc_line(row) for row in line_rows]
        return _print_defaults({
            "title": "Bon d'achat",
            "subtitle": "Achat multi-produits",
            "number": f"ACH-{doc['id']:06d}",
            "date": doc["purchase_date"],
            "partner_label": "Fournisseur",
            "partner_name": doc["partner_name"] or "Non renseigné",
            "partner_phone": doc["partner_phone"] or "",
            "partner_address": doc["partner_address"] or "",
            "item_label": "Matière",
            "item_name": f"{len(lines)} ligne(s)",
            "quantity": None,
            "unit": "",
            "unit_price": None,
            "total": doc["total"],
            "paid": None,
            "due": None,
            "notes": doc["notes"] or "",
            "lines": lines,
        })

    if doc_type == "sale_finished":
        pointer = query_db("SELECT id, document_id FROM sales WHERE id = %s", (item_id,), one=True)
        if pointer and pointer["document_id"]:
            return build_print_payload("sale_document", int(pointer["document_id"]))
        row = query_db(
            """
            SELECT s.*, f.name AS item_name, COALESCE(c.name, 'Comptoir') AS partner_name,
                   c.phone AS partner_phone, c.address AS partner_address
            FROM sales s
            JOIN finished_products f ON f.id = s.finished_product_id
            LEFT JOIN clients c ON c.id = s.client_id
            WHERE s.id = %s
            """,
            (item_id,),
            one=True,
        )
        if not row:
            return None
        lines = [_sale_line_to_doc_line(row, row["item_name"])]
        return _print_defaults({
            "title": "Facture",
            "subtitle": "Vente produit final",
            "number": f"VPF-{row['id']:06d}",
            "date": row["sale_date"],
            "partner_label": "Client",
            "partner_name": row["partner_name"],
            "partner_phone": row["partner_phone"] or "",
            "partner_address": row["partner_address"] or "",
            "payment_mode": _payment_mode_label(row["sale_type"]),
            "item_label": "Article",
            "item_name": row["item_name"],
            "quantity": row["quantity"],
            "unit": row["unit"],
            "unit_price": row["unit_price"],
            "total": row["total"],
            "paid": row["amount_paid"],
            "due": row["balance_due"],
            "notes": row["notes"] or "",
            "lines": lines,
        })

    if doc_type == "sale_raw":
        pointer = query_db("SELECT id, document_id FROM raw_sales WHERE id = %s", (item_id,), one=True)
        if pointer and pointer["document_id"]:
            return build_print_payload("sale_document", int(pointer["document_id"]))
        row = query_db(
            """
            SELECT rs.*, COALESCE(NULLIF(rs.custom_item_name, ''), r.name) AS item_name, COALESCE(c.name, 'Comptoir') AS partner_name,
                   c.phone AS partner_phone, c.address AS partner_address
            FROM raw_sales rs
            JOIN raw_materials r ON r.id = rs.raw_material_id
            LEFT JOIN clients c ON c.id = rs.client_id
            WHERE rs.id = %s
            """,
            (item_id,),
            one=True,
        )
        if not row:
            return None
        lines = [_sale_line_to_doc_line(row, row["item_name"])]
        return _print_defaults({
            "title": "Facture",
            "subtitle": "Vente matière première",
            "number": f"VMP-{row['id']:06d}",
            "date": row["sale_date"],
            "partner_label": "Client",
            "partner_name": row["partner_name"],
            "partner_phone": row["partner_phone"] or "",
            "partner_address": row["partner_address"] or "",
            "payment_mode": _payment_mode_label(row["sale_type"]),
            "item_label": "Article",
            "item_name": row["item_name"],
            "quantity": row["quantity"],
            "unit": row["unit"],
            "unit_price": row["unit_price"],
            "total": row["total"],
            "paid": row["amount_paid"],
            "due": row["balance_due"],
            "notes": row["notes"] or "",
            "lines": lines,
        })

    if doc_type == "sale_document":
        doc = query_db(
            """
            SELECT sd.*, COALESCE(c.name, 'Comptoir') AS partner_name,
                   c.phone AS partner_phone, c.address AS partner_address
            FROM sale_documents sd
            LEFT JOIN clients c ON c.id = sd.client_id
            WHERE sd.id = %s
            """,
            (item_id,),
            one=True,
        )
        if not doc:
            return None
        line_rows = query_db(
            """
            SELECT * FROM (
                SELECT 'finished' AS kind, s.id AS line_id, s.quantity, s.unit, s.unit_price, s.total, f.name AS item_name
                FROM sales s
                JOIN finished_products f ON f.id = s.finished_product_id
                WHERE s.document_id = %s
                UNION ALL
                SELECT 'raw' AS kind, rs.id AS line_id, rs.quantity, rs.unit, rs.unit_price, rs.total, COALESCE(NULLIF(rs.custom_item_name, ''), r.name) AS item_name
                FROM raw_sales rs
                JOIN raw_materials r ON r.id = rs.raw_material_id
                WHERE rs.document_id = %s
            ) lines
            ORDER BY line_id ASC
            """,
            (item_id, item_id),
        )
        if not line_rows:
            return None
        lines = [_sale_line_to_doc_line(row, row["item_name"]) | {"kind": row["kind"]} for row in line_rows]
        subtitle = _sale_document_subtitle(lines)
        clean_lines = [{k: v for k, v in line.items() if k != "kind"} for line in lines]
        return _print_defaults({
            "title": "Facture",
            "subtitle": subtitle,
            "number": f"FAC-{doc['id']:06d}",
            "date": doc["sale_date"],
            "partner_label": "Client",
            "partner_name": doc["partner_name"],
            "partner_phone": doc["partner_phone"] or "",
            "partner_address": doc["partner_address"] or "",
            "payment_mode": _payment_mode_label(doc["sale_type"]),
            "item_label": "Article",
            "item_name": f"{len(clean_lines)} ligne(s)",
            "quantity": None,
            "unit": "",
            "unit_price": None,
            "total": doc["total"],
            "paid": doc["amount_paid"],
            "due": doc["balance_due"],
            "notes": doc["notes"] or "",
            "lines": clean_lines,
        })

    if doc_type == "payment":
        row = query_db(
            """
            SELECT p.*, c.name AS partner_name, c.phone AS partner_phone, c.address AS partner_address
            FROM payments p
            JOIN clients c ON c.id = p.client_id
            WHERE p.id = %s
            """,
            (item_id,),
            one=True,
        )
        if not row:
            return None
        label = "Avance client" if row["payment_type"] == "avance" else "Versement client"
        lines = [
            {
                "item_name": label,
                "quantity": None,
                "unit": "",
                "unit_price": None,
                "total": row["amount"],
            }
        ]
        return _print_defaults({
            "title": "Re\u00e7u",
            "subtitle": label,
            "number": f"PAY-{row['id']:06d}",
            "date": row["payment_date"],
            "partner_label": "Client",
            "partner_name": row["partner_name"],
            "partner_phone": row["partner_phone"] or "",
            "partner_address": row["partner_address"] or "",
            "payment_mode": _payment_mode_label(row["payment_type"]),
            "item_label": "Reference",
            "item_name": label,
            "quantity": None,
            "unit": "",
            "unit_price": None,
            "total": row["amount"],
            "paid": row["amount"],
            "due": 0,
            "notes": row["notes"] or "",
            "lines": lines,
        })

    if doc_type == "production":
        row = query_db(
            """
            SELECT pb.*, fp.name AS item_name
            FROM production_batches pb
            JOIN finished_products fp ON fp.id = pb.finished_product_id
            WHERE pb.id = %s
            """,
            (item_id,),
            one=True,
        )
        if not row:
            return None
        item_rows = query_db(
            """
            SELECT r.name AS material_name, pbi.quantity, r.unit, pbi.unit_cost_snapshot, pbi.line_cost
            FROM production_batch_items pbi
            JOIN raw_materials r ON r.id = pbi.raw_material_id
            WHERE pbi.batch_id = %s
            ORDER BY pbi.id ASC
            """,
            (item_id,),
        )
        recipe_text = " + ".join(
            f"{item['material_name']} {item['quantity']} {item['unit'] or 'kg'}" for item in item_rows
        ) or "-"
        lines = [
            {
                "item_name": item["material_name"],
                "quantity": item["quantity"],
                "unit": item["unit"] or "kg",
                "unit_price": item["unit_cost_snapshot"],
                "total": item["line_cost"],
            }
            for item in item_rows
        ]
        if not lines:
            lines = [
                {
                    "item_name": row["item_name"],
                    "quantity": row["output_quantity"],
                    "unit": "kg",
                    "unit_price": row["unit_cost"],
                    "total": row["production_cost"],
                }
            ]
        return _print_defaults({
            "title": "Fiche de production",
            "subtitle": "Production enregistree",
            "number": f"PROD-{row['id']:06d}",
            "date": row["production_date"],
            "partner_label": "Produit final",
            "partner_name": row["item_name"],
            "item_label": "Recette",
            "item_name": recipe_text,
            "quantity": row["output_quantity"],
            "unit": "kg",
            "unit_price": row["unit_cost"],
            "total": row["production_cost"],
            "paid": None,
            "due": None,
            "notes": row["notes"] or "",
            "lines": lines,
        })

    return None


def _fmt_money_pdf(value) -> str:
    try:
        return f"{float(value):,.2f} DA".replace(",", " ")
    except (TypeError, ValueError):
        return "0,00 DA"


def _logo_cell(logo_path: Path, width_cm: float, height_cm: float):
    if logo_path.exists():
        return RLImage(str(logo_path), width=width_cm * cm, height=height_cm * cm)
    return Spacer(width_cm * cm, height_cm * cm)


def generate_invoice_pdf(doc: dict[str, Any], printed_by: str) -> BytesIO | None:
    if not REPORTLAB_AVAILABLE:
        return None

    buffer = BytesIO()
    page_doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=PDF_PAGE_MARGIN_CM * cm,
        bottomMargin=PDF_PAGE_MARGIN_CM * cm,
        leftMargin=PDF_PAGE_MARGIN_CM * cm,
        rightMargin=PDF_PAGE_MARGIN_CM * cm,
    )
    content_width = float(page_doc.width)
    styles = getSampleStyleSheet()
    pdf_font_regular, pdf_font_bold = _pdf_font_names()

    # Premium Color Scheme matching HTML CSS variables
    primary_color = colors.HexColor("#0f172a")  # Deep Charcoal
    accent_color = colors.HexColor("#0284c7")   # Corporate Ocean Blue
    text_dark = colors.HexColor("#1e293b")      # Dark Slate Text
    text_muted = colors.HexColor("#64748b")     # Light Slate Text
    border_color = colors.HexColor("#cbd5e1")   # Slate Border
    border_light = colors.HexColor("#e2e8f0")   # Light Slate Divider
    bg_light = colors.HexColor("#f8fafc")       # Soft Accent Background

    story = []

    # Title & Subtitle for Ref Box
    invoice_title_style = ParagraphStyle(
        "print_invoice_title",
        parent=styles["Normal"],
        fontName=pdf_font_bold,
        fontSize=15.0,
        leading=17.0,
        textColor=primary_color,
        spaceAfter=0,
        alignment=TA_LEFT,
    )
    subtitle_style = ParagraphStyle(
        "print_subtitle",
        parent=styles["Normal"],
        fontName=pdf_font_regular,
        fontSize=8.5,
        leading=10.0,
        textColor=text_muted,
        spaceAfter=0,
        alignment=TA_LEFT,
    )

    # Key/Value for Invoice Box
    invoice_label_style = ParagraphStyle(
        "print_invoice_label",
        parent=styles["Normal"],
        fontName=pdf_font_bold,
        fontSize=8.0,
        leading=10.0,
        textColor=text_muted,
    )
    invoice_value_style = ParagraphStyle(
        "print_invoice_value",
        parent=styles["Normal"],
        fontName=pdf_font_bold,
        fontSize=9.0,
        leading=11.0,
        textColor=primary_color,
        alignment=TA_RIGHT,
    )

    # Contact style for company details
    contact_style = ParagraphStyle(
        "print_contact",
        parent=styles["Normal"],
        fontName=pdf_font_regular,
        fontSize=9.0,
        leading=12.0,
        textColor=text_dark,
    )

    # Client Box Header Tab Badge Style
    tab_style = ParagraphStyle(
        "print_client_tab",
        parent=styles["Normal"],
        fontName=pdf_font_bold,
        fontSize=7.5,
        leading=9.0,
        textColor=colors.white,
    )

    # Client Box Details
    partner_name_style = ParagraphStyle(
        "print_partner_name",
        parent=styles["Normal"],
        fontName=pdf_font_bold,
        fontSize=13.0,
        leading=15.0,
        textColor=primary_color,
    )
    prepared_label_style = ParagraphStyle(
        "print_prepared_label",
        parent=styles["Normal"],
        fontName=pdf_font_regular,
        fontSize=8.0,
        leading=10.0,
        textColor=text_muted,
        alignment=TA_RIGHT,
    )
    prepared_value_style = ParagraphStyle(
        "print_prepared_value",
        parent=styles["Normal"],
        fontName=pdf_font_bold,
        fontSize=8.5,
        leading=10.0,
        textColor=text_dark,
        alignment=TA_RIGHT,
    )
    client_box_text_style = ParagraphStyle(
        "print_client_text",
        parent=styles["Normal"],
        fontName=pdf_font_regular,
        fontSize=9.0,
        leading=12.0,
        textColor=text_dark,
    )

    # Table Header Styles
    table_head_style = ParagraphStyle(
        "print_table_head",
        parent=styles["Normal"],
        fontName=pdf_font_bold,
        fontSize=8.0,
        leading=10.0,
        textColor=primary_color,
    )
    table_head_right_style = ParagraphStyle(
        "print_table_head_right",
        parent=table_head_style,
        alignment=TA_RIGHT,
    )

    # Table Cell Styles
    cell_style = ParagraphStyle(
        "print_cell",
        parent=styles["Normal"],
        fontName=pdf_font_regular,
        fontSize=9.0,
        leading=11.0,
        textColor=text_dark,
    )
    cell_bold_style = ParagraphStyle(
        "print_cell_bold",
        parent=cell_style,
        fontName=pdf_font_bold,
        textColor=primary_color,
    )
    cell_right_style = ParagraphStyle(
        "print_cell_right",
        parent=cell_style,
        alignment=TA_RIGHT,
    )
    cell_right_bold_style = ParagraphStyle(
        "print_cell_right_bold",
        parent=cell_bold_style,
        alignment=TA_RIGHT,
    )

    # Summary Box Styles
    summary_label_style = ParagraphStyle(
        "print_summary_label",
        parent=styles["Normal"],
        fontName=pdf_font_bold,
        fontSize=8.0,
        leading=10.0,
        textColor=text_muted,
    )
    summary_value_style = ParagraphStyle(
        "print_summary_value",
        parent=styles["Normal"],
        fontName=pdf_font_bold,
        fontSize=10.0,
        leading=12.0,
        textColor=primary_color,
        alignment=TA_RIGHT,
    )
    summary_total_label_style = ParagraphStyle(
        "print_summary_total_label",
        parent=styles["Normal"],
        fontName=pdf_font_bold,
        fontSize=8.0,
        leading=10.0,
        textColor=primary_color,
    )
    summary_total_value_style = ParagraphStyle(
        "print_summary_total_value",
        parent=styles["Normal"],
        fontName=pdf_font_bold,
        fontSize=13.0,
        leading=15.0,
        textColor=accent_color,
        alignment=TA_RIGHT,
    )

    # Footer Style
    footer_style = ParagraphStyle(
        "print_footer",
        parent=styles["Normal"],
        fontName=pdf_font_regular,
        fontSize=8.5,
        leading=11.0,
        alignment=TA_CENTER,
        textColor=text_muted,
    )

    printed_date = str(doc.get("printed_date") or doc.get("date") or "")
    printed_time = str(doc.get("printed_time") or "")
    show_partner_phone = str(doc.get("partner_label", "")).strip().lower() != "client" and bool(doc.get("partner_phone"))

    # Company Contact Info Block
    brand_logo = _logo_cell(BASE_DIR / "static" / "fab_invoice_logo_clean.png", 12.4, 3.98)
    company_block = [
        brand_logo,
        Spacer(1, 0.34 * cm),
        Paragraph(f"<b>Adresse :</b> {COMPANY_INFO['address']}", contact_style),
        Spacer(1, 0.12 * cm),
        Paragraph(f"<b>Tél :</b> {COMPANY_INFO['phones']}", contact_style),
        Spacer(1, 0.12 * cm),
        Paragraph(f"<b>Email :</b> {COMPANY_INFO['email']}", contact_style),
    ]

    # Inner title banner with left accent border
    title_sub_rows = [
        [Paragraph(str(doc.get("title", "")).upper(), invoice_title_style)]
    ]
    if doc.get("subtitle"):
        title_sub_rows.append([Paragraph(str(doc.get("subtitle", "")), subtitle_style)])
    
    title_wrap_table = Table(title_sub_rows, colWidths=[6.0 * cm])
    title_wrap_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), bg_light),
                ("LINEBEFORE", (0, 0), (0, -1), 3.0, accent_color),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )

    # Document reference rows (metadata)
    invoice_rows = [
        [title_wrap_table, ""]  # Spanned over 2 columns
    ]
    invoice_rows.append([Paragraph("N° DOCUMENT :", invoice_label_style), Paragraph(str(doc.get("number", "")), invoice_value_style)])
    invoice_rows.append([Paragraph("DATE :", invoice_label_style), Paragraph(printed_date, invoice_value_style)])
    if printed_time:
        invoice_rows.append([Paragraph("HEURE :", invoice_label_style), Paragraph(printed_time, invoice_value_style)])

    payment_mode = doc.get("payment_mode")
    if payment_mode and payment_mode != "-":
        pay_lbl = _payment_mode_label(payment_mode)
        invoice_rows.append([Paragraph("PAIEMENT :", invoice_label_style), Paragraph(pay_lbl, invoice_value_style)])

    invoice_box = Table(
        invoice_rows,
        colWidths=[3.1 * cm, 3.1 * cm],
    )
    invoice_box_commands = [
        ("SPAN", (0, 0), (1, 0)),
        ("BACKGROUND", (0, 0), (-1, -1), bg_light),
        ("BOX", (0, 0), (-1, -1), 1.0, border_color),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    for r in range(1, len(invoice_rows) - 1):
        invoice_box_commands.append(("LINEBELOW", (0, r), (-1, r), 0.5, border_light))
        
    invoice_box.setStyle(TableStyle(invoice_box_commands))

    brand_table = Table([[company_block, invoice_box]], colWidths=[content_width - 6.4 * cm, 6.4 * cm])
    brand_table.setStyle(
        TableStyle(
            [
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(brand_table)
    story.append(Spacer(1, 0.72 * cm))

    # Client Box Layout (indented tab/badge above client box table)
    tab_label = str(doc.get("partner_label", "Client")).upper()
    tab_table = Table([[Paragraph(tab_label, tab_style)]], colWidths=[2.2 * cm], hAlign="LEFT")
    tab_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), primary_color),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    
    # Indent the tab by 0.4 cm to match HTML layout alignment
    tab_indent = Table([["", tab_table]], colWidths=[0.4 * cm, 2.2 * cm], hAlign="LEFT")
    tab_indent.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    
    client_rows = [
        [
            Paragraph(str(doc.get("partner_name", "")), partner_name_style),
            Paragraph("Préparé par :", prepared_label_style),
            Paragraph(str(printed_by), prepared_value_style),
        ]
    ]
    client_style_commands = [
        ("BOX", (0, 0), (-1, -1), 1.0, border_color),
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]
    if show_partner_phone:
        client_rows.append([
            Paragraph(f"<b>Tél :</b> {doc['partner_phone']}", client_box_text_style),
            "", ""
        ])
        r_idx = len(client_rows) - 1
        client_style_commands.append(("SPAN", (0, r_idx), (2, r_idx)))
        client_style_commands.append(("TOPPADDING", (0, r_idx), (-1, r_idx), 0))
        client_style_commands.append(("BOTTOMPADDING", (0, r_idx), (-1, r_idx), 4))

    if doc.get("partner_address"):
        client_rows.append([
            Paragraph(f"<b>Adresse :</b> {doc['partner_address']}", client_box_text_style),
            "", ""
        ])
        r_idx = len(client_rows) - 1
        client_style_commands.append(("SPAN", (0, r_idx), (2, r_idx)))
        client_style_commands.append(("TOPPADDING", (0, r_idx), (-1, r_idx), 0))
        client_style_commands.append(("BOTTOMPADDING", (0, r_idx), (-1, r_idx), 4))

    client_box = Table(
        client_rows,
        colWidths=[content_width * 0.58, 2.3 * cm, content_width - (content_width * 0.58) - 2.3 * cm],
        hAlign="LEFT",
    )
    client_box.setStyle(TableStyle(client_style_commands))
    
    story.append(tab_indent)
    story.append(Spacer(1, 0.08 * cm))
    story.append(client_box)
    story.append(Spacer(1, 0.55 * cm))

    # Items Table Layout (no outer BOX border to make it open on the sides)
    lines = doc.get("lines") or [
        {
            "item_name": doc.get("item_name") or "-",
            "quantity": doc.get("quantity"),
            "unit": doc.get("unit") or "",
            "unit_price": doc.get("unit_price"),
            "total": doc.get("total", 0),
        }
    ]
    table_rows = [
        [
            Paragraph(str(doc.get("item_label", "Article")), table_head_style),
            Paragraph("Quantité", table_head_right_style),
            Paragraph("PU", table_head_right_style),
            Paragraph("Total", table_head_right_style),
        ]
    ]
    for line_item in lines:
        qty_str = f"{line_item['quantity']} {line_item['unit']}" if line_item.get("quantity") is not None else "-"
        unit_price_str = _fmt_money_pdf(line_item.get("unit_price")) if line_item.get("unit_price") is not None else "-"
        total_str = _fmt_money_pdf(line_item.get("total", 0))
        table_rows.append(
            [
                Paragraph(str(line_item.get("item_name") or "-"), cell_bold_style),
                Paragraph(qty_str, cell_right_style),
                Paragraph(unit_price_str, cell_right_style),
                Paragraph(total_str, cell_right_bold_style),
            ]
        )

    items_table = Table(
        table_rows,
        colWidths=[content_width * 0.52, content_width * 0.16, content_width * 0.16, content_width * 0.16],
        repeatRows=1,
    )
    items_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), bg_light),
                ("LINEBELOW", (0, 0), (-1, 0), 1.5, primary_color),
                ("LINEBELOW", (0, 1), (-1, -1), 0.5, border_light),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, bg_light]),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    story.append(items_table)
    story.append(Spacer(1, 0.24 * cm))

    # Summary Totals Box
    summary_rows = []
    if doc.get("paid") is not None:
        summary_rows.append([Paragraph("Payé", summary_label_style), Paragraph(_fmt_money_pdf(doc["paid"]), summary_value_style)])
    if doc.get("due") is not None:
        summary_rows.append([Paragraph("Reste", summary_label_style), Paragraph(_fmt_money_pdf(doc["due"]), summary_value_style)])
    summary_rows.append([Paragraph("Total", summary_total_label_style), Paragraph(_fmt_money_pdf(doc.get("total", 0)), summary_total_value_style)])

    summary_table = Table(summary_rows, colWidths=[3.0 * cm, 3.4 * cm], hAlign="RIGHT")
    summary_commands = [
        ("BACKGROUND", (0, 0), (-1, -1), bg_light),
        ("BOX", (0, 0), (-1, -1), 1.0, border_color),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    num_rows = len(summary_rows)
    for r in range(num_rows - 1):
        summary_commands.append(("LINEBELOW", (0, r), (-1, r), 0.5, border_light))
    summary_commands.append(("LINEABOVE", (0, num_rows - 1), (-1, num_rows - 1), 1.5, primary_color))
    
    summary_table.setStyle(TableStyle(summary_commands))
    story.append(summary_table)

    # Footer Layout
    story.append(Spacer(1, 0.45 * cm))
    story.append(HRFlowable(width="100%", thickness=0.7, color=border_light))
    story.append(Spacer(1, 0.12 * cm))
    story.append(Paragraph("FABOuanes - Document commercial", footer_style))

    page_doc.build(story)
    buffer.seek(0)
    return buffer


def _generate_invoice_pdf_model(doc: dict[str, Any], printed_by: str) -> BytesIO:
    buffer = BytesIO()
    page_doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=PDF_PAGE_MARGIN_CM * cm,
        bottomMargin=PDF_PAGE_MARGIN_CM * cm,
        leftMargin=PDF_PAGE_MARGIN_CM * cm,
        rightMargin=PDF_PAGE_MARGIN_CM * cm,
    )
    content_width = float(page_doc.width)
    styles = getSampleStyleSheet()
    pdf_font_regular, pdf_font_bold = _pdf_font_names()
    black = colors.black
    line = colors.HexColor("#777777")
    light = colors.HexColor("#F5F5F5")
    company = doc.get("company") or COMPANY_INFO
    total = doc.get("total") or 0
    subtotal = doc.get("subtotal", total)
    discount = doc.get("discount", 0)
    tax = doc.get("tax", 0)
    grand_total = doc.get("grand_total", total)
    printed_date = str(doc.get("printed_date") or doc.get("date") or "")
    printed_time = str(doc.get("printed_time") or "")
    show_partner_phone = str(doc.get("partner_label", "")).strip().lower() != "client"
    story = []

    brand_style = ParagraphStyle("model_brand", parent=styles["Normal"], fontName=pdf_font_bold, fontSize=30, leading=30, textColor=black)
    subtitle_style = ParagraphStyle("model_company_subtitle", parent=styles["Normal"], fontName=pdf_font_regular, fontSize=14, leading=16, textColor=colors.HexColor("#222222"))
    contact_style = ParagraphStyle("model_contact", parent=styles["Normal"], fontName=pdf_font_regular, fontSize=10, leading=13, textColor=black)
    box_title_style = ParagraphStyle("model_box_title", parent=styles["Normal"], fontName=pdf_font_bold, fontSize=28, leading=30, textColor=black, alignment=TA_CENTER)
    label_style = ParagraphStyle("model_label", parent=styles["Normal"], fontName=pdf_font_bold, fontSize=10, leading=12, textColor=black)
    value_style = ParagraphStyle("model_value", parent=styles["Normal"], fontName=pdf_font_regular, fontSize=10, leading=12, textColor=colors.HexColor("#222222"))
    table_head_style = ParagraphStyle("model_table_head", parent=styles["Normal"], fontName=pdf_font_bold, fontSize=10, leading=12, textColor=black, alignment=TA_CENTER)
    cell_style = ParagraphStyle("model_cell", parent=styles["Normal"], fontName=pdf_font_regular, fontSize=9, leading=11, textColor=black)
    cell_bold_style = ParagraphStyle("model_cell_bold", parent=cell_style, fontName=pdf_font_bold)
    cell_right_style = ParagraphStyle("model_cell_right", parent=cell_style, alignment=TA_RIGHT)
    tab_style = ParagraphStyle("model_tab", parent=label_style, textColor=colors.white, alignment=TA_CENTER)
    total_label_style = ParagraphStyle("model_total_label", parent=label_style, fontSize=14, leading=16)
    total_value_style = ParagraphStyle("model_total_value", parent=cell_right_style, fontName=pdf_font_bold, fontSize=14, leading=16)

    logo_cell = _logo_cell(BASE_DIR / "static" / "fab_logo.png", 2.35, 2.35)
    company_copy = [
        Paragraph(str(company.get("name", "FABOuanes")), brand_style),
        Paragraph(str(company.get("subtitle", "")), subtitle_style),
        Spacer(1, 0.18 * cm),
        Paragraph(str(company.get("address", "")), contact_style),
        Paragraph(str(company.get("phones", "")), contact_style),
        Paragraph(str(company.get("email", "")), contact_style),
    ]
    company_box = Table([[logo_cell, company_copy]], colWidths=[2.8 * cm, content_width - 10.8 * cm])
    company_box.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )

    ref_box = Table(
        [
            [Paragraph(str(doc.get("title", "")).upper(), box_title_style), ""],
            [Paragraph("N facture :", label_style), Paragraph(str(doc.get("number", "")), value_style)],
            [Paragraph("Date / Heure :", label_style), Paragraph(f"{printed_date} {printed_time}".strip(), value_style)],
        ],
        colWidths=[3.7 * cm, 3.9 * cm],
    )
    ref_box.setStyle(
        TableStyle(
            [
                ("SPAN", (0, 0), (1, 0)),
                ("BOX", (0, 0), (-1, -1), 0.9, black),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )

    header_table = Table([[company_box, ref_box]], colWidths=[content_width - 8.0 * cm, 8.0 * cm])
    header_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    story.append(header_table)
    story.append(Spacer(1, 0.55 * cm))

    client_rows = [
        [Paragraph(str(doc.get("partner_label", "Client")), tab_style)],
        [Paragraph(str(doc.get("partner_name", "")), value_style)],
    ]
    if show_partner_phone:
        client_rows.append([Paragraph(str(doc.get("partner_phone") or "-"), value_style)])
    if doc.get("partner_address"):
        client_rows.append([Paragraph(str(doc.get("partner_address")), value_style)])
    client_box_width = min(content_width, 7.4 * cm)
    client_box = Table(client_rows, colWidths=[client_box_width], hAlign="LEFT")
    client_box.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, 0), black),
                ("BOX", (0, 0), (-1, -1), 0.9, black),
                ("LEFTPADDING", (0, 0), (-1, -1), 14),
                ("RIGHTPADDING", (0, 0), (-1, -1), 14),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(client_box)
    story.append(Spacer(1, 0.45 * cm))

    lines = doc.get("lines") or [
        {
            "item_name": doc.get("item_name") or "-",
            "quantity": doc.get("quantity"),
            "unit": doc.get("unit") or "",
            "unit_price": doc.get("unit_price"),
            "total": doc.get("total", 0),
        }
    ]
    table_rows = [
        [
            Paragraph("Designation", table_head_style),
            Paragraph("Quantite", table_head_style),
            Paragraph("Unite", table_head_style),
            Paragraph("Prix unitaire", table_head_style),
            Paragraph("Montant", table_head_style),
        ]
    ]
    for line_item in lines:
        qty_str = str(line_item.get("quantity")) if line_item.get("quantity") is not None else "-"
        unit_price_str = _fmt_money_pdf(line_item.get("unit_price")) if line_item.get("unit_price") is not None else "-"
        total_str = _fmt_money_pdf(line_item.get("total", 0))
        table_rows.append(
            [
                Paragraph(str(line_item.get("item_name") or "-"), cell_bold_style),
                Paragraph(qty_str, cell_right_style),
                Paragraph(str(line_item.get("unit") or "-"), cell_style),
                Paragraph(unit_price_str, cell_right_style),
                Paragraph(total_str, cell_right_style),
            ]
        )
    while len(table_rows) < 8:
        table_rows.append(["", "", "", "", ""])

    items_table = Table(
        table_rows,
        colWidths=[content_width * 0.42, content_width * 0.16, content_width * 0.12, content_width * 0.16, content_width * 0.14],
        repeatRows=1,
    )
    items_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), light),
                ("BOX", (0, 0), (-1, -1), 0.7, black),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, line),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (1, 1), (1, -1), "RIGHT"),
                ("ALIGN", (3, 1), (-1, -1), "RIGHT"),
            ]
        )
    )
    story.append(items_table)
    story.append(Spacer(1, 0.55 * cm))

    obs_lines = [str(doc.get("subtitle") or "").strip(), str(doc.get("notes") or "Merci pour votre confiance.").strip()]
    obs_text = "<br/>".join(line for line in obs_lines if line)
    observations = Table(
        [
            [Paragraph("Observations", label_style)],
            [HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#B8B8B8"))],
            [Paragraph(obs_text, cell_style)],
        ],
        colWidths=[content_width - 10.0 * cm],
    )
    observations.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.8, black),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )

    summary_rows = [
        [Paragraph("Sous-total", label_style), Paragraph(_fmt_money_pdf(subtotal), cell_right_style)],
        [Paragraph("Remise", label_style), Paragraph(_fmt_money_pdf(discount) if discount else "____________", cell_right_style)],
        [Paragraph("TVA", label_style), Paragraph(_fmt_money_pdf(tax) if tax else "____________", cell_right_style)],
    ]
    if doc.get("paid") is not None:
        summary_rows.append([Paragraph("Paye", label_style), Paragraph(_fmt_money_pdf(doc["paid"]), cell_right_style)])
    if doc.get("due") is not None:
        summary_rows.append([Paragraph("Reste", label_style), Paragraph(_fmt_money_pdf(doc["due"]), cell_right_style)])
    summary_rows.append([Paragraph("Total TTC", total_label_style), Paragraph(_fmt_money_pdf(grand_total), total_value_style)])
    summary_table = Table(summary_rows, colWidths=[4.1 * cm, 4.1 * cm])
    summary_table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.7, black),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, line),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ]
        )
    )

    bottom = Table([[observations, summary_table]], colWidths=[content_width - 8.2 * cm - 1.8 * cm, 8.2 * cm])
    bottom.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (0, 0), 18),
                ("RIGHTPADDING", (1, 0), (1, 0), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    story.append(bottom)
    story.append(Spacer(1, 0.75 * cm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#999999")))
    story.append(Spacer(1, 0.45 * cm))

    signature_table = Table(
        [
            [Paragraph("Signature du client", label_style), Paragraph("Cachet / Signature", label_style)],
            ["____________________________", "____________________________"],
        ],
        colWidths=[content_width / 2, content_width / 2],
    )
    signature_table.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
            ]
        )
    )
    story.append(signature_table)

    page_doc.build(story)
    buffer.seek(0)
    return buffer
