from __future__ import annotations

from urllib.parse import quote
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.async_db import get_async_sessionmaker
from app.core.helpers import async_compat
from app.utils.tool_pages import list_pdf_reader_files

DEFAULT_LIMIT = 80


def _as_float(value) -> float:
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def _doc(
    *,
    key: str,
    kind: str,
    category: str,
    title: str,
    number: str,
    doc_date: str,
    partner_name: str = "",
    detail: str = "",
    amount=None,
    view_url: str,
    pdf_url: str = "",
    source_url: str = "",
    delete_filename: str = "",
) -> dict:
    return {
        "key": key,
        "kind": kind,
        "category": category,
        "title": title,
        "number": number,
        "doc_date": str(doc_date or ""),
        "partner_name": str(partner_name or ""),
        "detail": str(detail or ""),
        "amount": amount,
        "view_url": view_url,
        "pdf_url": pdf_url,
        "source_url": source_url,
        "delete_filename": delete_filename,
        "search_text": " ".join(
            str(part or "")
            for part in (category, title, number, doc_date, partner_name, detail)
        ).lower(),
    }


def _print_doc(doc_type: str, item_id: int, **payload) -> dict:
    view_url = f"/print/{doc_type}/{item_id}"
    return _doc(
        key=f"{doc_type}:{item_id}",
        view_url=view_url,
        pdf_url=f"{view_url}?format=pdf",
        **payload,
    )


async def _append_purchase_documents(documents: list[dict], limit: int, db: AsyncSession) -> None:
    res1 = await db.execute(
        text("""
        SELECT pd.id, pd.purchase_date, pd.total, pd.notes,
               COALESCE(s.name, 'Non renseigne') AS partner_name
        FROM purchase_documents pd
        LEFT JOIN suppliers s ON s.id = pd.supplier_id
        ORDER BY pd.purchase_date DESC, pd.id DESC
        LIMIT :limit
        """),
        {"limit": limit},
    )
    for row in res1.all():
        documents.append(
            _print_doc(
                "purchase_document",
                int(row.id),
                kind="purchase",
                category="Achats",
                title="Bon d'achat",
                number=f"ACH-{int(row.id):06d}",
                doc_date=row.purchase_date,
                partner_name=row.partner_name,
                detail=row.notes or "Achat multi-produits",
                amount=_as_float(row.total),
                source_url="/operations?type=purchase",
            )
        )

    res2 = await db.execute(
        text("""
        SELECT p.id, p.purchase_date, p.total, p.notes,
               COALESCE(s.name, 'Non renseigne') AS partner_name,
               COALESCE(NULLIF(p.custom_item_name, ''), rm.name) AS item_name
        FROM purchases p
        JOIN raw_materials rm ON rm.id = p.raw_material_id
        LEFT JOIN suppliers s ON s.id = p.supplier_id
        WHERE p.document_id IS NULL
        ORDER BY p.purchase_date DESC, p.id DESC
        LIMIT :limit
        """),
        {"limit": limit},
    )
    for row in res2.all():
        documents.append(
            _print_doc(
                "purchase",
                int(row.id),
                kind="purchase",
                category="Achats",
                title="Bon d'achat",
                number=f"ACH-{int(row.id):06d}",
                doc_date=row.purchase_date,
                partner_name=row.partner_name,
                detail=row.item_name or row.notes or "",
                amount=_as_float(row.total),
                source_url="/operations?type=purchase",
            )
        )


async def _append_sale_documents(documents: list[dict], limit: int, db: AsyncSession) -> None:
    res1 = await db.execute(
        text("""
        SELECT sd.id, sd.sale_date, sd.total, sd.sale_type, sd.notes,
               COALESCE(c.name, 'Comptoir') AS partner_name
        FROM sale_documents sd
        LEFT JOIN clients c ON c.id = sd.client_id
        ORDER BY sd.sale_date DESC, sd.id DESC
        LIMIT :limit
        """),
        {"limit": limit},
    )
    for row in res1.all():
        documents.append(
            _print_doc(
                "sale_document",
                int(row.id),
                kind="sale",
                category="Ventes",
                title="Bon de vente",
                number=f"FAC-{int(row.id):06d}",
                doc_date=row.sale_date,
                partner_name=row.partner_name,
                detail="Credit" if row.sale_type == "credit" else "Comptant",
                amount=_as_float(row.total),
                source_url="/operations?type=sale",
            )
        )

    res2 = await db.execute(
        text("""
        SELECT s.id, s.sale_date, s.total, s.sale_type, s.notes,
               COALESCE(c.name, 'Comptoir') AS partner_name,
               fp.name AS item_name
        FROM sales s
        JOIN finished_products fp ON fp.id = s.finished_product_id
        LEFT JOIN clients c ON c.id = s.client_id
        WHERE s.document_id IS NULL
        ORDER BY s.sale_date DESC, s.id DESC
        LIMIT :limit
        """),
        {"limit": limit},
    )
    for row in res2.all():
        documents.append(
            _print_doc(
                "sale_finished",
                int(row.id),
                kind="sale",
                category="Ventes",
                title="Bon de vente",
                number=f"VPF-{int(row.id):06d}",
                doc_date=row.sale_date,
                partner_name=row.partner_name,
                detail=row.item_name or "",
                amount=_as_float(row.total),
                source_url="/operations?type=sale",
            )
        )

    res3 = await db.execute(
        text("""
        SELECT rs.id, rs.sale_date, rs.total, rs.sale_type, rs.notes,
               COALESCE(c.name, 'Comptoir') AS partner_name,
               COALESCE(NULLIF(rs.custom_item_name, ''), rm.name) AS item_name
        FROM raw_sales rs
        JOIN raw_materials rm ON rm.id = rs.raw_material_id
        LEFT JOIN clients c ON c.id = rs.client_id
        WHERE rs.document_id IS NULL
        ORDER BY rs.sale_date DESC, rs.id DESC
        LIMIT :limit
        """),
        {"limit": limit},
    )
    for row in res3.all():
        documents.append(
            _print_doc(
                "sale_raw",
                int(row.id),
                kind="sale",
                category="Ventes",
                title="Bon de vente matiere",
                number=f"VMP-{int(row.id):06d}",
                doc_date=row.sale_date,
                partner_name=row.partner_name,
                detail=row.item_name or "",
                amount=_as_float(row.total),
                source_url="/operations?type=sale",
            )
        )


async def _append_payment_documents(documents: list[dict], limit: int, db: AsyncSession) -> None:
    res = await db.execute(
        text("""
        SELECT p.id, p.payment_date, p.amount, p.payment_type, p.notes,
               c.name AS partner_name
        FROM payments p
        JOIN clients c ON c.id = p.client_id
        ORDER BY p.payment_date DESC, p.id DESC
        LIMIT :limit
        """),
        {"limit": limit},
    )
    for row in res.all():
        is_advance = str(row.payment_type or "").lower() == "avance"
        documents.append(
            _print_doc(
                "payment",
                int(row.id),
                kind="advance" if is_advance else "payment",
                category="Avances" if is_advance else "Versements",
                title="Bon d'avance" if is_advance else "Bon de versement",
                number=f"PAY-{int(row.id):06d}",
                doc_date=row.payment_date,
                partner_name=row.partner_name,
                detail=row.notes or ("Avance client" if is_advance else "Versement client"),
                amount=_as_float(row.amount),
                source_url="/operations?type=payment",
            )
        )


async def _append_production_documents(documents: list[dict], limit: int, db: AsyncSession) -> None:
    res = await db.execute(
        text("""
        SELECT pb.id, pb.production_date, pb.production_cost, pb.output_quantity, pb.notes,
               fp.name AS product_name
        FROM production_batches pb
        JOIN finished_products fp ON fp.id = pb.finished_product_id
        ORDER BY pb.production_date DESC, pb.id DESC
        LIMIT :limit
        """),
        {"limit": limit},
    )
    for row in res.all():
        detail = f"{row.output_quantity} kg"
        if row.notes:
            detail = f"{detail} - {row.notes}"
        documents.append(
            _print_doc(
                "production",
                int(row.id),
                kind="production",
                category="Production",
                title="Bon de production",
                number=f"PROD-{int(row.id):06d}",
                doc_date=row.production_date,
                partner_name=row.product_name,
                detail=detail,
                amount=_as_float(row.production_cost),
                source_url="/production",
            )
        )


async def _append_client_history_documents(documents: list[dict], limit: int, db: AsyncSession) -> None:
    res = await db.execute(
        text("""
        SELECT c.id, c.name, c.phone, c.address, c.created_at,
               COUNT(ich.id) AS imported_rows
        FROM clients c
        LEFT JOIN imported_client_history ich ON ich.client_id = c.id
        GROUP BY c.id, c.name, c.phone, c.address, c.created_at
        ORDER BY c.name ASC
        LIMIT :limit
        """),
        {"limit": limit},
    )
    for row in res.all():
        client_id = int(row.id)
        imported_rows = int(row.imported_rows or 0)
        detail = row.phone or row.address or ""
        if imported_rows:
            detail = f"{detail} - {imported_rows} ligne(s) importee(s)" if detail else f"{imported_rows} ligne(s) importee(s)"
        documents.append(
            _doc(
                key=f"client_history:{client_id}",
                kind="client_history",
                category="Clients",
                title="Historique client",
                number=f"HIS-{client_id}",
                doc_date=row.created_at,
                partner_name=row.name,
                detail=detail,
                amount=None,
                view_url=f"/contacts/clients/{client_id}/print-history",
                pdf_url="",
                source_url=f"/contacts/clients/{client_id}",
            )
        )


def _append_external_pdfs(documents: list[dict]) -> None:
    for filename in list_pdf_reader_files():
        safe = quote(filename)
        documents.append(
            _doc(
                key=f"pdf:{filename}",
                kind="external",
                category="PDF importes",
                title="PDF importe",
                number=filename,
                doc_date="",
                partner_name="",
                detail=filename,
                amount=None,
                view_url=f"/pdf-reader/file/{safe}",
                pdf_url=f"/pdf-reader/file/{safe}",
                delete_filename=filename,
            )
        )


@async_compat
async def list_bon_space_documents(
    q: str = "",
    kind: str = "",
    limit: int = DEFAULT_LIMIT,
    db: AsyncSession | None = None,
) -> list[dict]:
    if db is None:
        async with get_async_sessionmaker()() as session:
            return await _list_bon_space_documents_impl(q, kind, limit, session)
    return await _list_bon_space_documents_impl(q, kind, limit, db)


async def _list_bon_space_documents_impl(
    q: str,
    kind: str,
    limit: int,
    db: AsyncSession,
) -> list[dict]:
    limit = max(20, min(int(limit or DEFAULT_LIMIT), 200))
    source_limit = max(limit, 80)
    documents: list[dict] = []
    
    await _append_purchase_documents(documents, source_limit, db)
    await _append_sale_documents(documents, source_limit, db)
    await _append_payment_documents(documents, source_limit, db)
    await _append_production_documents(documents, source_limit, db)
    await _append_client_history_documents(documents, source_limit, db)
    _append_external_pdfs(documents)

    normalized_kind = str(kind or "").strip().lower()
    if normalized_kind:
        documents = [item for item in documents if item["kind"] == normalized_kind]

    terms = [part.lower() for part in str(q or "").split() if part.strip()]
    if terms:
        documents = [
            item
            for item in documents
            if all(term in item["search_text"] for term in terms)
        ]

    def sort_key(item: dict) -> tuple[str, str]:
        return (str(item.get("doc_date") or ""), str(item.get("number") or ""))

    return sorted(documents, key=sort_key, reverse=True)[:limit]


def find_bon_space_document(documents: list[dict], selected_key: str = "") -> dict | None:
    selected_key = str(selected_key or "").strip()
    if selected_key:
        for item in documents:
            if item["key"] == selected_key:
                return item
        return None
    return documents[0] if documents else None
