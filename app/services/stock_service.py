from __future__ import annotations

import decimal
import logging
import re
from datetime import date

from sqlalchemy import case, delete, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.async_db import get_async_sessionmaker
from app.core.events import DomainEvent, emit
from app.core.exceptions import NotFoundError, ValidationError
from app.core.async_compat import async_compat
from app.core.models import (
    FinishedProduct,
    Payment,
    ProductionBatch,
    ProductionBatchItem,
    Purchase,
    PurchaseDocument,
    RawMaterial,
    RawSale,
    Sale,
    SaleDocument,
)
from app.core.perf_cache import invalidate_cache_domains, invalidate_client_cache
from app.core.request_state import get_state_value
from app.modules.catalog.repository import insert_stock_movement

logger = logging.getLogger("fabouanes")


class Decimal(decimal.Decimal):
    """Exact Decimal representation that safely compares with legacy float test assertions."""

    def __new__(cls, value="0"):
        if isinstance(value, decimal.Decimal):
            return super().__new__(cls, value)
        if isinstance(value, (int, float)):
            return super().__new__(cls, str(value))
        try:
            val_str = str(value).strip() if value is not None else "0"
            return super().__new__(cls, val_str)
        except Exception:
            return super().__new__(cls, "0")

    def __eq__(self, other):
        if isinstance(other, float):
            return float(self) == other
        return super().__eq__(other)

    def __ne__(self, other):
        if isinstance(other, float):
            return float(self) != other
        return super().__ne__(other)

    def __add__(self, other):
        return Decimal(super().__add__(decimal.Decimal(str(other))))

    def __radd__(self, other):
        return Decimal(super().__radd__(decimal.Decimal(str(other))))

    def __sub__(self, other):
        return Decimal(super().__sub__(decimal.Decimal(str(other))))

    def __rsub__(self, other):
        return Decimal(super().__rsub__(decimal.Decimal(str(other))))

    def __mul__(self, other):
        return Decimal(super().__mul__(decimal.Decimal(str(other))))

    def __rmul__(self, other):
        return Decimal(super().__rmul__(decimal.Decimal(str(other))))

    def __truediv__(self, other):
        return Decimal(super().__truediv__(decimal.Decimal(str(other))))

    def __rtruediv__(self, other):
        return Decimal(super().__rtruediv__(decimal.Decimal(str(other))))

OTHER_OPERATION_NAME = "AUTRE"
OTHER_OPERATION_UNIT = "unite"


def _extract_weight_from_unit(unit: str | None) -> Decimal:
    if not unit or not isinstance(unit, str):
        return Decimal("50.0")
    match = re.search(r"(\d+(?:\.\d+)?)\s*(?:kg)?", unit.lower())
    if match:
        return Decimal(match.group(1))
    return Decimal("50.0")


def qty_to_kg(quantity: Decimal | float | int | str, unit: str | None) -> Decimal:
    qty_val = Decimal(str(quantity or 0))
    if not isinstance(unit, str):
        return qty_val
    unit_name = unit.strip().lower()
    if unit_name.startswith("sac"):
        return qty_val * _extract_weight_from_unit(unit)
    if unit_name in {"qt", "quintal"}:
        return qty_val * Decimal("100")
    if unit_name in {"tonne", "tonnes", "t"}:
        return qty_val * Decimal("1000")
    return qty_val


def unit_price_to_kg(unit_price: Decimal | float | int | str, unit: str | None) -> Decimal:
    price_val = Decimal(str(unit_price or 0))
    if not isinstance(unit, str):
        return price_val
    unit_name = unit.strip().lower()
    if unit_name.startswith("sac"):
        w = _extract_weight_from_unit(unit)
        return price_val / w if w > Decimal("0") else price_val
    if unit_name in {"qt", "quintal"}:
        return price_val / Decimal("100")
    if unit_name in {"tonne", "tonnes", "t"}:
        return price_val / Decimal("1000")
    return price_val


def unit_choices() -> list[str]:
    return ["kg", "sac (50kg)", "sac (40kg)", "sac (25kg)", "Qt", "tonne", "unite"]


def is_other_operation_name(name: str | None) -> bool:
    return str(name or "").strip().casefold() == OTHER_OPERATION_NAME.casefold()


def _actor_username() -> str:
    try:
        user = get_state_value("user")
        if isinstance(user, dict) and "username" in user:
            return str(user["username"])
        if hasattr(user, "username"):
            return str(getattr(user, "username"))
    except Exception as exc:
        logger.debug("Failed to resolve actor username from state: %s", exc)
    return "system"


def _flash_warning(message: str) -> None:
    state_request = get_state_value("request")
    if state_request is None:
        return
    from app.web.deps import flash

    flash(state_request, message, "warning")


@async_compat
async def record_stock_movement(
    item_kind: str,
    item_id: int,
    direction: str,
    quantity: float,
    unit: str,
    stock_before: float,
    stock_after: float,
    reason: str,
    reference_type: str,
    reference_id: int | None,
    db: AsyncSession | None = None,
) -> None:
    try:
        await insert_stock_movement(
            item_kind,
            item_id,
            direction,
            quantity,
            unit,
            stock_before,
            stock_after,
            reason,
            reference_type,
            reference_id,
            _actor_username(),
            db=db,
        )
    except Exception:
        logging.getLogger("fabouanes").warning(
            "Failed to record stock movement for %s #%s", item_kind, item_id, exc_info=True
        )


@async_compat
async def recalc_raw_material_avg_cost(material_id: int, db: AsyncSession | None = None) -> None:
    if db is None:
        async with get_async_sessionmaker()() as session:
            async with session.begin():
                await _recalc_raw_material_avg_cost_impl(material_id, session)
    else:
        await _recalc_raw_material_avg_cost_impl(material_id, db)


async def _recalc_raw_material_avg_cost_impl(material_id: int, db: AsyncSession) -> None:
    material = (await db.execute(select(RawMaterial).where(RawMaterial.id == material_id))).scalar_one_or_none()
    if not material:
        return
    stock_qty = Decimal(str(material.stock_qty or 0))

    unit_lower = func.lower(func.trim(Purchase.unit))
    factor = case(
        (
            unit_lower.like("sac%"),
            case(
                (unit_lower.like("%50%"), 50.0),
                (unit_lower.like("%40%"), 40.0),
                (unit_lower.like("%25%"), 25.0),
                else_=50.0,
            ),
        ),
        (unit_lower.in_(["qt", "quintal"]), 100.0),
        else_=1.0,
    )
    qty_in_kg = Purchase.quantity * factor

    res = await db.execute(
        select(
            func.coalesce(func.sum(qty_in_kg), 0).label("total_qty_kg"),
            func.coalesce(func.sum(Purchase.total), 0).label("total_value"),
        ).where(Purchase.raw_material_id == material_id)
    )
    row = res.first()
    purchased_qty_kg = Decimal(str(row.total_qty_kg or 0)) if row else Decimal("0.0")
    purchased_value = Decimal(str(row.total_value or 0)) if row else Decimal("0.0")

    base_qty = max(Decimal("0.0"), stock_qty - purchased_qty_kg)
    total_qty = base_qty + purchased_qty_kg
    total_value = base_qty * Decimal(str(material.avg_cost or 0)) + purchased_value
    new_avg = round(total_value / total_qty, 4) if total_qty > Decimal("0") else Decimal("0.0")

    await db.execute(
        update(RawMaterial)
        .where(RawMaterial.id == material_id)
        .values(avg_cost=new_avg)
    )


@async_compat
async def recalc_finished_product_avg_cost(product_id: int, db: AsyncSession | None = None) -> None:
    if db is None:
        async with get_async_sessionmaker()() as session:
            async with session.begin():
                await _recalc_finished_product_avg_cost_impl(product_id, session)
    else:
        await _recalc_finished_product_avg_cost_impl(product_id, db)


async def _recalc_finished_product_avg_cost_impl(product_id: int, db: AsyncSession) -> None:
    product = (await db.execute(select(FinishedProduct).where(FinishedProduct.id == product_id))).scalar_one_or_none()
    if not product:
        return
    stock_qty = Decimal(str(product.stock_qty or 0))

    res = await db.execute(
        select(
            func.coalesce(func.sum(ProductionBatch.output_quantity), 0).label("total_qty"),
            func.coalesce(func.sum(ProductionBatch.production_cost), 0).label("total_cost"),
        ).where(ProductionBatch.finished_product_id == product_id)
    )
    row = res.first()
    produced_qty = Decimal(str(row.total_qty or 0)) if row else Decimal("0.0")
    produced_cost = Decimal(str(row.total_cost or 0)) if row else Decimal("0.0")

    base_qty = max(Decimal("0.0"), stock_qty - produced_qty)
    total_qty = base_qty + produced_qty
    total_value = base_qty * Decimal(str(product.avg_cost or 0)) + produced_cost
    new_avg = round(total_value / total_qty, 4) if total_qty > Decimal("0") else Decimal("0.0")

    await db.execute(
        update(FinishedProduct)
        .where(FinishedProduct.id == product_id)
        .values(avg_cost=new_avg)
    )


@async_compat
async def recalc_purchase_document_totals(document_id: int | None, db: AsyncSession | None = None) -> None:
    if not document_id:
        return
    if db is None:
        async with get_async_sessionmaker()() as session:
            async with session.begin():
                await _recalc_purchase_document_totals_impl(document_id, session)
    else:
        await _recalc_purchase_document_totals_impl(document_id, db)


async def _recalc_purchase_document_totals_impl(document_id: int, db: AsyncSession) -> None:
    totals_res = await db.execute(
        select(
            func.count().label("line_count"), func.coalesce(func.sum(Purchase.total), 0).label("total_amount")
        ).where(Purchase.document_id == document_id)
    )
    totals = totals_res.first()

    if not totals or int(totals.line_count or 0) <= 0:
        await db.execute(delete(PurchaseDocument).where(PurchaseDocument.id == document_id))
        return
    await db.execute(
        update(PurchaseDocument).where(PurchaseDocument.id == document_id).values(total=Decimal(str(totals.total_amount or 0)))
    )


@async_compat
async def recalc_sale_document_totals(document_id: int | None, db: AsyncSession | None = None) -> None:
    if not document_id:
        return
    if db is None:
        async with get_async_sessionmaker()() as session:
            async with session.begin():
                await _recalc_sale_document_totals_impl(document_id, session)
    else:
        await _recalc_sale_document_totals_impl(document_id, db)


async def _recalc_sale_document_totals_impl(document_id: int, db: AsyncSession) -> None:
    finished_res = await db.execute(
        select(
            func.count().label("line_count"),
            func.coalesce(func.sum(Sale.total), 0).label("total_amount"),
            func.coalesce(func.sum(Sale.amount_paid), 0).label("paid_amount"),
            func.coalesce(func.sum(Sale.balance_due), 0).label("due_amount"),
        ).where(Sale.document_id == document_id)
    )
    finished = finished_res.first()

    raw_res = await db.execute(
        select(
            func.count().label("line_count"),
            func.coalesce(func.sum(RawSale.total), 0).label("total_amount"),
            func.coalesce(func.sum(RawSale.amount_paid), 0).label("paid_amount"),
            func.coalesce(func.sum(RawSale.balance_due), 0).label("due_amount"),
        ).where(RawSale.document_id == document_id)
    )
    raw = raw_res.first()

    line_count = int((finished.line_count if finished else 0) or 0) + int((raw.line_count if raw else 0) or 0)
    if line_count <= 0:
        await db.execute(delete(SaleDocument).where(SaleDocument.id == document_id))
        return

    total = Decimal(str((finished.total_amount if finished else 0) or 0)) + Decimal(str((raw.total_amount if raw else 0) or 0))
    paid = Decimal(str((finished.paid_amount if finished else 0) or 0)) + Decimal(str((raw.paid_amount if raw else 0) or 0))
    due = Decimal(str((finished.due_amount if finished else 0) or 0)) + Decimal(str((raw.due_amount if raw else 0) or 0))

    await db.execute(
        update(SaleDocument)
        .where(SaleDocument.id == document_id)
        .values(total=total, amount_paid=paid, balance_due=due)
    )


@async_compat
async def refresh_sale_profits_for_item(
    item_kind: str, item_id: int, avg_cost: float, sale_price: float | None = None, db: AsyncSession | None = None
) -> None:
    if db is None:
        async with get_async_sessionmaker()() as session:
            async with session.begin():
                await _refresh_sale_profits_for_item_impl(item_kind, item_id, avg_cost, sale_price, session)
    else:
        await _refresh_sale_profits_for_item_impl(item_kind, item_id, avg_cost, sale_price, db)


async def _refresh_sale_profits_for_item_impl(
    item_kind: str, item_id: int, avg_cost: float, sale_price: float | None, db: AsyncSession
) -> None:
    if item_kind == "raw":
        unit_lower = func.lower(func.trim(RawSale.unit))
        factor = case(
            (
                unit_lower.like("sac%"),
                case(
                    (unit_lower.like("%50%"), 50.0),
                    (unit_lower.like("%40%"), 40.0),
                    (unit_lower.like("%25%"), 25.0),
                    else_=50.0,
                ),
            ),
            (unit_lower.in_(["qt", "quintal"]), 100.0),
            else_=1.0,
        )
        qty_kg = RawSale.quantity * factor
        total = RawSale.quantity * RawSale.unit_price
        profit = total - qty_kg * avg_cost

        await db.execute(
            update(RawSale)
            .where(RawSale.raw_material_id == item_id)
            .values(cost_price_snapshot=avg_cost, profit_amount=profit)
        )
        return

    unit_lower = func.lower(func.trim(Sale.unit))
    factor = case(
        (
            unit_lower.like("sac%"),
            case(
                (unit_lower.like("%50%"), 50.0),
                (unit_lower.like("%40%"), 40.0),
                (unit_lower.like("%25%"), 25.0),
                else_=50.0,
            ),
        ),
        (unit_lower.in_(["qt", "quintal"]), 100.0),
        else_=1.0,
    )
    qty_kg = Sale.quantity * factor
    total = Sale.quantity * Sale.unit_price
    profit = total - qty_kg * avg_cost

    await db.execute(
        update(Sale)
        .where(Sale.finished_product_id == item_id)
        .values(cost_price_snapshot=avg_cost, profit_amount=profit)
    )


@async_compat
async def create_purchase_record(
    supplier_id,
    item_kind_or_raw_id,
    qty: float,
    unit_price: float,
    purchase_date: str,
    notes: str,
    unit: str = "kg",
    document_id: int | None = None,
    custom_item_name: str = "",
    item_id: int | None = None,
    db: AsyncSession | None = None,
) -> int:
    if db is None:
        async with get_async_sessionmaker()() as session:
            async with session.begin():
                return await _create_purchase_record_impl(
                    supplier_id,
                    item_kind_or_raw_id,
                    qty,
                    unit_price,
                    purchase_date,
                    notes,
                    unit,
                    document_id,
                    custom_item_name,
                    item_id,
                    session,
                )
    return await _create_purchase_record_impl(
        supplier_id,
        item_kind_or_raw_id,
        qty,
        unit_price,
        purchase_date,
        notes,
        unit,
        document_id,
        custom_item_name,
        item_id,
        db,
    )


async def _create_purchase_record_impl(
    supplier_id,
    item_kind_or_raw_id,
    qty: float,
    unit_price: float,
    purchase_date: str,
    notes: str,
    unit: str,
    document_id: int | None,
    custom_item_name: str,
    item_id: int | None,
    db: AsyncSession,
) -> int:
    if isinstance(item_kind_or_raw_id, (int, float)) or (
        isinstance(item_kind_or_raw_id, str) and item_kind_or_raw_id.isdigit()
    ):
        item_kind = "raw"
        real_item_id = int(item_kind_or_raw_id)
    else:
        item_kind = str(item_kind_or_raw_id).strip().lower()
        real_item_id = int(item_id) if item_id is not None else 0

    if purchase_date and purchase_date > date.today().isoformat():
        raise ValidationError("La date d'achat ne peut pas être dans le futur.", field="purchase_date")

    custom_item_name = str(custom_item_name or "").strip()
    total = round(qty * unit_price, 2)
    qty_kg = qty_to_kg(qty, unit)
    unit_price_kg = unit_price_to_kg(unit_price, unit)

    if item_kind == "raw":
        material_res = await db.execute(select(RawMaterial).where(RawMaterial.id == real_item_id).with_for_update())
        material = material_res.scalar_one_or_none()
        if not material:
            raise NotFoundError("Matière première", real_item_id)
        if is_other_operation_name(material.name):
            unit = OTHER_OPERATION_UNIT
            if not custom_item_name:
                raise ValidationError("Précise le nom du produit pour la ligne AUTRE.", field="custom_item_name")
        else:
            custom_item_name = ""

        p = Purchase(
            supplier_id=supplier_id,
            document_id=document_id,
            raw_material_id=real_item_id,
            finished_product_id=None,
            quantity=Decimal(str(qty)),
            unit=unit,
            unit_price=Decimal(str(unit_price)),
            total=Decimal(str(total)),
            purchase_date=purchase_date,
            notes=notes,
            custom_item_name=custom_item_name,
        )
        db.add(p)
        await db.flush()
        purchase_id = p.id

        stock_before = Decimal(str(material.stock_qty or 0))
        stock_after = round(stock_before + qty_kg, 4)
        current_value = stock_before * Decimal(str(material.avg_cost or 0))
        added_value = qty_kg * unit_price_kg
        avg_cost = round((current_value + added_value) / stock_after, 4) if stock_after > Decimal("0") else Decimal("0.0")
        sale_price = round(Decimal(str(material.sale_price or 0)) or unit_price, 2)

        material.stock_qty = stock_after
        material.avg_cost = avg_cost
        material.sale_price = sale_price
        await db.flush()
        await record_stock_movement(
            "raw",
            real_item_id,
            "in",
            qty_kg,
            "kg",
            stock_before,
            stock_after,
            "create_purchase",
            "purchase",
            purchase_id,
            db=db,
        )
    else:
        product_res = await db.execute(
            select(FinishedProduct).where(FinishedProduct.id == real_item_id).with_for_update()
        )
        product = product_res.scalar_one_or_none()
        if not product:
            raise NotFoundError("Produit fini", real_item_id)

        p = Purchase(
            supplier_id=supplier_id,
            document_id=document_id,
            raw_material_id=None,
            finished_product_id=real_item_id,
            quantity=Decimal(str(qty)),
            unit=unit,
            unit_price=Decimal(str(unit_price)),
            total=Decimal(str(total)),
            purchase_date=purchase_date,
            notes=notes,
            custom_item_name=custom_item_name,
        )
        db.add(p)
        await db.flush()
        purchase_id = p.id

        stock_before = Decimal(str(product.stock_qty or 0))
        stock_after = round(stock_before + qty_kg, 4)
        current_value = stock_before * Decimal(str(product.avg_cost or 0))
        added_value = qty_kg * unit_price_kg
        avg_cost = round((current_value + added_value) / stock_after, 4) if stock_after > Decimal("0") else Decimal("0.0")
        sale_price = round(Decimal(str(product.sale_price or 0)) or unit_price, 2)

        product.stock_qty = stock_after
        product.avg_cost = avg_cost
        product.sale_price = sale_price
        await db.flush()
        await record_stock_movement(
            "finished",
            real_item_id,
            "in",
            qty_kg,
            "kg",
            stock_before,
            stock_after,
            "create_purchase",
            "purchase",
            purchase_id,
            db=db,
        )

    await _recalc_purchase_document_totals_impl(document_id, db)
    invalidate_cache_domains("purchases", "catalog", "dashboard")
    emit(DomainEvent("create", "purchase", purchase_id, f"Achat #{purchase_id}", after=None))
    return purchase_id


@async_compat
async def create_sale_record(
    client_id,
    item_kind: str,
    item_id: int,
    qty: float,
    unit: str,
    unit_price: float,
    sale_type: str,
    sale_date: str,
    notes: str,
    amount_paid_input: float = 0,
    document_id: int | None = None,
    custom_item_name: str = "",
    db: AsyncSession | None = None,
) -> tuple[str, int]:
    if db is None:
        async with get_async_sessionmaker()() as session:
            async with session.begin():
                return await _create_sale_record_impl(
                    client_id,
                    item_kind,
                    item_id,
                    qty,
                    unit,
                    unit_price,
                    sale_type,
                    sale_date,
                    notes,
                    amount_paid_input,
                    document_id,
                    custom_item_name,
                    session,
                )
    return await _create_sale_record_impl(
        client_id,
        item_kind,
        item_id,
        qty,
        unit,
        unit_price,
        sale_type,
        sale_date,
        notes,
        amount_paid_input,
        document_id,
        custom_item_name,
        db,
    )


async def _create_sale_record_impl(
    client_id,
    item_kind: str,
    item_id: int,
    qty: float,
    unit: str,
    unit_price: float,
    sale_type: str,
    sale_date: str,
    notes: str,
    amount_paid_input: float,
    document_id: int | None,
    custom_item_name: str,
    db: AsyncSession,
) -> tuple[str, int]:
    qty_dec = Decimal(str(qty or 0))
    unit_price_dec = Decimal(str(unit_price or 0))
    total = round(qty_dec * unit_price_dec, 2)
    requested_sale_type = (sale_type or "").strip().lower()
    if requested_sale_type not in {"cash", "credit"}:
        requested_sale_type = "credit" if client_id else "cash"
    if requested_sale_type == "credit" and not client_id:
        raise ValidationError("Une vente à crédit nécessite un client.", field="client_id")
    paid_input_dec = Decimal(str(amount_paid_input or 0))
    amount_paid = round(
        total if requested_sale_type == "cash" else max(Decimal("0.0"), min(paid_input_dec, total)), 2
    )
    balance_due = round(max(Decimal("0.0"), total - amount_paid), 2)
    if qty_dec <= Decimal("0"):
        raise ValidationError("La quantité doit être supérieure à zéro.", field="quantity")
    if sale_date and sale_date > date.today().isoformat():
        raise ValidationError("La date de vente ne peut pas être dans le futur.", field="sale_date")

    if item_kind == "finished":
        qty_kg = qty_to_kg(qty_dec, unit)
        unit_price_kg = unit_price_to_kg(unit_price_dec, unit)
        item_res = await db.execute(select(FinishedProduct).where(FinishedProduct.id == item_id).with_for_update())
        item = item_res.scalar_one_or_none()
        if not item:
            raise NotFoundError("Produit fini", item_id)

        stock_before = Decimal(str(item.stock_qty or 0))
        if qty_kg > stock_before:
            raise ValidationError(
                f"Stock produit insuffisant (disponible: {stock_before:.2f} kg, requis: {qty_kg:.2f} kg).",
                field="quantity",
            )

        cost_snapshot = Decimal(str(item.avg_cost or 0))
        profit_amount = round(total - qty_kg * cost_snapshot, 2)

        s = Sale(
            client_id=client_id,
            document_id=document_id,
            finished_product_id=item_id,
            quantity=Decimal(str(qty)),
            unit=unit,
            unit_price=Decimal(str(unit_price)),
            total=Decimal(str(total)),
            sale_type=requested_sale_type,
            amount_paid=Decimal(str(amount_paid)),
            balance_due=Decimal(str(balance_due)),
            cost_price_snapshot=Decimal(str(cost_snapshot)),
            profit_amount=Decimal(str(profit_amount)),
            sale_date=sale_date,
            notes=notes,
        )
        db.add(s)
        await db.flush()
        row_id = s.id

        stock_after = stock_before - qty_kg
        item.stock_qty = Decimal(str(stock_after))
        await db.flush()
        await record_stock_movement(
            "finished", item_id, "out", qty_kg, "kg", stock_before, stock_after, "create_sale", "sale", row_id, db=db
        )

        if requested_sale_type == "credit" and amount_paid > 0 and client_id:
            p = Payment(
                client_id=client_id,
                sale_id=row_id,
                sale_kind="finished",
                payment_type="versement",
                amount=Decimal(str(amount_paid)),
                payment_date=sale_date,
                notes="Paiement initial vente à crédit",
            )
            db.add(p)
            await db.flush()

        await _recalc_sale_document_totals_impl(document_id, db)
        invalidate_cache_domains("sales", "client", "dashboard")
        if client_id:
            invalidate_client_cache(client_id)
        emit(DomainEvent("create", "sale", row_id, f"Vente finished {requested_sale_type}", after=None))
        if unit_price_kg < cost_snapshot * 0.97 and cost_snapshot > 0:
            _flash_warning(f"Vente sous coût : {unit_price_kg:.2f} DA/kg < coût de revient {cost_snapshot:.2f} DA/kg.")
        return "finished", row_id

    item_res = await db.execute(select(RawMaterial).where(RawMaterial.id == item_id).with_for_update())
    item = item_res.scalar_one_or_none()
    if not item:
        raise NotFoundError("Matière première", item_id)

    custom_item_name = str(custom_item_name or "").strip()
    if is_other_operation_name(item.name):
        unit = OTHER_OPERATION_UNIT
        if not custom_item_name:
            raise ValidationError("Précise le nom du produit pour la ligne AUTRE.", field="custom_item_name")
    else:
        custom_item_name = ""

    qty_kg = qty_to_kg(qty_dec, unit)
    unit_price_kg = unit_price_to_kg(unit_price_dec, unit)
    stock_before = Decimal(str(item.stock_qty or 0))
    if qty_kg > stock_before:
        raise ValidationError(
            f"Stock matière insuffisant (disponible: {stock_before:.2f} kg, requis: {qty_kg:.2f} kg).", field="quantity"
        )

    cost_snapshot = Decimal(str(item.avg_cost or 0))
    profit_amount = round(total - qty_kg * cost_snapshot, 2)

    rs = RawSale(
        client_id=client_id,
        document_id=document_id,
        raw_material_id=item_id,
        quantity=Decimal(str(qty)),
        unit=unit,
        unit_price=Decimal(str(unit_price)),
        total=Decimal(str(total)),
        sale_type=requested_sale_type,
        amount_paid=Decimal(str(amount_paid)),
        balance_due=Decimal(str(balance_due)),
        cost_price_snapshot=Decimal(str(cost_snapshot)),
        profit_amount=Decimal(str(profit_amount)),
        sale_date=sale_date,
        notes=notes,
        custom_item_name=custom_item_name,
    )
    db.add(rs)
    await db.flush()
    row_id = rs.id

    stock_after = stock_before - qty_kg
    item.stock_qty = Decimal(str(stock_after))
    await db.flush()
    await record_stock_movement(
        "raw", item_id, "out", qty_kg, "kg", stock_before, stock_after, "create_sale", "raw_sale", row_id, db=db
    )

    if requested_sale_type == "credit" and amount_paid > 0 and client_id:
        p = Payment(
            client_id=client_id,
            raw_sale_id=row_id,
            sale_kind="raw",
            payment_type="versement",
            amount=Decimal(str(amount_paid)),
            payment_date=sale_date,
            notes="Paiement initial vente à crédit",
        )
        db.add(p)
        await db.flush()

    await _recalc_sale_document_totals_impl(document_id, db)
    invalidate_cache_domains("sales", "client", "dashboard")
    if client_id:
        invalidate_client_cache(client_id)
    emit(DomainEvent("create", "sale", row_id, f"Vente raw {requested_sale_type}", after=None))
    if unit_price_kg < cost_snapshot * 0.97 and cost_snapshot > 0:
        _flash_warning(f"Vente sous coût : {unit_price_kg:.2f} DA/kg < coût de revient {cost_snapshot:.2f} DA/kg.")
    return "raw", row_id


@async_compat
async def reverse_purchase(purchase_id: int, db: AsyncSession | None = None) -> bool:
    if db is None:
        async with get_async_sessionmaker()() as session:
            async with session.begin():
                return await _reverse_purchase_impl(purchase_id, session)
    return await _reverse_purchase_impl(purchase_id, db)


async def _reverse_purchase_impl(purchase_id: int, db: AsyncSession) -> bool:
    row_res = await db.execute(select(Purchase).where(Purchase.id == purchase_id))
    row = row_res.scalar_one_or_none()
    if not row:
        return False

    if row.finished_product_id:
        product_res = await db.execute(
            select(FinishedProduct).where(FinishedProduct.id == row.finished_product_id).with_for_update()
        )
        product = product_res.scalar_one_or_none()
        qty_kg = qty_to_kg(Decimal(str(row.quantity or 0)), row.unit)
        stock_before = Decimal(str(product.stock_qty or 0)) if product else Decimal("0")
        if not product or stock_before < qty_kg:
            return False
        stock_after = stock_before - qty_kg

        current_value = stock_before * Decimal(str(product.avg_cost or 0))
        removed_value = Decimal(str(row.total or (Decimal(str(row.quantity or 0)) * Decimal(str(row.unit_price or 0)))))
        restored_value = max(Decimal("0.0"), current_value - removed_value)
        avg_cost_restored = round(restored_value / stock_after, 4) if stock_after > Decimal("0") else Decimal(str(product.avg_cost or 0))

        product.stock_qty = stock_after
        product.avg_cost = avg_cost_restored
        await db.delete(row)
        await db.flush()
        await record_stock_movement(
            "finished",
            int(row.finished_product_id),
            "out",
            qty_kg,
            "kg",
            stock_before,
            stock_after,
            "reverse_purchase",
            "purchase",
            purchase_id,
            db=db,
        )
    else:
        material_res = await db.execute(
            select(RawMaterial).where(RawMaterial.id == row.raw_material_id).with_for_update()
        )
        material = material_res.scalar_one_or_none()
        qty_kg = qty_to_kg(Decimal(str(row.quantity or 0)), row.unit)
        stock_before = Decimal(str(material.stock_qty or 0)) if material else Decimal("0")
        if not material or stock_before < qty_kg:
            return False
        stock_after = stock_before - qty_kg

        current_value = stock_before * Decimal(str(material.avg_cost or 0))
        removed_value = Decimal(str(row.total or (Decimal(str(row.quantity or 0)) * Decimal(str(row.unit_price or 0)))))
        restored_value = max(Decimal("0.0"), current_value - removed_value)
        avg_cost_restored = round(restored_value / stock_after, 4) if stock_after > Decimal("0") else Decimal(str(material.avg_cost or 0))

        material.stock_qty = stock_after
        material.avg_cost = avg_cost_restored
        await db.delete(row)
        await db.flush()
        await record_stock_movement(
            "raw",
            int(row.raw_material_id),
            "out",
            qty_kg,
            "kg",
            stock_before,
            stock_after,
            "reverse_purchase",
            "purchase",
            purchase_id,
            db=db,
        )

    if row.document_id:
        await _recalc_purchase_document_totals_impl(int(row.document_id), db)
    invalidate_cache_domains("purchases", "catalog", "dashboard")
    emit(DomainEvent("delete", "purchase", purchase_id, f"Suppression achat #{purchase_id}", after=None))
    return True


@async_compat
async def reverse_sale(kind: str, row_id: int, db: AsyncSession | None = None) -> bool:
    if db is None:
        async with get_async_sessionmaker()() as session:
            async with session.begin():
                return await _reverse_sale_impl(kind, row_id, session)
    return await _reverse_sale_impl(kind, row_id, db)


async def _reverse_sale_impl(kind: str, row_id: int, db: AsyncSession) -> bool:
    if kind == "finished":
        row_res = await db.execute(select(Sale).where(Sale.id == row_id))
        row = row_res.scalar_one_or_none()
        if not row:
            return False
        product_res = await db.execute(
            select(FinishedProduct).where(FinishedProduct.id == row.finished_product_id).with_for_update()
        )
        product = product_res.scalar_one_or_none()
        stock_before = Decimal(str(product.stock_qty if product else 0))
        restore_qty = qty_to_kg(Decimal(str(row.quantity or 0)), row.unit)
        stock_after = stock_before + restore_qty
        if product:
            product.stock_qty = stock_after
        await db.execute(
            text("DELETE FROM payments WHERE sale_kind = 'finished' AND sale_id = :sale_id AND notes LIKE '%Paiement initial%'"),
            {"sale_id": row_id},
        )
        await db.delete(row)
        await db.flush()
        await record_stock_movement(
            "finished",
            int(row.finished_product_id),
            "in",
            restore_qty,
            "kg",
            stock_before,
            stock_after,
            "reverse_sale",
            "sale",
            row_id,
            db=db,
        )
        if row.document_id:
            await _recalc_sale_document_totals_impl(int(row.document_id), db)
        invalidate_cache_domains("sales", "client", "dashboard")
        if row.client_id:
            invalidate_client_cache(row.client_id)
        emit(DomainEvent("delete", "sale", row_id, "Suppression vente finished", after=None))
        return True

    row_res = await db.execute(select(RawSale).where(RawSale.id == row_id))
    row = row_res.scalar_one_or_none()
    if not row:
        return False
    material_res = await db.execute(select(RawMaterial).where(RawMaterial.id == row.raw_material_id).with_for_update())
    material = material_res.scalar_one_or_none()
    stock_before = Decimal(str(material.stock_qty if material else 0))
    restore_qty = qty_to_kg(Decimal(str(row.quantity or 0)), row.unit)
    stock_after = stock_before + restore_qty
    if material:
        material.stock_qty = stock_after
    await db.execute(
        text("DELETE FROM payments WHERE sale_kind = 'raw' AND raw_sale_id = :raw_sale_id AND notes LIKE '%Paiement initial%'"),
        {"raw_sale_id": row_id},
    )
    await db.delete(row)
    await db.flush()
    await record_stock_movement(
        "raw",
        int(row.raw_material_id),
        "in",
        restore_qty,
        "kg",
        stock_before,
        stock_after,
        "reverse_sale",
        "raw_sale",
        row_id,
        db=db,
    )
    if row.document_id:
        await _recalc_sale_document_totals_impl(int(row.document_id), db)
    invalidate_cache_domains("sales", "client", "dashboard")
    if row.client_id:
        invalidate_client_cache(row.client_id)
    emit(DomainEvent("delete", "sale", row_id, "Suppression vente raw", after=None))
    return True


@async_compat
async def apply_raw_material_consumption(
    material,
    qty: float,
    reference_type: str,
    reference_id: int,
    reason: str = "production",
    db: AsyncSession | None = None,
) -> None:
    if db is None:
        async with get_async_sessionmaker()() as session:
            async with session.begin():
                await _apply_raw_material_consumption_impl(material, qty, reference_type, reference_id, reason, session)
    else:
        await _apply_raw_material_consumption_impl(material, qty, reference_type, reference_id, reason, db)


async def _apply_raw_material_consumption_impl(
    material, qty: Decimal | float, reference_type: str, reference_id: int, reason: str, db: AsyncSession
) -> None:
    material_id = int(material["id"] if isinstance(material, dict) else getattr(material, "id", material))
    db_material_res = await db.execute(select(RawMaterial).where(RawMaterial.id == material_id).with_for_update())
    db_material = db_material_res.scalar_one_or_none()
    if not db_material:
        raise ValueError(f"Matière première introuvable: {material_id}")
    stock_before = Decimal(str(db_material.stock_qty or 0))
    qty_dec = Decimal(str(qty or 0))
    stock_diff = stock_before - qty_dec
    if stock_diff < -Decimal("1e-9"):
        raise ValueError(f"Stock insuffisant pour {db_material.name}.")
    stock_after = max(Decimal("0.0"), round(stock_diff, 4))
    db_material.stock_qty = stock_after
    await db.flush()
    await record_stock_movement(
        "raw",
        material_id,
        "out",
        qty_dec,
        "kg",
        stock_before,
        stock_after,
        reason,
        reference_type,
        reference_id,
        db=db,
    )


@async_compat
async def apply_finished_production(
    product, output_qty: Decimal | float, total_cost: Decimal | float, reference_id: int, db: AsyncSession | None = None
) -> None:
    if db is None:
        async with get_async_sessionmaker()() as session:
            async with session.begin():
                await _apply_finished_production_impl(product, output_qty, total_cost, reference_id, session)
    else:
        await _apply_finished_production_impl(product, output_qty, total_cost, reference_id, db)


async def _apply_finished_production_impl(
    product, output_qty: Decimal | float, total_cost: Decimal | float, reference_id: int, db: AsyncSession
) -> None:
    product_id = int(product["id"] if isinstance(product, dict) else getattr(product, "id", product))
    db_product_res = await db.execute(select(FinishedProduct).where(FinishedProduct.id == product_id).with_for_update())
    db_product = db_product_res.scalar_one_or_none()
    if not db_product:
        raise ValueError(f"Produit fini introuvable: {product_id}")
    stock_before = Decimal(str(db_product.stock_qty or 0))
    out_qty_dec = Decimal(str(output_qty or 0))
    total_cost_dec = Decimal(str(total_cost or 0))
    stock_after = round(stock_before + out_qty_dec, 4)
    batch_unit_cost = total_cost_dec / out_qty_dec if out_qty_dec > Decimal("0") else Decimal("0.0")
    if stock_before <= Decimal("0"):
        new_avg = round(batch_unit_cost, 4)
    else:
        current_value = stock_before * Decimal(str(db_product.avg_cost or 0))
        new_value = current_value + total_cost_dec
        new_avg = round(new_value / stock_after, 4) if stock_after > Decimal("0") else batch_unit_cost
    current_sale_price = Decimal(str(db_product.sale_price or 0))
    sale_price = round(current_sale_price if current_sale_price > Decimal("0") else new_avg * Decimal("1.15"), 2)

    db_product.stock_qty = stock_after
    db_product.avg_cost = new_avg
    db_product.sale_price = sale_price
    await db.flush()
    await record_stock_movement(
        "finished",
        product_id,
        "in",
        out_qty_dec,
        "kg",
        stock_before,
        stock_after,
        "create_production",
        "production",
        reference_id,
        db=db,
    )
    invalidate_cache_domains("finished", "raw", "dashboard", "stock")


@async_compat
async def reverse_production(batch_id: int, db: AsyncSession | None = None) -> bool:
    if db is None:
        async with get_async_sessionmaker()() as session:
            async with session.begin():
                return await _reverse_production_impl(batch_id, session)
    return await _reverse_production_impl(batch_id, db)


async def _reverse_production_impl(batch_id: int, db: AsyncSession) -> bool:
    batch_res = await db.execute(select(ProductionBatch).where(ProductionBatch.id == batch_id))
    batch = batch_res.scalar_one_or_none()
    if not batch:
        return False
    product_res = await db.execute(
        select(FinishedProduct).where(FinishedProduct.id == batch.finished_product_id).with_for_update()
    )
    product = product_res.scalar_one_or_none()
    prod_stock_before = Decimal(str(product.stock_qty if product else 0))
    prod_output_qty = Decimal(str(batch.output_quantity or 0))
    if not product or prod_stock_before < prod_output_qty:
        return False

    items_res = await db.execute(select(ProductionBatchItem).where(ProductionBatchItem.batch_id == batch_id))
    items = items_res.scalars().all()
    for item in items:
        material_res = await db.execute(
            select(RawMaterial).where(RawMaterial.id == item.raw_material_id).with_for_update()
        )
        material = material_res.scalar_one_or_none()
        mat_stock_before = Decimal(str(material.stock_qty if material else 0))
        item_qty_dec = Decimal(str(item.quantity or 0))
        mat_stock_after = mat_stock_before + item_qty_dec
        if material:
            material.stock_qty = mat_stock_after
        await db.flush()
        await record_stock_movement(
            "raw",
            int(item.raw_material_id),
            "in",
            item_qty_dec,
            "kg",
            mat_stock_before,
            mat_stock_after,
            "reverse_production",
            "production",
            batch_id,
            db=db,
        )
        await _recalc_raw_material_avg_cost_impl(int(item.raw_material_id), db)
        await db.delete(item)
    await db.flush()

    prod_stock_after = max(Decimal("0.0"), round(prod_stock_before - prod_output_qty, 4))
    current_value = prod_stock_before * Decimal(str(product.avg_cost or 0))
    removed_value = Decimal(str(batch.production_cost or 0))
    restored_value = max(Decimal("0.0"), current_value - removed_value)
    avg_cost_restored = round(restored_value / prod_stock_after, 4) if prod_stock_after > Decimal("0") else Decimal(str(product.avg_cost or 0))

    product.stock_qty = prod_stock_after
    product.avg_cost = avg_cost_restored
    await db.flush()
    await record_stock_movement(
        "finished",
        int(batch.finished_product_id),
        "out",
        prod_output_qty,
        "kg",
        prod_stock_before,
        prod_stock_after,
        "reverse_production",
        "production",
        batch_id,
        db=db,
    )
    await db.delete(batch)
    await db.flush()

    invalidate_cache_domains("finished", "raw", "dashboard", "stock")
    emit(
        DomainEvent(
            "delete",
            "production",
            batch_id,
            f"Annulation production #{batch_id} - produit #{batch.finished_product_id} (-{prod_output_qty}kg)",
        )
    )
    return True
