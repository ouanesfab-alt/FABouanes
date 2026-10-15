"""
Tests unitaires complets pour le module Achats (app/modules/purchases).
Conforme à la Règle 4 de GEMINI.md.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from unittest import mock
from unittest.mock import MagicMock

import pytest

from app.core.exceptions import NotFoundError, ValidationError
from app.core.models import FinishedProduct, Purchase, RawMaterial
from app.modules.purchases.schemas import (
    PurchaseFormSchema,
    PurchaseLineSchema,
    SupplierValidationSchema,
)
from app.modules.purchases.service import PurchaseService, create_supplier_payment


# ── Schemas Tests ─────────────────────────────────────────────────────────────


def test_supplier_validation_schema_valid():
    schema = SupplierValidationSchema(name="Fournisseur Test", phone="0555123456", address="Alger", notes="Fournisseur blé")
    assert schema.name == "Fournisseur Test"
    assert schema.phone == "0555123456"


def test_supplier_validation_schema_empty_name():
    with pytest.raises(ValueError, match="Le nom du fournisseur ne peut pas être vide"):
        SupplierValidationSchema(name="   ")


def test_purchase_line_schema_decimal_coercion():
    line = PurchaseLineSchema(
        raw_material_id="raw:3",
        quantity="15.5",
        unit="kg",
        unit_price=120.75,
        custom_item_name="",
    )
    assert isinstance(line.quantity, Decimal)
    assert line.quantity == Decimal("15.5")
    assert isinstance(line.unit_price, Decimal)
    assert line.unit_price == Decimal("120.75")


def test_purchase_line_schema_invalid_id():
    with pytest.raises(ValueError, match="L'article sélectionné est invalide"):
        PurchaseLineSchema(raw_material_id="invalid_format", quantity=10, unit="kg", unit_price=100)


def test_purchase_form_schema_future_date_rejected():
    tomorrow = date.today() + timedelta(days=1)
    with pytest.raises(ValueError, match="futur"):
        PurchaseFormSchema(
            supplier_id=1,
            purchase_date=tomorrow,
            lines=[PurchaseLineSchema(raw_material_id="raw:1", quantity=1, unit_price=10)],
        )


def test_purchase_form_schema_multipart_parsing():
    form_data = {
        "supplier_id": "5",
        "purchase_date": date.today().isoformat(),
        "notes": "Commande matières",
        "raw_material_id[]": ["raw:1", "raw:2"],
        "quantity[]": ["10", "20.5"],
        "unit[]": ["kg", "sac (50kg)"],
        "unit_price[]": ["100", "4500"],
        "custom_item_name[]": ["", ""],
    }
    schema = PurchaseFormSchema.model_validate(form_data)
    assert schema.supplier_id == 5
    assert len(schema.lines) == 2
    assert schema.lines[0].quantity == Decimal("10")
    assert schema.lines[1].quantity == Decimal("20.5")
    assert schema.lines[1].unit_price == Decimal("4500")


# ── Service Tests ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_purchase_record_raw_material():
    session = mock.AsyncMock()
    session.add = MagicMock()
    service = PurchaseService(session)

    # Mock RawMaterial
    material = RawMaterial(id=1, name="Semoule", stock_qty=Decimal("50.00"), avg_cost=Decimal("40.00"), sale_price=Decimal("60.00"))
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = material
    session.execute.return_value = mock_res

    with mock.patch.object(service, "record_stock_movement", return_value=None), \
         mock.patch.object(service, "recalc_purchase_document_totals", return_value=None):

        purchase_id = await service.create_purchase_record(
            supplier_id=1,
            item_kind="raw",
            item_id=1,
            qty=Decimal("10.00"),
            unit="kg",
            unit_price=Decimal("50.00"),
            purchase_date=date.today(),
            notes="Achat test",
        )

        assert session.add.called
        # Check that stock was updated
        assert material.stock_qty == Decimal("60.00")
        assert material.avg_cost > Decimal("40.00")


@pytest.mark.asyncio
async def test_create_purchase_record_validation():
    session = mock.AsyncMock()
    service = PurchaseService(session)

    with pytest.raises(ValidationError, match="quantité"):
        await service.create_purchase_record(
            supplier_id=1,
            item_kind="raw",
            item_id=1,
            qty=Decimal("0"),
            unit="kg",
            unit_price=Decimal("50"),
            purchase_date=date.today(),
            notes="",
        )

    with pytest.raises(ValidationError, match="prix unitaire"):
        await service.create_purchase_record(
            supplier_id=1,
            item_kind="raw",
            item_id=1,
            qty=Decimal("10"),
            unit="kg",
            unit_price=Decimal("-5"),
            purchase_date=date.today(),
            notes="",
        )


@pytest.mark.asyncio
async def test_reverse_purchase_finished_product():
    session = mock.AsyncMock()
    session.add = MagicMock()
    service = PurchaseService(session)

    purchase_row = Purchase(
        id=10,
        supplier_id=1,
        finished_product_id=2,
        raw_material_id=None,
        quantity=Decimal("5.00"),
        unit="kg",
        unit_price=Decimal("100.00"),
        total=Decimal("500.00"),
        purchase_date=date.today(),
    )
    product = FinishedProduct(id=2, name="Couscous", stock_qty=Decimal("20.00"), avg_cost=Decimal("80.00"), sale_price=Decimal("120.00"))

    mock_res_p = MagicMock()
    mock_res_p.scalar_one_or_none.return_value = purchase_row

    mock_res_prod = MagicMock()
    mock_res_prod.scalar_one_or_none.return_value = product

    session.execute.side_effect = [mock_res_p, mock_res_prod]

    with mock.patch.object(service, "record_stock_movement", return_value=None):
        ok = await service.reverse_purchase(10, recalc=False)
        assert ok is True
        assert product.stock_qty == Decimal("15.00")
        assert session.delete.called


@pytest.mark.asyncio
async def test_reverse_purchase_insufficient_stock():
    session = mock.AsyncMock()
    service = PurchaseService(session)

    purchase_row = Purchase(
        id=10,
        supplier_id=1,
        raw_material_id=1,
        quantity=Decimal("50.00"),
        unit="kg",
        unit_price=Decimal("10.00"),
        total=Decimal("500.00"),
        purchase_date=date.today(),
    )
    # Available stock is only 10kg, cannot reverse 50kg!
    material = RawMaterial(id=1, name="Blé", stock_qty=Decimal("10.00"), avg_cost=Decimal("10.00"), sale_price=Decimal("15.00"))

    mock_res_p = MagicMock()
    mock_res_p.scalar_one_or_none.return_value = purchase_row

    mock_res_mat = MagicMock()
    mock_res_mat.scalar_one_or_none.return_value = material

    session.execute.side_effect = [mock_res_p, mock_res_mat]

    ok = await service.reverse_purchase(10)
    assert ok is False


# ── Supplier Payment Tests ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_supplier_payment_negative_amount():
    with pytest.raises(ValidationError, match="supérieur à 0"):
        await create_supplier_payment(supplier_id=1, amount=0)


@pytest.mark.asyncio
async def test_create_supplier_payment_success():
    mock_session = mock.AsyncMock()

    mock_supplier_check = MagicMock()
    mock_supplier_check.fetchone.return_value = (1,)
    mock_session.execute.return_value = mock_supplier_check

    def mock_add(obj):
        obj.id = 99

    mock_session.add = MagicMock(side_effect=mock_add)

    payment_id = await create_supplier_payment(
        supplier_id=1,
        amount=Decimal("1500.00"),
        payment_type="versement",
        notes="Acompte",
        db=mock_session,
    )
    assert payment_id == 99
    mock_session.add.assert_called_once()


@pytest.mark.asyncio
async def test_create_supplier_payment_supplier_not_found():
    mock_session = mock.AsyncMock()

    mock_supplier_check = MagicMock()
    mock_supplier_check.fetchone.return_value = None

    mock_session.execute.return_value = mock_supplier_check

    with pytest.raises(NotFoundError):
        await create_supplier_payment(
            supplier_id=999,
            amount=Decimal("500.00"),
            db=mock_session,
        )
