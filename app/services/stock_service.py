from __future__ import annotations

import logging
from datetime import date
import re
from decimal import Decimal

from sqlalchemy import select, func, update, delete, case
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.async_db import get_async_sessionmaker, ensure_transaction
from app.core.request_state import get_state_value

from app.core.exceptions import ValidationError, NotFoundError
from app.core.helpers import async_compat

OTHER_OPERATION_NAME = "AUTRE"
OTHER_OPERATION_UNIT = "unite"


def _extract_weight_from_unit(unit: str | None) -> float:
    if not unit:
        return 50.0
    match = re.search(r"(\d+(?:\.\d+)?)\s*(?:kg)?", unit.lower())
    if match:
        return float(match.group(1))
    return 50.0


def qty_to_kg(quantity: float, unit: str | None) -> float:
    unit_name = (unit or "kg").strip().lower()
    if unit_name.startswith("sac"):
        return quantity * _extract_weight_from_unit(unit)
    if unit_name in {"qt", "quintal"}:
        return quantity * 100
    return quantity


def unit_price_to_kg(unit_price: float, unit: str | None) -> float:
    unit_name = (unit or "kg").strip().lower()
    if unit_name.startswith("sac"):
        return unit_price / _extract_weight_from_unit(unit)
    if unit_name in {"qt", "quintal"}:
        return unit_price / 100
    return unit_price


def unit_choices() -> list[str]:
    return ["kg", "sac (50kg)", "sac (40kg)", "sac (25kg)", "Qt", "unite"]


def is_other_operation_name(name: str | None) -> bool:
    return str(name or "").strip().casefold() == OTHER_OPERATION_NAME.casefold()


def _actor_username() -> str:
    try:
        user = get_state_value("user")
        if user:
            return str(user["username"])
    except Exception:
        pass
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
        from app.modules.catalog.repository import insert_stock_movement
        await insert_stock_movement(
            item_kind, item_id, direction, quantity, unit,
            stock_before, stock_after, reason, reference_type,
            reference_id, _actor_username(), db=db
        )
        from app.core.perf_cache import invalidate_cache_domains
        invalidate_cache_domains("catalog", "sales_sellable_items", "dashboard")
    except Exception:
        logging.getLogger("fabouanes").warning("Failed to record stock movement for %s #%s", item_kind, item_id, exc_info=True)



@async_compat
async def recalc_raw_material_avg_cost(material_id: int, db: AsyncSession | None = None) -> None:
    async with ensure_transaction(db) as session:
        await _recalc_raw_material_avg_cost_impl(material_id, session)


async def _recalc_raw_material_avg_cost_impl(material_id: int, db: AsyncSession) -> None:
    from app.core.models import RawMaterial, Purchase

    material = (await db.execute(select(RawMaterial).where(RawMaterial.id == material_id))).scalar_one_or_none()
    if not material:
        return
    stock_qty = float(material.stock_qty)

    unit_lower = func.lower(func.trim(Purchase.unit))
    factor = case(
        (unit_lower.like("sac%"),
         case(
             (unit_lower.like("%50%"), 50.0),
             (unit_lower.like("%40%"), 40.0),
             (unit_lower.like("%25%"), 25.0),
             else_=50.0
         )),
        (unit_lower.in_(["qt", "quintal"]), 100.0),
        else_=1.0
    )
    qty_in_kg = Purchase.quantity * factor

    res = await db.execute(
        select(
            func.coalesce(func.sum(qty_in_kg), 0).label("total_qty_kg"),
            func.coalesce(func.sum(Purchase.total), 0).label("total_value")
        ).where(Purchase.raw_material_id == material_id)
    )
    row = res.first()
    purchased_qty_kg = float(row.total_qty_kg) if row else 0.0
    purchased_value = float(row.total_value) if row else 0.0

    base_qty = max(0.0, stock_qty - purchased_qty_kg)
    total_qty = base_qty + purchased_qty_kg
    total_value = base_qty * float(material.avg_cost) + purchased_value

    await db.execute(
        update(RawMaterial)
        .where(RawMaterial.id == material_id)
        .values(avg_cost=(total_value / total_qty) if total_qty > 0 else 0.0)
    )


@async_compat
async def recalc_finished_product_avg_cost(product_id: int, db: AsyncSession | None = None) -> None:
    async with ensure_transaction(db) as session:
        await _recalc_finished_product_avg_cost_impl(product_id, session)


async def _recalc_finished_product_avg_cost_impl(product_id: int, db: AsyncSession) -> None:
    from app.core.models import FinishedProduct, ProductionBatch

    product = (await db.execute(select(FinishedProduct).where(FinishedProduct.id == product_id))).scalar_one_or_none()
    if not product:
        return
    stock_qty = float(product.stock_qty)

    res = await db.execute(
        select(
            func.coalesce(func.sum(ProductionBatch.output_quantity), 0).label("total_qty"),
            func.coalesce(func.sum(ProductionBatch.production_cost), 0).label("total_cost")
        ).where(ProductionBatch.finished_product_id == product_id)
    )
    row = res.first()
    produced_qty = float(row.total_qty) if row else 0.0
    produced_cost = float(row.total_cost) if row else 0.0

    base_qty = max(0.0, stock_qty - produced_qty)
    total_qty = base_qty + produced_qty
    total_value = base_qty * float(product.avg_cost) + produced_cost

    await db.execute(
        update(FinishedProduct)
        .where(FinishedProduct.id == product_id)
        .values(avg_cost=(total_value / total_qty) if total_qty > 0 else 0.0)
    )


@async_compat
async def recalc_purchase_document_totals(document_id: int | None, db: AsyncSession | None = None) -> None:
    if not document_id:
        return
    async with ensure_transaction(db) as session:
        await _recalc_purchase_document_totals_impl(document_id, session)


async def _recalc_purchase_document_totals_impl(document_id: int, db: AsyncSession) -> None:
    from app.core.models import Purchase, PurchaseDocument

    totals_res = await db.execute(
        select(
            func.count().label("line_count"),
            func.coalesce(func.sum(Purchase.total), 0).label("total_amount")
        )
        .where(Purchase.document_id == document_id)
    )
    totals = totals_res.first()

    if not totals or int(totals.line_count or 0) <= 0:
        await db.execute(delete(PurchaseDocument).where(PurchaseDocument.id == document_id))
        return
    await db.execute(
        update(PurchaseDocument)
        .where(PurchaseDocument.id == document_id)
        .values(total=float(totals.total_amount or 0))
    )


@async_compat
async def recalc_sale_document_totals(document_id: int | None, db: AsyncSession | None = None) -> None:
    if not document_id:
        return
    async with ensure_transaction(db) as session:
        await _recalc_sale_document_totals_impl(document_id, session)


async def _recalc_sale_document_totals_impl(document_id: int, db: AsyncSession) -> None:
    from app.core.models import Sale, RawSale, SaleDocument

    finished_res = await db.execute(
        select(
            func.count().label("line_count"),
            func.coalesce(func.sum(Sale.total), 0).label("total_amount"),
            func.coalesce(func.sum(Sale.amount_paid), 0).label("paid_amount"),
            func.coalesce(func.sum(Sale.balance_due), 0).label("due_amount")
        )
        .where(Sale.document_id == document_id)
    )
    finished = finished_res.first()

    raw_res = await db.execute(
        select(
            func.count().label("line_count"),
            func.coalesce(func.sum(RawSale.total), 0).label("total_amount"),
            func.coalesce(func.sum(RawSale.amount_paid), 0).label("paid_amount"),
            func.coalesce(func.sum(RawSale.balance_due), 0).label("due_amount")
        )
        .where(RawSale.document_id == document_id)
    )
    raw = raw_res.first()

    line_count = int((finished.line_count if finished else 0) or 0) + int((raw.line_count if raw else 0) or 0)
    if line_count <= 0:
        await db.execute(delete(SaleDocument).where(SaleDocument.id == document_id))
        return

    total = float((finished.total_amount if finished else 0) or 0) + float((raw.total_amount if raw else 0) or 0)
    paid = float((finished.paid_amount if finished else 0) or 0) + float((raw.paid_amount if raw else 0) or 0)
    due = float((finished.due_amount if finished else 0) or 0) + float((raw.due_amount if raw else 0) or 0)

    await db.execute(
        update(SaleDocument)
        .where(SaleDocument.id == document_id)
        .values(total=total, amount_paid=paid, balance_due=due)
    )


@async_compat
async def refresh_sale_profits_for_item(item_kind: str, item_id: int, avg_cost: float, sale_price: float | None = None, db: AsyncSession | None = None) -> None:
    async with ensure_transaction(db) as session:
        await _refresh_sale_profits_for_item_impl(item_kind, item_id, avg_cost, sale_price, session)


async def _refresh_sale_profits_for_item_impl(item_kind: str, item_id: int, avg_cost: float, sale_price: float | None, db: AsyncSession) -> None:
    from app.core.models import Sale, RawSale

    if item_kind == "raw":
        unit_lower = func.lower(func.trim(RawSale.unit))
        factor = case(
            (unit_lower.like("sac%"),
             case(
                 (unit_lower.like("%50%"), 50.0),
                 (unit_lower.like("%40%"), 40.0),
                 (unit_lower.like("%25%"), 25.0),
                 else_=50.0
             )),
            (unit_lower.in_(["qt", "quintal"]), 100.0),
            else_=1.0
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
        (unit_lower.like("sac%"),
         case(
             (unit_lower.like("%50%"), 50.0),
             (unit_lower.like("%40%"), 40.0),
             (unit_lower.like("%25%"), 25.0),
             else_=50.0
         )),
        (unit_lower.in_(["qt", "quintal"]), 100.0),
        else_=1.0
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
    async with ensure_transaction(db) as session:
        return await _create_purchase_record_impl(
            supplier_id, item_kind_or_raw_id, qty, unit_price,
            purchase_date, notes, unit, document_id, custom_item_name, item_id, session
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
    from app.core.models import RawMaterial, FinishedProduct, Purchase

    if isinstance(item_kind_or_raw_id, (int, float)) or (isinstance(item_kind_or_raw_id, str) and item_kind_or_raw_id.isdigit()):
        item_kind = "raw"
        real_item_id = int(item_kind_or_raw_id)
    else:
        item_kind = str(item_kind_or_raw_id).strip().lower()
        real_item_id = int(item_id) if item_id is not None else 0

    if qty <= 0:
        raise ValidationError("La quantité doit être supérieure à zéro.", field="quantity")
    if unit_price < 0:
        raise ValidationError("Le prix unitaire ne peut pas être négatif.", field="unit_price")

    if purchase_date and purchase_date > date.today().isoformat():
        raise ValidationError("La date d'achat ne peut pas être dans le futur.", field="purchase_date")

    custom_item_name = str(custom_item_name or "").strip()
    total = qty * unit_price
    qty_kg = qty_to_kg(qty, unit)
    unit_price_kg = unit_price_to_kg(unit_price, unit)

    if item_kind == "raw":
        material_res = await db.execute(select(RawMaterial).where(RawMaterial.id == real_item_id))
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
            custom_item_name=custom_item_name
        )
        db.add(p)
        await db.flush()
        purchase_id = p.id

        stock_before = float(material.stock_qty)
        stock_after = stock_before + qty_kg
        current_value = stock_before * float(material.avg_cost)
        added_value = qty_kg * unit_price_kg
        avg_cost = (current_value + added_value) / stock_after if stock_after > 0 else 0
        sale_price = float(material.sale_price) or unit_price

        material.stock_qty = Decimal(str(stock_after))
        material.avg_cost = Decimal(str(avg_cost))
        material.sale_price = Decimal(str(sale_price))
        await db.flush()
        await record_stock_movement("raw", real_item_id, "in", qty_kg, "kg", stock_before, stock_after, "create_purchase", "purchase", purchase_id, db=db)
    else:
        product_res = await db.execute(select(FinishedProduct).where(FinishedProduct.id == real_item_id))
        product = product_res.scalar_one_or_none()
        if not product:
            raise NotFoundError("Produit fini", real_item_id)

        p = Purchase(
            supplier_id=supplier_id,
            document_id=document_id,
            raw_material_id=None,
            finished_product_id=real_item_id,
            quantity=Decimal(str(qty_kg)),
            unit=unit,
            unit_price=Decimal(str(unit_price_kg)),
            total=Decimal(str(total)),
            purchase_date=purchase_date,
            notes=notes,
            custom_item_name=custom_item_name
        )
        db.add(p)
        await db.flush()
        purchase_id = p.id

        stock_before = float(product.stock_qty)
        stock_after = stock_before + qty_kg
        current_value = stock_before * float(product.avg_cost)
        added_value = qty_kg * unit_price_kg
        avg_cost = (current_value + added_value) / stock_after if stock_after > 0 else 0
        sale_price = float(product.sale_price) or unit_price

        product.stock_qty = Decimal(str(stock_after))
        product.avg_cost = Decimal(str(avg_cost))
        product.sale_price = Decimal(str(sale_price))
        await db.flush()
        await record_stock_movement("finished", real_item_id, "in", qty_kg, "kg", stock_before, stock_after, "create_purchase", "purchase", purchase_id, db=db)

    await _recalc_purchase_document_totals_impl(document_id, db)
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
    async with ensure_transaction(db) as session:
        return await _create_sale_record_impl(
            client_id, item_kind, item_id, qty, unit, unit_price,
            sale_type, sale_date, notes, amount_paid_input, document_id, custom_item_name, session
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
    from app.core.models import FinishedProduct, RawMaterial, Sale, RawSale, Payment

    total = qty * unit_price
    requested_sale_type = (sale_type or "").strip().lower()
    if requested_sale_type not in {"cash", "credit"}:
        requested_sale_type = "credit" if client_id else "cash"
    if requested_sale_type == "credit" and not client_id:
        raise ValidationError("Une vente à crédit nécessite un client.", field="client_id")
    amount_paid = total if requested_sale_type == "cash" else max(0.0, min(float(amount_paid_input or 0), total))
    balance_due = round(total - amount_paid, 2)
    if qty <= 0:
        raise ValidationError("La quantité doit être supérieure à zéro.", field="quantity")
    if sale_date and sale_date > date.today().isoformat():
        raise ValidationError("La date de vente ne peut pas être dans le futur.", field="sale_date")

    if item_kind == "finished":
        qty_kg = qty_to_kg(qty, unit)
        unit_price_kg = unit_price_to_kg(unit_price, unit)
        item_res = await db.execute(select(FinishedProduct).where(FinishedProduct.id == item_id))
        item = item_res.scalar_one_or_none()
        if not item:
            raise NotFoundError("Produit fini", item_id)

        stock_before = float(item.stock_qty)
        if qty_kg > stock_before:
            raise ValidationError(f"Stock produit insuffisant (disponible: {stock_before:.2f} kg, requis: {qty_kg:.2f} kg).", field="quantity")

        cost_snapshot = float(item.avg_cost)
        profit_amount = total - qty_kg * cost_snapshot

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
            notes=notes
        )
        db.add(s)
        await db.flush()
        row_id = s.id

        stock_after = stock_before - qty_kg
        item.stock_qty = Decimal(str(stock_after))
        await db.flush()
        await record_stock_movement("finished", item_id, "out", qty_kg, "kg", stock_before, stock_after, "create_sale", "sale", row_id, db=db)

        if amount_paid > 0 and client_id:
            p = Payment(
                client_id=client_id,
                sale_id=row_id,
                sale_kind="finished",
                payment_type="versement",
                amount=Decimal(str(amount_paid)),
                payment_date=sale_date,
                notes="Paiement initial vente"
            )
            db.add(p)
            await db.flush()

        await _recalc_sale_document_totals_impl(document_id, db)
        if unit_price_kg < cost_snapshot * 0.97 and cost_snapshot > 0:
            _flash_warning(f"Vente sous coût : {unit_price_kg:.2f} DA/kg < coût de revient {cost_snapshot:.2f} DA/kg.")
        return "finished", row_id

    item_res = await db.execute(select(RawMaterial).where(RawMaterial.id == item_id))
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

    qty_kg = qty_to_kg(qty, unit)
    unit_price_kg = unit_price_to_kg(unit_price, unit)
    stock_before = float(item.stock_qty)
    if qty_kg > stock_before:
        raise ValidationError(f"Stock matière insuffisant (disponible: {stock_before:.2f} kg, requis: {qty_kg:.2f} kg).", field="quantity")

    cost_snapshot = float(item.avg_cost)
    profit_amount = total - qty_kg * cost_snapshot

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
        custom_item_name=custom_item_name
    )
    db.add(rs)
    await db.flush()
    row_id = rs.id

    stock_after = stock_before - qty_kg
    item.stock_qty = Decimal(str(stock_after))
    await db.flush()
    await record_stock_movement("raw", item_id, "out", qty_kg, "kg", stock_before, stock_after, "create_sale", "raw_sale", row_id, db=db)

    if amount_paid > 0 and client_id:
        p = Payment(
            client_id=client_id,
            raw_sale_id=row_id,
            sale_kind="raw",
            payment_type="versement",
            amount=Decimal(str(amount_paid)),
            payment_date=sale_date,
            notes="Paiement initial vente"
        )
        db.add(p)
        await db.flush()

    await _recalc_sale_document_totals_impl(document_id, db)
    if unit_price_kg < cost_snapshot * 0.97 and cost_snapshot > 0:
        _flash_warning(f"Vente sous coût : {unit_price_kg:.2f} DA/kg < coût de revient {cost_snapshot:.2f} DA/kg.")
    return "raw", row_id


@async_compat
async def reverse_purchase(purchase_id: int, db: AsyncSession | None = None) -> bool:
    async with ensure_transaction(db) as session:
        return await _reverse_purchase_impl(purchase_id, session)


async def _reverse_purchase_impl(purchase_id: int, db: AsyncSession) -> bool:
    from app.core.models import Purchase, FinishedProduct, RawMaterial

    row_res = await db.execute(select(Purchase).where(Purchase.id == purchase_id))
    row = row_res.scalar_one_or_none()
    if not row:
        return False

    if row.finished_product_id:
        product_res = await db.execute(select(FinishedProduct).where(FinishedProduct.id == row.finished_product_id))
        product = product_res.scalar_one_or_none()
        if not product or float(product.stock_qty) < float(row.quantity):
            return False
        stock_before = float(product.stock_qty)
        stock_after = stock_before - float(row.quantity)

        current_value = stock_before * float(product.avg_cost)
        removed_value = float(row.quantity) * float(row.unit_price)
        restored_value = current_value - removed_value
        avg_cost_restored = restored_value / stock_after if stock_after > 0 else float(product.avg_cost)

        product.stock_qty = Decimal(str(stock_after))
        product.avg_cost = Decimal(str(avg_cost_restored))
        await db.delete(row)
        await db.flush()
        await record_stock_movement("finished", int(row.finished_product_id), "out", float(row.quantity), "kg", stock_before, stock_after, "reverse_purchase", "purchase", purchase_id, db=db)
    else:
        material_res = await db.execute(select(RawMaterial).where(RawMaterial.id == row.raw_material_id))
        material = material_res.scalar_one_or_none()
        qty_kg = qty_to_kg(float(row.quantity), row.unit)
        if not material or float(material.stock_qty) < qty_kg:
            return False
        stock_before = float(material.stock_qty)
        stock_after = stock_before - qty_kg

        current_value = stock_before * float(material.avg_cost)
        removed_value = float(row.quantity) * float(row.unit_price)
        restored_value = current_value - removed_value
        avg_cost_restored = restored_value / stock_after if stock_after > 0 else float(material.avg_cost)

        material.stock_qty = Decimal(str(stock_after))
        material.avg_cost = Decimal(str(avg_cost_restored))
        await db.delete(row)
        await db.flush()
        await record_stock_movement("raw", int(row.raw_material_id), "out", qty_kg, "kg", stock_before, stock_after, "reverse_purchase", "purchase", purchase_id, db=db)

    if row.document_id:
        await _recalc_purchase_document_totals_impl(int(row.document_id), db)
    return True


@async_compat
async def reverse_sale(kind: str, row_id: int, db: AsyncSession | None = None) -> bool:
    async with ensure_transaction(db) as session:
        return await _reverse_sale_impl(kind, row_id, session)


async def _reverse_sale_impl(kind: str, row_id: int, db: AsyncSession) -> bool:
    from app.core.models import Sale, RawSale, FinishedProduct, RawMaterial, Payment

    if kind == "finished":
        row_res = await db.execute(select(Sale).where(Sale.id == row_id))
        row = row_res.scalar_one_or_none()
        if not row:
            return False
        product_res = await db.execute(select(FinishedProduct).where(FinishedProduct.id == row.finished_product_id))
        product = product_res.scalar_one_or_none()
        stock_before = float(product.stock_qty if product else 0)
        restore_qty = qty_to_kg(float(row.quantity), row.unit)
        stock_after = stock_before + restore_qty
        if product:
            product.stock_qty = Decimal(str(stock_after))
        await db.execute(delete(Payment).where(Payment.sale_kind == "finished", Payment.sale_id == row_id))
        await db.delete(row)
        await db.flush()
        await record_stock_movement("finished", int(row.finished_product_id), "in", restore_qty, "kg", stock_before, stock_after, "reverse_sale", "sale", row_id, db=db)
        if row.document_id:
            await _recalc_sale_document_totals_impl(int(row.document_id), db)
        return True

    row_res = await db.execute(select(RawSale).where(RawSale.id == row_id))
    row = row_res.scalar_one_or_none()
    if not row:
        return False
    material_res = await db.execute(select(RawMaterial).where(RawMaterial.id == row.raw_material_id))
    material = material_res.scalar_one_or_none()
    stock_before = float(material.stock_qty if material else 0)
    restore_qty = qty_to_kg(float(row.quantity), row.unit)
    stock_after = stock_before + restore_qty
    if material:
        material.stock_qty = Decimal(str(stock_after))
    await db.execute(delete(Payment).where(Payment.sale_kind == "raw", Payment.raw_sale_id == row_id))
    await db.delete(row)
    await db.flush()
    await record_stock_movement("raw", int(row.raw_material_id), "in", restore_qty, "kg", stock_before, stock_after, "reverse_sale", "raw_sale", row_id, db=db)
    if row.document_id:
        await _recalc_sale_document_totals_impl(int(row.document_id), db)
    return True


@async_compat
async def apply_raw_material_consumption(material, qty: float, reference_type: str, reference_id: int, reason: str = "production", db: AsyncSession | None = None) -> None:
    async with ensure_transaction(db) as session:
        await _apply_raw_material_consumption_impl(material, qty, reference_type, reference_id, reason, session)


async def _apply_raw_material_consumption_impl(material, qty: float, reference_type: str, reference_id: int, reason: str, db: AsyncSession) -> None:
    from app.core.models import RawMaterial

    material_id = int(material["id"])
    db_material_res = await db.execute(select(RawMaterial).where(RawMaterial.id == material_id))
    db_material = db_material_res.scalar_one_or_none()
    if not db_material:
        raise ValueError(f"Matière première introuvable: {material_id}")
    stock_before = float(db_material.stock_qty)
    stock_after = stock_before - float(qty)
    if stock_after < -1e-9:
        raise ValueError(f"Stock insuffisant pour {db_material.name}.")
    db_material.stock_qty = Decimal(str(stock_after))
    await db.flush()
    await record_stock_movement("raw", material_id, "out", float(qty), "kg", stock_before, stock_after, reason, reference_type, reference_id, db=db)


@async_compat
async def apply_finished_production(product, output_qty: float, total_cost: float, reference_id: int, db: AsyncSession | None = None) -> None:
    async with ensure_transaction(db) as session:
        await _apply_finished_production_impl(product, output_qty, total_cost, reference_id, session)


async def _apply_finished_production_impl(product, output_qty: float, total_cost: float, reference_id: int, db: AsyncSession) -> None:
    from app.core.models import FinishedProduct

    product_id = int(product["id"])
    db_product_res = await db.execute(select(FinishedProduct).where(FinishedProduct.id == product_id))
    db_product = db_product_res.scalar_one_or_none()
    if not db_product:
        raise ValueError(f"Produit fini introuvable: {product_id}")
    stock_before = float(db_product.stock_qty)
    current_value = stock_before * float(db_product.avg_cost)
    new_value = current_value + float(total_cost)
    stock_after = stock_before + float(output_qty)
    new_avg = (new_value / stock_after) if stock_after > 0 else 0
    sale_price = float(db_product.sale_price) if float(db_product.sale_price) > 0 else new_avg * 1.15

    db_product.stock_qty = Decimal(str(stock_after))
    db_product.avg_cost = Decimal(str(new_avg))
    db_product.sale_price = Decimal(str(sale_price))
    await db.flush()
    await record_stock_movement("finished", product_id, "in", float(output_qty), "kg", stock_before, stock_after, "create_production", "production", reference_id, db=db)


@async_compat
async def reverse_production(batch_id: int, db: AsyncSession | None = None) -> bool:
    async with ensure_transaction(db) as session:
        return await _reverse_production_impl(batch_id, session)


async def _reverse_production_impl(batch_id: int, db: AsyncSession) -> bool:
    from app.core.models import ProductionBatch, ProductionBatchItem, FinishedProduct, RawMaterial

    batch_res = await db.execute(select(ProductionBatch).where(ProductionBatch.id == batch_id))
    batch = batch_res.scalar_one_or_none()
    if not batch:
        return False
    product_res = await db.execute(select(FinishedProduct).where(FinishedProduct.id == batch.finished_product_id))
    product = product_res.scalar_one_or_none()
    if not product or float(product.stock_qty) < float(batch.output_quantity):
        return False
    items_res = await db.execute(select(ProductionBatchItem).where(ProductionBatchItem.batch_id == batch_id))
    items = items_res.scalars().all()
    for item in items:
        material_res = await db.execute(select(RawMaterial).where(RawMaterial.id == item.raw_material_id))
        material = material_res.scalar_one_or_none()
        material = material_res.scalar_one_or_none()
        stock_before = float(material.stock_qty if material else 0)
        stock_after = stock_before + float(item.quantity)
        if material:
            material.stock_qty = Decimal(str(stock_after))
        await db.flush()
        await record_stock_movement("raw", int(item.raw_material_id), "in", float(item.quantity), "kg", stock_before, stock_after, "reverse_production", "production", batch_id, db=db)
        await _recalc_raw_material_avg_cost_impl(int(item.raw_material_id), db)
    stock_before = float(product.stock_qty)
    stock_after = stock_before - float(batch.output_quantity)

    current_value = stock_before * float(product.avg_cost)
    removed_value = float(batch.production_cost)
    restored_value = current_value - removed_value
    avg_cost_restored = restored_value / stock_after if stock_after > 0 else float(product.avg_cost)

    product.stock_qty = Decimal(str(stock_after))
    product.avg_cost = Decimal(str(avg_cost_restored))
    await db.flush()
    await record_stock_movement("finished", int(batch.finished_product_id), "out", float(batch.output_quantity), "kg", stock_before, stock_after, "reverse_production", "production", batch_id, db=db)
    await db.delete(batch)
    await db.flush()
    return True
