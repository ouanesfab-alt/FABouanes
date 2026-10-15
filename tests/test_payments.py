"""
Tests unitaires complets pour le module Paiements / Règlements (app/modules/payments).
Conforme à la Règle 4 de GEMINI.md.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from unittest import mock
from unittest.mock import MagicMock

import pytest

from app.core.exceptions import ValidationError
from app.core.models import Payment, Sale
from app.modules.payments.schemas import (
    PaymentCreate,
    PaymentCreateSchema,
    PaymentFormSchema,
)
from app.modules.payments.service import PaymentsService


# ── Schemas Tests ─────────────────────────────────────────────────────────────


def test_payment_create_schema_decimal():
    p = PaymentCreate(
        client_id=1,
        amount=Decimal("12500.50"),
        payment_date="2026-06-15",
        payment_type="versement",
    )
    assert p.amount == Decimal("12500.50")
    assert p.payment_type == "versement"


def test_payment_form_schema_decimal_coercion():
    form_data = {
        "client_id": "4",
        "amount": "2500.75",
        "payment_date": date.today().isoformat(),
        "payment_type": "versement",
        "sale_link": "finished:10",
        "notes": "Chèque 123",
    }
    schema = PaymentFormSchema.model_validate(form_data)
    assert schema.client_id == 4
    assert isinstance(schema.amount, Decimal)
    assert schema.amount == Decimal("2500.75")
    assert schema.sale_link == "finished:10"


def test_payment_form_schema_future_date_rejected():
    tomorrow = date.today() + timedelta(days=1)
    with pytest.raises(ValueError, match="futur"):
        PaymentFormSchema(
            client_id=1,
            amount=Decimal("100"),
            payment_date=tomorrow,
        )


def test_payment_create_schema_string_amount_cleaned():
    p = PaymentCreateSchema(
        client_id="2",
        amount=" 1 500,50 ",
    )
    assert p.client_id == 2
    assert p.amount == Decimal("1500.50")


# ── Service Tests ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_apply_payment_to_entry_partial():
    session = mock.AsyncMock()
    service = PaymentsService(session)

    sale = Sale(
        id=5,
        client_id=1,
        finished_product_id=1,
        quantity=Decimal("10.00"),
        unit="kg",
        unit_price=Decimal("100.00"),
        total=Decimal("1000.00"),
        sale_type="credit",
        amount_paid=Decimal("200.00"),
        balance_due=Decimal("800.00"),
        sale_date=date.today(),
    )

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = sale
    session.execute.return_value = mock_res

    paid = await service.apply_payment_to_entry("finished", 5, Decimal("300.00"))

    assert paid == Decimal("300.00")
    assert sale.amount_paid == Decimal("500.00")
    assert sale.balance_due == Decimal("500.00")
    assert session.add.called
    assert session.flush.called


@pytest.mark.asyncio
async def test_apply_payment_to_entry_overpay_capped():
    session = mock.AsyncMock()
    service = PaymentsService(session)

    sale = Sale(
        id=5,
        client_id=1,
        finished_product_id=1,
        quantity=Decimal("10.00"),
        unit="kg",
        unit_price=Decimal("100.00"),
        total=Decimal("1000.00"),
        sale_type="credit",
        amount_paid=Decimal("800.00"),
        balance_due=Decimal("200.00"),
        sale_date=date.today(),
    )

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = sale
    session.execute.return_value = mock_res

    # Attempting to pay 500 when only 200 is due
    paid = await service.apply_payment_to_entry("finished", 5, Decimal("500.00"))

    assert paid == Decimal("200.00")
    assert sale.amount_paid == Decimal("1000.00")
    assert sale.balance_due == Decimal("0.00")


@pytest.mark.asyncio
async def test_create_payment_record_advance():
    session = mock.AsyncMock()
    service = PaymentsService(session)

    # Mock client existence check
    mock_client_res = MagicMock()
    mock_client_res.first.return_value = (1,)
    session.execute.return_value = mock_client_res

    payment_id = await service.create_payment_record(
        client_id=1,
        amount=Decimal("5000.00"),
        payment_date=date.today(),
        notes="Avance sur commande",
        payment_type="avance",
    )

    assert session.add.called
    added_obj = session.add.call_args[0][0]
    assert isinstance(added_obj, Payment)
    assert added_obj.payment_type == "avance"
    assert added_obj.amount == Decimal("5000.00")


@pytest.mark.asyncio
async def test_create_payment_record_zero_amount():
    session = mock.AsyncMock()
    service = PaymentsService(session)

    with pytest.raises(ValidationError, match="supérieur à zéro"):
        await service.create_payment_record(
            client_id=1,
            amount=Decimal("0.00"),
            payment_date=date.today(),
            notes="",
        )


@pytest.mark.asyncio
async def test_reverse_payment_allocations():
    session = mock.AsyncMock()
    service = PaymentsService(session)

    sale = Sale(
        id=5,
        client_id=1,
        finished_product_id=1,
        quantity=Decimal("10.00"),
        unit="kg",
        unit_price=Decimal("100.00"),
        total=Decimal("1000.00"),
        sale_type="credit",
        amount_paid=Decimal("500.00"),
        balance_due=Decimal("500.00"),
        sale_date=date.today(),
    )

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = sale
    session.execute.return_value = mock_res

    # Reversing an allocation of 300
    payment_dict = {
        "payment_type": "versement",
        "allocation_meta": '[{"kind": "finished", "id": 5, "amount": 300.0}]',
    }

    await service.reverse_payment_allocations(payment_dict)

    assert sale.amount_paid == Decimal("200.00")
    assert sale.balance_due == Decimal("800.00")
