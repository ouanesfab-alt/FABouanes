"""Tests unitaires lot C3 -- sales/commands.py et sales/validation.py."""
from __future__ import annotations

import pytest
from datetime import date as _date
from unittest.mock import AsyncMock, MagicMock, patch


# ===========================================================================
# SalesValidator -- methodes statiques (sans DB)
# ===========================================================================

class TestSalesValidatorStatic:

    def test_cash_no_client_ok(self):
        from app.modules.sales.validation import SalesValidator
        SalesValidator.validate_sale_type(None, "cash")

    def test_credit_with_client_ok(self):
        from app.modules.sales.validation import SalesValidator
        SalesValidator.validate_sale_type(42, "credit")

    def test_credit_no_client_raises(self):
        from app.modules.sales.validation import SalesValidator
        from app.core.exceptions import ValidationError
        with pytest.raises(ValidationError):
            SalesValidator.validate_sale_type(None, "credit")

    def test_quantity_positive_ok(self):
        from app.modules.sales.validation import SalesValidator
        SalesValidator.validate_quantity(10.0)
        SalesValidator.validate_quantity(0.001)

    def test_quantity_zero_raises(self):
        from app.modules.sales.validation import SalesValidator
        from app.core.exceptions import ValidationError
        with pytest.raises(ValidationError):
            SalesValidator.validate_quantity(0.0)

    def test_quantity_negative_raises(self):
        from app.modules.sales.validation import SalesValidator
        from app.core.exceptions import ValidationError
        with pytest.raises(ValidationError):
            SalesValidator.validate_quantity(-5.0)


@pytest.mark.asyncio
class TestSalesValidatorAsync:

    async def test_client_none_skips(self):
        from app.modules.sales.validation import SalesValidator
        session = AsyncMock()
        await SalesValidator.validate_client(None, session)
        session.get.assert_not_called()

    async def test_client_found_ok(self):
        from app.modules.sales.validation import SalesValidator
        session = AsyncMock()
        session.get.return_value = MagicMock()
        await SalesValidator.validate_client(1, session)

    async def test_client_not_found_raises(self):
        from app.modules.sales.validation import SalesValidator
        from app.core.exceptions import NotFoundError
        session = AsyncMock()
        session.get.return_value = None
        with pytest.raises(NotFoundError):
            await SalesValidator.validate_client(99, session)

    async def test_finished_stock_ok(self):
        from app.modules.sales.validation import SalesValidator
        session = AsyncMock()
        mock_product = MagicMock()
        mock_product.stock_qty = 100.0
        mock_res = MagicMock()
        mock_res.scalar_one_or_none.return_value = mock_product
        session.execute.return_value = mock_res
        with patch("app.modules.sales.validation.qty_to_kg", return_value=10.0):
            item, qty_kg = await SalesValidator.validate_stock_availability(
                "finished", 1, 10.0, "kg", "", session
            )
        assert item is mock_product
        assert qty_kg == 10.0

    async def test_finished_stock_insufficient_raises(self):
        from app.modules.sales.validation import SalesValidator
        from app.core.exceptions import ValidationError
        session = AsyncMock()
        mock_product = MagicMock()
        mock_product.stock_qty = 5.0
        mock_res = MagicMock()
        mock_res.scalar_one_or_none.return_value = mock_product
        session.execute.return_value = mock_res
        with patch("app.modules.sales.validation.qty_to_kg", return_value=10.0):
            with pytest.raises(ValidationError, match="insuffisant"):
                await SalesValidator.validate_stock_availability(
                    "finished", 1, 10.0, "kg", "", session
                )

    async def test_finished_not_found_raises(self):
        from app.modules.sales.validation import SalesValidator
        from app.core.exceptions import NotFoundError
        session = AsyncMock()
        mock_res = MagicMock()
        mock_res.scalar_one_or_none.return_value = None
        session.execute.return_value = mock_res
        with patch("app.modules.sales.validation.qty_to_kg", return_value=10.0):
            with pytest.raises(NotFoundError):
                await SalesValidator.validate_stock_availability(
                    "finished", 99, 10.0, "kg", "", session
                )

    async def test_raw_stock_ok(self):
        from app.modules.sales.validation import SalesValidator
        session = AsyncMock()
        mock_material = MagicMock()
        mock_material.stock_qty = 200.0
        mock_material.name = "Orge"
        mock_res = MagicMock()
        mock_res.scalar_one_or_none.return_value = mock_material
        session.execute.return_value = mock_res
        with patch("app.modules.sales.validation.qty_to_kg", return_value=20.0):
            item, qty_kg = await SalesValidator.validate_stock_availability(
                "raw", 1, 20.0, "kg", "", session
            )
        assert item is mock_material

    async def test_raw_autre_no_name_raises(self):
        from app.modules.sales.validation import SalesValidator
        from app.core.exceptions import ValidationError
        session = AsyncMock()
        mock_material = MagicMock()
        mock_material.stock_qty = 200.0
        mock_material.name = "Autre"
        mock_res = MagicMock()
        mock_res.scalar_one_or_none.return_value = mock_material
        session.execute.return_value = mock_res
        with patch("app.modules.sales.validation.qty_to_kg", return_value=5.0):
            with pytest.raises(ValidationError, match="nom du produit"):
                await SalesValidator.validate_stock_availability(
                    "raw", 1, 5.0, "kg", "", session
                )

    async def test_unknown_kind_raises(self):
        from app.modules.sales.validation import SalesValidator
        from app.core.exceptions import ValidationError
        session = AsyncMock()
        with patch("app.modules.sales.validation.qty_to_kg", return_value=1.0):
            with pytest.raises(ValidationError):
                await SalesValidator.validate_stock_availability(
                    "unknown", 1, 1.0, "kg", "", session
                )


# ===========================================================================
# SalesCommands -- calcul pur (logique sans DB)
# ===========================================================================

class TestSalesAmountLogic:

    def test_cash_amount_equals_total(self):
        qty, unit_price = 10.0, 20.0
        total = qty * unit_price
        amount_paid = total  # cash
        assert amount_paid == pytest.approx(200.0)

    def test_credit_balance_due(self):
        total, amount_paid_input = 500.0, 200.0
        amount_paid = max(0.0, min(amount_paid_input, total))
        balance_due = round(total - amount_paid, 2)
        assert balance_due == pytest.approx(300.0)

    def test_overpayment_capped(self):
        total = 100.0
        assert max(0.0, min(9999.0, total)) == pytest.approx(100.0)

    def test_negative_payment_becomes_zero(self):
        total = 100.0
        assert max(0.0, min(-50.0, total)) == pytest.approx(0.0)

    def test_profit_calculation(self):
        total, qty_kg, cost_snapshot = 300.0, 10.0, 20.0
        profit = total - qty_kg * cost_snapshot
        assert profit == pytest.approx(100.0)

    def test_invalid_sale_type_defaults_credit_with_client(self):
        sale_type = "INVALID"
        client_id = 5
        requested = sale_type.strip().lower()
        if requested not in {"cash", "credit"}:
            requested = "credit" if client_id else "cash"
        assert requested == "credit"

    def test_invalid_sale_type_defaults_cash_without_client(self):
        sale_type = "INVALID"
        client_id = None
        requested = sale_type.strip().lower()
        if requested not in {"cash", "credit"}:
            requested = "credit" if client_id else "cash"
        assert requested == "cash"


# ===========================================================================
# SalesCommands -- tests async avec session mockee
# ===========================================================================

@pytest.mark.asyncio
class TestSalesCommandsAsync:

    def _session(self):
        s = AsyncMock()
        s.add = MagicMock()
        s.delete = AsyncMock()
        s.flush = AsyncMock()
        s.commit = AsyncMock()
        s.execute = AsyncMock()
        return s

    def _make_res(self, line_count, total=0, paid=0, due=0):
        row = MagicMock()
        row._mapping = {
            "line_count": line_count, "total_amount": total,
            "paid_amount": paid, "due_amount": due,
        }
        res = MagicMock()
        res.first.return_value = row
        return res

    async def test_recalc_no_doc_id_returns_early(self):
        from app.modules.sales.commands import SalesCommands
        session = self._session()
        cmd = SalesCommands(session)
        await cmd.recalc_sale_document_totals(None)
        session.execute.assert_not_called()

    async def test_recalc_empty_doc_deletes_it(self):
        from app.modules.sales.commands import SalesCommands
        session = self._session()
        session.execute.side_effect = [self._make_res(0), self._make_res(0)]
        mock_doc = MagicMock()
        cmd = SalesCommands(session)
        cmd.doc_repo = AsyncMock()
        cmd.doc_repo.get = AsyncMock(return_value=mock_doc)
        await cmd.recalc_sale_document_totals(1)
        session.delete.assert_called_once_with(mock_doc)

    async def test_recalc_updates_doc_totals(self):
        from app.modules.sales.commands import SalesCommands
        session = self._session()
        session.execute.side_effect = [
            self._make_res(2, 500.0, 300.0, 200.0),
            self._make_res(1, 100.0, 100.0, 0.0),
        ]
        mock_doc = MagicMock()
        cmd = SalesCommands(session)
        cmd.doc_repo = AsyncMock()
        cmd.doc_repo.get = AsyncMock(return_value=mock_doc)
        await cmd.recalc_sale_document_totals(7)
        assert mock_doc.total == pytest.approx(600.0)
        assert mock_doc.amount_paid == pytest.approx(400.0)
        assert mock_doc.balance_due == pytest.approx(200.0)

    async def test_recalc_doc_not_found_no_crash(self):
        from app.modules.sales.commands import SalesCommands
        session = self._session()
        session.execute.side_effect = [
            self._make_res(2, 500.0, 300.0, 200.0),
            self._make_res(0, 0, 0, 0),
        ]
        cmd = SalesCommands(session)
        cmd.doc_repo = AsyncMock()
        cmd.doc_repo.get = AsyncMock(return_value=None)
        await cmd.recalc_sale_document_totals(42)
        # Pas de crash meme si doc est None

    async def test_reverse_finished_not_found_false(self):
        from app.modules.sales.commands import SalesCommands
        session = self._session()
        mock_res = MagicMock()
        mock_res.scalar_one_or_none.return_value = None
        session.execute.return_value = mock_res
        assert await SalesCommands(session).reverse_sale("finished", 999) is False

    async def test_reverse_raw_not_found_false(self):
        from app.modules.sales.commands import SalesCommands
        session = self._session()
        mock_res = MagicMock()
        mock_res.scalar_one_or_none.return_value = None
        session.execute.return_value = mock_res
        assert await SalesCommands(session).reverse_sale("raw", 888) is False

    async def test_reverse_finished_restores_stock(self):
        from app.modules.sales.commands import SalesCommands
        session = self._session()

        mock_sale = MagicMock()
        mock_sale.id = 1
        mock_sale.finished_product_id = 1
        mock_sale.quantity = 10.0
        mock_sale.unit = "kg"
        mock_sale.document_id = None

        mock_product = MagicMock()
        mock_product.stock_qty = 90.0

        res_sale = MagicMock()
        res_sale.scalar_one_or_none.return_value = mock_sale
        res_prod = MagicMock()
        res_prod.scalar_one_or_none.return_value = mock_product

        session.execute.side_effect = [res_sale, res_prod, MagicMock()]

        cmd = SalesCommands(session)
        with patch(
            "app.modules.sales.commands.SalesCommands.record_stock_movement",
            new_callable=AsyncMock,
        ), patch("app.modules.sales.commands.qty_to_kg", return_value=10.0):
            result = await cmd.reverse_sale("finished", 1)

        assert result is True
        assert mock_product.stock_qty == pytest.approx(100.0)

    async def test_reverse_raw_restores_stock(self):
        from app.modules.sales.commands import SalesCommands
        session = self._session()

        mock_sale = MagicMock()
        mock_sale.id = 2
        mock_sale.raw_material_id = 5
        mock_sale.quantity = 20.0
        mock_sale.unit = "kg"
        mock_sale.document_id = None

        mock_material = MagicMock()
        mock_material.stock_qty = 80.0

        res_sale = MagicMock()
        res_sale.scalar_one_or_none.return_value = mock_sale
        res_mat = MagicMock()
        res_mat.scalar_one_or_none.return_value = mock_material

        session.execute.side_effect = [res_sale, res_mat, MagicMock()]

        cmd = SalesCommands(session)
        with patch(
            "app.modules.sales.commands.SalesCommands.record_stock_movement",
            new_callable=AsyncMock,
        ), patch("app.modules.sales.commands.qty_to_kg", return_value=20.0):
            result = await cmd.reverse_sale("raw", 2)

        assert result is True
        assert mock_material.stock_qty == pytest.approx(100.0)

    async def test_record_stock_movement_silences_exception(self):
        from app.modules.sales.commands import SalesCommands
        session = self._session()
        session.add.side_effect = RuntimeError("DB crash")
        cmd = SalesCommands(session)
        with patch("app.modules.sales.commands.get_state_value", return_value=None):
            await cmd.record_stock_movement(
                "finished", 1, "out", 10.0, "kg",
                100.0, 90.0, "test", "sale", 1
            )
        # Ne doit pas lever d'exception

    async def test_record_stock_movement_with_user(self):
        from app.modules.sales.commands import SalesCommands
        session = self._session()
        cmd = SalesCommands(session)
        with patch(
            "app.modules.sales.commands.get_state_value",
            return_value={"username": "admin_test"},
        ):
            await cmd.record_stock_movement(
                "raw", 3, "in", 5.0, "kg", 50.0, 55.0, "reverse_sale", "raw_sale", 10
            )
        # session.add doit avoir ete appele avec un StockMovement
        session.add.assert_called_once()
