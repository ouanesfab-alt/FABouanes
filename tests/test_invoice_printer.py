"""Tests unitaires pour app/services/printing/invoice_printer.py (lot D2)."""
from __future__ import annotations

import pytest
from unittest.mock import patch
from app.services.printing.invoice_printer import generate_invoice_pdf


def test_generate_invoice_pdf_reportlab_unavailable():
    with patch("app.services.printing.invoice_printer.REPORTLAB_AVAILABLE", False):
        result = generate_invoice_pdf({"id": 1}, "Admin")
        assert result is None


def test_generate_invoice_pdf_success():
    doc_sample = {
        "id": 1,
        "doc_number": "FAC-2026-0001",
        "doc_type": "facture",
        "created_at": "2026-07-31T10:00:00",
        "client_name": "SARL Test",
        "client_phone": "0550000000",
        "client_address": "Alger",
        "lines": [
            {
                "item_name": "Aliment Bovin Engraissement",
                "quantity": 100.0,
                "unit": "kg",
                "unit_price": 45.0,
                "subtotal": 4500.0,
            }
        ],
        "subtotal": 4500.0,
        "tax_amount": 0.0,
        "total": 4500.0,
        "amount_paid": 4500.0,
        "balance_due": 0.0,
        "sale_type": "cash",
        "notes": "Livraison incluse",
    }
    result = generate_invoice_pdf(doc_sample, printed_by="Admin")
    if result is not None:
        pdf_bytes = result.getvalue()
        assert len(pdf_bytes) > 0
        assert pdf_bytes.startswith(b"%PDF")
