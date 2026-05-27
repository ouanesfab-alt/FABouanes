from __future__ import annotations

from typing import Any

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


def build_print_payload(doc_type: str, item_id: int) -> dict[str, Any] | None:
    """Routing function to load/format raw data for print views/PDFs."""
    if doc_type == "purchase":
        return _build_purchase_payload(item_id, _build_print_payload=build_print_payload)
    if doc_type == "purchase_document":
        return _build_purchase_document_payload(item_id)
    if doc_type == "sale_finished":
        return _build_sale_finished_payload(item_id, _build_print_payload=build_print_payload)
    if doc_type == "sale_raw":
        return _build_sale_raw_payload(item_id, _build_print_payload=build_print_payload)
    if doc_type == "sale_document":
        return _build_sale_document_payload(item_id)
    if doc_type == "payment":
        return _build_payment_payload(item_id)
    if doc_type == "production":
        return _build_production_payload(item_id)
    return None
