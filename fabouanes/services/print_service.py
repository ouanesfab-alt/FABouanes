from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

from fabouanes.config import BASE_DIR
from fabouanes.core.db_access import query_db

try:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
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
        pointer = query_db("SELECT id, document_id FROM purchases WHERE id = ?", (item_id,), one=True)
        if pointer and pointer["document_id"]:
            return build_print_payload("purchase_document", int(pointer["document_id"]))
        row = query_db(
            """
            SELECT p.*, COALESCE(NULLIF(p.custom_item_name, ''), rm.name) AS item_name, rm.unit AS base_unit, COALESCE(p.unit, rm.unit, 'kg') AS display_unit,
                   CASE
                       WHEN lower(COALESCE(p.unit, rm.unit, 'kg')) = 'sac' THEN p.quantity / 50.0
                       WHEN lower(COALESCE(p.unit, rm.unit, 'kg')) IN ('qt', 'quintal') THEN p.quantity / 100.0
                       ELSE p.quantity
                   END AS display_quantity,
                   CASE
                       WHEN lower(COALESCE(p.unit, rm.unit, 'kg')) = 'sac' THEN p.unit_price * 50.0
                       WHEN lower(COALESCE(p.unit, rm.unit, 'kg')) IN ('qt', 'quintal') THEN p.unit_price * 100.0
                       ELSE p.unit_price
                   END AS display_unit_price,
                   s.name AS partner_name
            FROM purchases p
            JOIN raw_materials rm ON rm.id = p.raw_material_id
            LEFT JOIN suppliers s ON s.id = p.supplier_id
            WHERE p.id = ?
            """,
            (item_id,),
            one=True,
        )
        if not row:
            return None
        lines = [_purchase_line_to_doc_line(row)]
        return {
            "title": "Bon d'achat",
            "subtitle": "Achat matière première",
            "number": f"ACH-{row['id']:06d}",
            "date": row["purchase_date"],
            "partner_label": "Fournisseur",
            "partner_name": row["partner_name"] or "Non renseigné",
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
        }

    if doc_type == "purchase_document":
        doc = query_db(
            """
            SELECT pd.*, s.name AS partner_name
            FROM purchase_documents pd
            LEFT JOIN suppliers s ON s.id = pd.supplier_id
            WHERE pd.id = ?
            """,
            (item_id,),
            one=True,
        )
        if not doc:
            return None
        line_rows = query_db(
            """
            SELECT p.*, COALESCE(NULLIF(p.custom_item_name, ''), rm.name) AS item_name, rm.unit AS base_unit, COALESCE(p.unit, rm.unit, 'kg') AS display_unit,
                   CASE
                       WHEN lower(COALESCE(p.unit, rm.unit, 'kg')) = 'sac' THEN p.quantity / 50.0
                       WHEN lower(COALESCE(p.unit, rm.unit, 'kg')) IN ('qt', 'quintal') THEN p.quantity / 100.0
                       ELSE p.quantity
                   END AS display_quantity,
                   CASE
                       WHEN lower(COALESCE(p.unit, rm.unit, 'kg')) = 'sac' THEN p.unit_price * 50.0
                       WHEN lower(COALESCE(p.unit, rm.unit, 'kg')) IN ('qt', 'quintal') THEN p.unit_price * 100.0
                       ELSE p.unit_price
                   END AS display_unit_price
            FROM purchases p
            JOIN raw_materials rm ON rm.id = p.raw_material_id
            WHERE p.document_id = ?
            ORDER BY p.id ASC
            """,
            (item_id,),
        )
        if not line_rows:
            return None
        lines = [_purchase_line_to_doc_line(row) for row in line_rows]
        return {
            "title": "Bon d'achat",
            "subtitle": "Achat multi-produits",
            "number": f"ACH-{doc['id']:06d}",
            "date": doc["purchase_date"],
            "partner_label": "Fournisseur",
            "partner_name": doc["partner_name"] or "Non renseigné",
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
        }

    if doc_type == "sale_finished":
        pointer = query_db("SELECT id, document_id FROM sales WHERE id = ?", (item_id,), one=True)
        if pointer and pointer["document_id"]:
            return build_print_payload("sale_document", int(pointer["document_id"]))
        row = query_db(
            """
            SELECT s.*, f.name AS item_name, COALESCE(c.name, 'Comptoir') AS partner_name
            FROM sales s
            JOIN finished_products f ON f.id = s.finished_product_id
            LEFT JOIN clients c ON c.id = s.client_id
            WHERE s.id = ?
            """,
            (item_id,),
            one=True,
        )
        if not row:
            return None
        lines = [_sale_line_to_doc_line(row, row["item_name"])]
        return {
            "title": "Facture",
            "subtitle": "Vente produit final",
            "number": f"VPF-{row['id']:06d}",
            "date": row["sale_date"],
            "partner_label": "Client",
            "partner_name": row["partner_name"],
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
        }

    if doc_type == "sale_raw":
        pointer = query_db("SELECT id, document_id FROM raw_sales WHERE id = ?", (item_id,), one=True)
        if pointer and pointer["document_id"]:
            return build_print_payload("sale_document", int(pointer["document_id"]))
        row = query_db(
            """
            SELECT rs.*, COALESCE(NULLIF(rs.custom_item_name, ''), r.name) AS item_name, COALESCE(c.name, 'Comptoir') AS partner_name
            FROM raw_sales rs
            JOIN raw_materials r ON r.id = rs.raw_material_id
            LEFT JOIN clients c ON c.id = rs.client_id
            WHERE rs.id = ?
            """,
            (item_id,),
            one=True,
        )
        if not row:
            return None
        lines = [_sale_line_to_doc_line(row, row["item_name"])]
        return {
            "title": "Facture",
            "subtitle": "Vente matière première",
            "number": f"VMP-{row['id']:06d}",
            "date": row["sale_date"],
            "partner_label": "Client",
            "partner_name": row["partner_name"],
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
        }

    if doc_type == "sale_document":
        doc = query_db(
            """
            SELECT sd.*, COALESCE(c.name, 'Comptoir') AS partner_name
            FROM sale_documents sd
            LEFT JOIN clients c ON c.id = sd.client_id
            WHERE sd.id = ?
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
                WHERE s.document_id = ?
                UNION ALL
                SELECT 'raw' AS kind, rs.id AS line_id, rs.quantity, rs.unit, rs.unit_price, rs.total, COALESCE(NULLIF(rs.custom_item_name, ''), r.name) AS item_name
                FROM raw_sales rs
                JOIN raw_materials r ON r.id = rs.raw_material_id
                WHERE rs.document_id = ?
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
        return {
            "title": "Facture",
            "subtitle": subtitle,
            "number": f"FAC-{doc['id']:06d}",
            "date": doc["sale_date"],
            "partner_label": "Client",
            "partner_name": doc["partner_name"],
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
        }

    if doc_type == "payment":
        row = query_db(
            """
            SELECT p.*, c.name AS partner_name
            FROM payments p
            JOIN clients c ON c.id = p.client_id
            WHERE p.id = ?
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
        return {
            "title": "Re\u00e7u",
            "subtitle": label,
            "number": f"PAY-{row['id']:06d}",
            "date": row["payment_date"],
            "partner_label": "Client",
            "partner_name": row["partner_name"],
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
        }

    if doc_type == "production":
        row = query_db(
            """
            SELECT pb.*, fp.name AS item_name,
                   COALESCE((
                       SELECT STRING_AGG(r.name || ' ' || CAST(pbi.quantity AS TEXT) || ' ' || r.unit, ' + ' ORDER BY pbi.id)
                       FROM production_batch_items pbi
                       LEFT JOIN raw_materials r ON r.id = pbi.raw_material_id
                       WHERE pbi.batch_id = pb.id
                   ), '') AS recipe_text
            FROM production_batches pb
            JOIN finished_products fp ON fp.id = pb.finished_product_id
            WHERE pb.id = ?
            """,
            (item_id,),
            one=True,
        )
        if not row:
            return None
        recipe_text = row["recipe_text"] or "-"
        lines = [
            {
                "item_name": recipe_text,
                "quantity": row["output_quantity"],
                "unit": "kg",
                "unit_price": row["unit_cost"],
                "total": row["production_cost"],
            }
        ]
        return {
            "title": "Fiche de production",
            "subtitle": "Production enregistree",
            "number": f"PROD-{row['id']:06d}",
            "date": row["production_date"],
            "partner_label": "Produit fini",
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
        }

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
    dark = colors.HexColor("#111827")
    muted = colors.HexColor("#6B7280")
    light = colors.HexColor("#F8FAFC")
    line = colors.HexColor("#D7DEE8")
    story = []

    title_style = ParagraphStyle(
        "print_title",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=16.5,
        leading=18.0,
        textColor=dark,
        spaceAfter=0,
        alignment=TA_CENTER,
    )
    subtitle_style = ParagraphStyle(
        "print_subtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.6,
        leading=10.8,
        textColor=muted,
        alignment=TA_CENTER,
    )
    label_style = ParagraphStyle(
        "print_label",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.0,
        leading=8.6,
        textColor=muted,
    )
    value_style = ParagraphStyle(
        "print_value",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9.0,
        leading=11.2,
        textColor=dark,
    )
    partner_name_style = ParagraphStyle(
        "print_partner_name",
        parent=value_style,
        fontSize=13.0,
        leading=14.2,
        textColor=colors.HexColor("#1F2937"),
    )
    ref_label_style = ParagraphStyle(
        "print_ref_label",
        parent=label_style,
        alignment=TA_RIGHT,
    )
    ref_value_style = ParagraphStyle(
        "print_ref_value",
        parent=value_style,
        alignment=TA_RIGHT,
        fontSize=9.4,
    )
    table_head_style = ParagraphStyle(
        "print_table_head",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.1,
        leading=8.5,
        textColor=colors.HexColor("#374151"),
    )
    cell_style = ParagraphStyle(
        "print_cell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.3,
        leading=10.3,
        textColor=dark,
    )
    cell_bold_style = ParagraphStyle(
        "print_cell_bold",
        parent=cell_style,
        fontName="Helvetica-Bold",
    )
    cell_right_style = ParagraphStyle(
        "print_cell_right",
        parent=cell_style,
        alignment=TA_RIGHT,
    )
    footer_style = ParagraphStyle(
        "print_footer",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.0,
        leading=10.0,
        alignment=TA_CENTER,
        textColor=muted,
    )

    printed_date = str(doc.get("printed_date") or doc.get("date") or "")
    printed_time = str(doc.get("printed_time") or "")
    logo_cell = _logo_cell(BASE_DIR / "static" / "fab_logo.png", 2.8, 2.8)

    partner_box = Table(
        [
            [
                Paragraph(str(doc.get("partner_label", "")), label_style),
                Spacer(1, 0.05 * cm),
                Paragraph(str(doc.get("partner_name", "")), partner_name_style),
            ]
        ],
        colWidths=[4.8 * cm],
    )
    partner_box.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.7, line),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )

    ref_box = Table(
        [
            [Paragraph("Reference", ref_label_style), Paragraph(str(doc.get("number", "")), ref_value_style)],
            [Paragraph("Date", ref_label_style), Paragraph(printed_date, ref_value_style)],
            [Paragraph("Heure", ref_label_style), Paragraph(printed_time or "-", ref_value_style)],
            [Paragraph("Total", ref_label_style), Paragraph(_fmt_money_pdf(doc.get("total", 0)), ref_value_style)],
        ],
        colWidths=[2.2 * cm, 3.2 * cm],
    )
    ref_box.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.7, line),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, line),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )

    party_width = 5.2 * cm
    ref_width = 5.4 * cm
    header_table = Table(
        [
            [
                [logo_cell, Spacer(1, 0.14 * cm), partner_box],
                [Paragraph(str(doc.get("title", "")), title_style), Spacer(1, 0.08 * cm), Paragraph(str(doc.get("subtitle", "")), subtitle_style)],
                ref_box,
            ]
        ],
        colWidths=[party_width, content_width - party_width - ref_width, ref_width],
    )
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
    story.append(Spacer(1, 0.18 * cm))
    story.append(HRFlowable(width="100%", thickness=0.8, color=line))
    story.append(Spacer(1, 0.22 * cm))

    info_table = Table(
        [
            [
                [Paragraph("Préparé par", label_style), Spacer(1, 0.04 * cm), Paragraph(str(printed_by), value_style)],
                [Paragraph("Document", label_style), Spacer(1, 0.04 * cm), Paragraph(str(doc.get("number", "")), value_style)],
            ]
        ],
        colWidths=[content_width / 2.0, content_width / 2.0],
    )
    info_table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.7, line),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, line),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(info_table)
    story.append(Spacer(1, 0.22 * cm))

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
            Paragraph("Quantite", table_head_style),
            Paragraph("PU", table_head_style),
            Paragraph("Total", table_head_style),
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
                Paragraph(total_str, cell_right_style),
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
                ("BACKGROUND", (0, 0), (-1, 0), light),
                ("BOX", (0, 0), (-1, -1), 0.7, line),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, line),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
            ]
        )
    )
    story.append(items_table)
    story.append(Spacer(1, 0.24 * cm))

    summary_rows = []
    if doc.get("paid") is not None:
        summary_rows.append([Paragraph("Paye", label_style), Paragraph(_fmt_money_pdf(doc["paid"]), ref_value_style)])
    if doc.get("due") is not None:
        summary_rows.append([Paragraph("Reste", label_style), Paragraph(_fmt_money_pdf(doc["due"]), ref_value_style)])
    summary_rows.append([Paragraph("Total", label_style), Paragraph(_fmt_money_pdf(doc.get("total", 0)), ref_value_style)])

    summary_table = Table(summary_rows, colWidths=[3.0 * cm, 3.4 * cm], hAlign="RIGHT")
    summary_table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.7, line),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, line),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ]
        )
    )
    story.append(summary_table)

    story.append(Spacer(1, 0.45 * cm))
    story.append(HRFlowable(width="100%", thickness=0.7, color=line))
    story.append(Spacer(1, 0.12 * cm))
    story.append(Paragraph("FABOuanes - Document commercial", footer_style))

    page_doc.build(story)
    buffer.seek(0)
    return buffer
