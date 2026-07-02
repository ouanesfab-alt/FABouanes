from __future__ import annotations

from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.helpers import async_compat
from .base import COMPANY_INFO, PRINT_LAYOUT
from .invoice_printer import generate_invoice_pdf, _generate_invoice_pdf_model
from .purchase_printer import _build_purchase_payload, _build_purchase_document_payload
from .report_printer import (
    _build_sale_finished_payload,
    _build_sale_raw_payload,
    _build_sale_document_payload,
    _build_payment_payload,
)
from .production_printer import _build_production_payload

__all__ = [
    "COMPANY_INFO",
    "PRINT_LAYOUT",
    "generate_invoice_pdf",
    "_generate_invoice_pdf_model",
    "build_print_payload",
]


@async_compat
async def build_print_payload(
    doc_type: str,
    item_id: int,
    db: AsyncSession | None = None,
) -> dict[str, Any] | None:
    """Routing function to load/format raw data for print views/PDFs."""
    if doc_type == "purchase":
        return await _build_purchase_payload(item_id, _build_print_payload=build_print_payload, db=db)
    if doc_type == "purchase_document":
        return await _build_purchase_document_payload(item_id, db=db)
    if doc_type == "sale_finished":
        return await _build_sale_finished_payload(item_id, _build_print_payload=build_print_payload, db=db)
    if doc_type == "sale_raw":
        return await _build_sale_raw_payload(item_id, _build_print_payload=build_print_payload, db=db)
    if doc_type == "sale_document":
        return await _build_sale_document_payload(item_id, db=db)
    if doc_type == "payment":
        return await _build_payment_payload(item_id, db=db)
    if doc_type == "production":
        return await _build_production_payload(item_id, db=db)
    return None
