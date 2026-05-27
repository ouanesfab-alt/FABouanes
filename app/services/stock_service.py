from __future__ import annotations

import logging
import asyncio
from datetime import date

from app.core.db_access import db_transaction, execute_db_async, query_db_async
from app.core.request_state import get_state_value
from app.repositories.stock_repository import insert_stock_movement
from app.core.exceptions import ValidationError, NotFoundError
from app.repositories.client_repository import async_compat

OTHER_OPERATION_NAME = "AUTRE"
OTHER_OPERATION_UNIT = "unite"


def qty_to_kg(quantity: float, unit: str | None) -> float:
    unit_name = (unit or "kg").strip().lower()
    if unit_name == "sac":
        return quantity * 50
    if unit_name in {"qt", "quintal"}:
        return quantity * 100
    return quantity


def unit_price_to_kg(unit_price: float, unit: str | None) -> float:
    unit_name = (unit or "kg").strip().lower()
    if unit_name == "sac":
        return unit_price / 50
    if unit_name in {"qt", "quintal"}:
        return unit_price / 100
    return unit_price


def unit_choices() -> list[str]:
    return ["kg", "sac", "Qt", "unite"]


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
) -> None:
    try:
        await asyncio.to_thread(insert_stock_movement, item_kind, item_id, direction, quantity, unit, stock_before, stock_after, reason, reference_type, reference_id, _actor_username())
    except Exception as exc:
        logging.getLogger("fabouanes").warning("Failed to record stock movement for %s #%s", item_kind, item_id, exc_info=True)


@async_compat
async def recalc_raw_material_avg_cost(material_id: int) -> None:
    material = await query_db_async("SELECT id, stock_qty, avg_cost FROM raw_materials WHERE id = %s", (material_id,), one=True)
    if not material:
        return
    stock_qty = float(material["stock_qty"])
    purchases = await query_db_async("SELECT quantity, unit_price FROM purchases WHERE raw_material_id = %s ORDER BY purchase_date, id", (material_id,))
    purchased_qty = sum(float(row["quantity"]) for row in purchases)
    base_qty = max(0.0, stock_qty - purchased_qty)
    total_qty = base_qty
    total_value = base_qty * float(material["avg_cost"])
    for row in purchases:
        total_qty += float(row["quantity"])
        total_value += float(row["quantity"]) * float(row["unit_price"])
    await execute_db_async("UPDATE raw_materials SET avg_cost = %s WHERE id = %s", ((total_value / total_qty) if total_qty > 0 else 0.0, material_id))


@async_compat
async def recalc_finished_product_avg_cost(product_id: int) -> None:
    product = await query_db_async("SELECT id, stock_qty, avg_cost FROM finished_products WHERE id = %s", (product_id,), one=True)
    if not product:
        return
    stock_qty = float(product["stock_qty"])
    productions = await query_db_async(
        "SELECT output_quantity, production_cost FROM production_batches WHERE finished_product_id = %s ORDER BY production_date, id",
        (product_id,),
    )
    produced_qty = sum(float(row["output_quantity"]) for row in productions)
    base_qty = max(0.0, stock_qty - produced_qty)
    total_qty = base_qty
    total_value = base_qty * float(product["avg_cost"])
    for row in productions:
        total_qty += float(row["output_quantity"])
        total_value += float(row["production_cost"])
    await execute_db_async("UPDATE finished_products SET avg_cost = %s WHERE id = %s", ((total_value / total_qty) if total_qty > 0 else 0.0, product_id))


@async_compat
async def recalc_purchase_document_totals(document_id: int | None) -> None:
    if not document_id:
        return
    totals = await query_db_async(
        "SELECT COUNT(*) AS line_count, COALESCE(SUM(total), 0) AS total_amount FROM purchases WHERE document_id = %s",
        (document_id,),
        one=True,
    )
    if not totals or int(totals["line_count"] or 0) <= 0:
        await execute_db_async("DELETE FROM purchase_documents WHERE id = %s", (document_id,))
        return
    await execute_db_async("UPDATE purchase_documents SET total = %s WHERE id = %s", (float(totals["total_amount"] or 0), document_id))


@async_compat
async def recalc_sale_document_totals(document_id: int | None) -> None:
    if not document_id:
        return
    finished = await query_db_async(
        "SELECT COUNT(*) AS line_count, COALESCE(SUM(total), 0) AS total_amount, COALESCE(SUM(amount_paid), 0) AS paid_amount, COALESCE(SUM(balance_due), 0) AS due_amount FROM sales WHERE document_id = %s",
        (document_id,),
        one=True,
    )
    raw = await query_db_async(
        "SELECT COUNT(*) AS line_count, COALESCE(SUM(total), 0) AS total_amount, COALESCE(SUM(amount_paid), 0) AS paid_amount, COALESCE(SUM(balance_due), 0) AS due_amount FROM raw_sales WHERE document_id = %s",
        (document_id,),
        one=True,
    )
    line_count = int((finished["line_count"] if finished else 0) or 0) + int((raw["line_count"] if raw else 0) or 0)
    if line_count <= 0:
        await execute_db_async("DELETE FROM sale_documents WHERE id = %s", (document_id,))
        return
    total = float((finished["total_amount"] if finished else 0) or 0) + float((raw["total_amount"] if raw else 0) or 0)
    paid = float((finished["paid_amount"] if finished else 0) or 0) + float((raw["paid_amount"] if raw else 0) or 0)
    due = float((finished["due_amount"] if finished else 0) or 0) + float((raw["due_amount"] if raw else 0) or 0)
    await execute_db_async("UPDATE sale_documents SET total = %s, amount_paid = %s, balance_due = %s WHERE id = %s", (total, paid, due, document_id))


@async_compat
async def refresh_sale_profits_for_item(item_kind: str, item_id: int, avg_cost: float, sale_price: float | None = None) -> None:
    if item_kind == "raw":
        rows = await query_db_async("SELECT id, quantity, unit, unit_price FROM raw_sales WHERE raw_material_id = %s", (item_id,))
        for row in rows:
            qty_kg = qty_to_kg(float(row["quantity"]), row["unit"])
            total = float(row["quantity"]) * float(row["unit_price"])
            await execute_db_async("UPDATE raw_sales SET cost_price_snapshot = %s, profit_amount = %s WHERE id = %s", (avg_cost, total - qty_kg * avg_cost, row["id"]))
        return
    rows = await query_db_async("SELECT id, quantity, unit, unit_price FROM sales WHERE finished_product_id = %s", (item_id,))
    for row in rows:
        qty_kg = qty_to_kg(float(row["quantity"]), row["unit"])
        total = float(row["quantity"]) * float(row["unit_price"])
        await execute_db_async("UPDATE sales SET cost_price_snapshot = %s, profit_amount = %s WHERE id = %s", (avg_cost, total - qty_kg * avg_cost, row["id"]))


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
) -> int:
    with db_transaction():
        if isinstance(item_kind_or_raw_id, (int, float)) or (isinstance(item_kind_or_raw_id, str) and item_kind_or_raw_id.isdigit()):
            item_kind = "raw"
            real_item_id = int(item_kind_or_raw_id)
        else:
            item_kind = str(item_kind_or_raw_id).strip().lower()
            real_item_id = int(item_id) if item_id is not None else 0

        if purchase_date and purchase_date > date.today().isoformat():
            raise ValidationError("La date d'achat ne peut pas être dans le futur.", field="purchase_date")
        
        custom_item_name = str(custom_item_name or "").strip()
        total = qty * unit_price
        qty_kg = qty_to_kg(qty, unit)
        unit_price_kg = unit_price_to_kg(unit_price, unit)

        if item_kind == "raw":
            material = await query_db_async("SELECT * FROM raw_materials WHERE id = %s FOR UPDATE", (real_item_id,), one=True)
            if not material:
                raise NotFoundError("Matière première", real_item_id)
            if is_other_operation_name(material["name"]):
                unit = OTHER_OPERATION_UNIT
                if not custom_item_name:
                    raise ValidationError("Précise le nom du produit pour la ligne AUTRE.", field="custom_item_name")
            else:
                custom_item_name = ""

            purchase_id = await execute_db_async(
                """
                INSERT INTO purchases (supplier_id, document_id, raw_material_id, finished_product_id, quantity, unit, unit_price, total, purchase_date, notes, custom_item_name)
                VALUES (%s, %s, %s, NULL, %s, %s, %s, %s, %s, %s, %s)
                """,
                (supplier_id, document_id, real_item_id, qty, unit, unit_price, total, purchase_date, notes, custom_item_name),
            )
            stock_before = float(material["stock_qty"])
            stock_after = stock_before + qty_kg
            current_value = stock_before * float(material["avg_cost"])
            added_value = qty_kg * unit_price_kg
            avg_cost = (current_value + added_value) / stock_after if stock_after > 0 else 0
            sale_price = float(material["sale_price"]) or unit_price
            await execute_db_async("UPDATE raw_materials SET stock_qty = %s, avg_cost = %s, sale_price = %s WHERE id = %s", (stock_after, avg_cost, sale_price, real_item_id))
            await record_stock_movement("raw", real_item_id, "in", qty_kg, "kg", stock_before, stock_after, "create_purchase", "purchase", purchase_id)
        else:
            product = await query_db_async("SELECT * FROM finished_products WHERE id = %s FOR UPDATE", (real_item_id,), one=True)
            if not product:
                raise NotFoundError("Produit fini", real_item_id)
            
            purchase_id = await execute_db_async(
                """
                INSERT INTO purchases (supplier_id, document_id, raw_material_id, finished_product_id, quantity, unit, unit_price, total, purchase_date, notes, custom_item_name)
                VALUES (%s, %s, NULL, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (supplier_id, document_id, real_item_id, qty_kg, unit, unit_price_kg, total, purchase_date, notes, custom_item_name),
            )
            stock_before = float(product["stock_qty"])
            stock_after = stock_before + qty_kg
            current_value = stock_before * float(product["avg_cost"])
            added_value = qty_kg * unit_price_kg
            avg_cost = (current_value + added_value) / stock_after if stock_after > 0 else 0
            sale_price = float(product["sale_price"]) or unit_price
            await execute_db_async("UPDATE finished_products SET stock_qty = %s, avg_cost = %s, sale_price = %s WHERE id = %s", (stock_after, avg_cost, sale_price, real_item_id))
            await record_stock_movement("finished", real_item_id, "in", qty_kg, "kg", stock_before, stock_after, "create_purchase", "purchase", purchase_id)

        await recalc_purchase_document_totals(document_id)
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
) -> tuple[str, int]:
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

    with db_transaction():
        if item_kind == "finished":
            qty_kg = qty_to_kg(qty, unit)
            unit_price_kg = unit_price_to_kg(unit_price, unit)
            item = await query_db_async("SELECT * FROM finished_products WHERE id = %s FOR UPDATE", (item_id,), one=True)
            if not item:
                raise NotFoundError("Produit fini", item_id)
            stock_before = float(item["stock_qty"])
            if qty_kg > stock_before:
                raise ValidationError(f"Stock produit insuffisant (disponible: {stock_before:.2f} kg, requis: {qty_kg:.2f} kg).", field="quantity")

            cost_snapshot = float(item["avg_cost"])
            profit_amount = total - qty_kg * cost_snapshot
            row_id = await execute_db_async(
                """
                INSERT INTO sales (client_id, document_id, finished_product_id, quantity, unit, unit_price, total, sale_type, amount_paid, balance_due, cost_price_snapshot, profit_amount, sale_date, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (client_id, document_id, item_id, qty, unit, unit_price, total, requested_sale_type, amount_paid, balance_due, cost_snapshot, profit_amount, sale_date, notes),
            )
            stock_after = stock_before - qty_kg
            await execute_db_async("UPDATE finished_products SET stock_qty = %s WHERE id = %s", (stock_after, item_id))
            await record_stock_movement("finished", item_id, "out", qty_kg, "kg", stock_before, stock_after, "create_sale", "sale", row_id)
            if amount_paid > 0 and client_id:
                await execute_db_async(
                    "INSERT INTO payments (client_id, sale_id, sale_kind, payment_type, amount, payment_date, notes) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (client_id, row_id, "finished", "versement", amount_paid, sale_date, "Paiement initial vente"),
                )
            await recalc_sale_document_totals(document_id)
            if unit_price_kg < cost_snapshot * 0.97 and cost_snapshot > 0:
                _flash_warning(f"Vente sous coût : {unit_price_kg:.2f} DA/kg < coût de revient {cost_snapshot:.2f} DA/kg.")
            return "finished", row_id

        item = await query_db_async("SELECT * FROM raw_materials WHERE id = %s FOR UPDATE", (item_id,), one=True)
        if not item:
            raise NotFoundError("Matière première", item_id)
        custom_item_name = str(custom_item_name or "").strip()
        if is_other_operation_name(item["name"]):
            unit = OTHER_OPERATION_UNIT
            if not custom_item_name:
                raise ValidationError("Précise le nom du produit pour la ligne AUTRE.", field="custom_item_name")
        else:
            custom_item_name = ""
        qty_kg = qty_to_kg(qty, unit)
        unit_price_kg = unit_price_to_kg(unit_price, unit)
        stock_before = float(item["stock_qty"])
        if qty_kg > stock_before:
            raise ValidationError(f"Stock matière insuffisant (disponible: {stock_before:.2f} kg, requis: {qty_kg:.2f} kg).", field="quantity")

        cost_snapshot = float(item["avg_cost"])
        profit_amount = total - qty_kg * cost_snapshot
        row_id = await execute_db_async(
            """
            INSERT INTO raw_sales (client_id, document_id, raw_material_id, quantity, unit, unit_price, total, sale_type, amount_paid, balance_due, cost_price_snapshot, profit_amount, sale_date, notes, custom_item_name)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (client_id, document_id, item_id, qty, unit, unit_price, total, requested_sale_type, amount_paid, balance_due, cost_snapshot, profit_amount, sale_date, notes, custom_item_name),
        )
        stock_after = stock_before - qty_kg
        await execute_db_async("UPDATE raw_materials SET stock_qty = %s WHERE id = %s", (stock_after, item_id))
        await record_stock_movement("raw", item_id, "out", qty_kg, "kg", stock_before, stock_after, "create_sale", "raw_sale", row_id)
        if amount_paid > 0 and client_id:
            await execute_db_async(
                "INSERT INTO payments (client_id, raw_sale_id, sale_kind, payment_type, amount, payment_date, notes) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (client_id, row_id, "raw", "versement", amount_paid, sale_date, "Paiement initial vente"),
            )
        await recalc_sale_document_totals(document_id)
        if unit_price_kg < cost_snapshot * 0.97 and cost_snapshot > 0:
            _flash_warning(f"Vente sous coût : {unit_price_kg:.2f} DA/kg < coût de revient {cost_snapshot:.2f} DA/kg.")
        return "raw", row_id


@async_compat
async def reverse_purchase(purchase_id: int) -> bool:
    with db_transaction():
        row = await query_db_async("SELECT * FROM purchases WHERE id = %s", (purchase_id,), one=True)
        if not row:
            return False
        
        if row["finished_product_id"]:
            product = await query_db_async("SELECT * FROM finished_products WHERE id = %s FOR UPDATE", (row["finished_product_id"],), one=True)
            if not product or float(product["stock_qty"]) < float(row["quantity"]):
                return False
            stock_before = float(product["stock_qty"])
            stock_after = stock_before - float(row["quantity"])
            
            current_value = stock_before * float(product["avg_cost"])
            removed_value = float(row["quantity"]) * float(row["unit_price"])
            restored_value = current_value - removed_value
            avg_cost_restored = restored_value / stock_after if stock_after > 0 else float(product["avg_cost"])
            
            await execute_db_async("UPDATE finished_products SET stock_qty = %s, avg_cost = %s WHERE id = %s", (stock_after, avg_cost_restored, row["finished_product_id"]))
            await execute_db_async("DELETE FROM purchases WHERE id = %s", (purchase_id,))
            await record_stock_movement("finished", int(row["finished_product_id"]), "out", float(row["quantity"]), "kg", stock_before, stock_after, "reverse_purchase", "purchase", purchase_id)
        else:
            material = await query_db_async("SELECT * FROM raw_materials WHERE id = %s FOR UPDATE", (row["raw_material_id"],), one=True)
            if not material or float(material["stock_qty"]) < float(row["quantity"]):
                return False
            stock_before = float(material["stock_qty"])
            stock_after = stock_before - float(row["quantity"])
            
            current_value = stock_before * float(material["avg_cost"])
            removed_value = float(row["quantity"]) * float(row["unit_price"])
            restored_value = current_value - removed_value
            avg_cost_restored = restored_value / stock_after if stock_after > 0 else float(material["avg_cost"])
            
            await execute_db_async("UPDATE raw_materials SET stock_qty = %s, avg_cost = %s WHERE id = %s", (stock_after, avg_cost_restored, row["raw_material_id"]))
            await execute_db_async("DELETE FROM purchases WHERE id = %s", (purchase_id,))
            await record_stock_movement("raw", int(row["raw_material_id"]), "out", float(row["quantity"]), "kg", stock_before, stock_after, "reverse_purchase", "purchase", purchase_id)

        if row["document_id"]:
            await recalc_purchase_document_totals(int(row["document_id"]))
        return True


@async_compat
async def reverse_sale(kind: str, row_id: int) -> bool:
    with db_transaction():
        if kind == "finished":
            row = await query_db_async("SELECT * FROM sales WHERE id = %s", (row_id,), one=True)
            if not row:
                return False
            product = await query_db_async("SELECT * FROM finished_products WHERE id = %s FOR UPDATE", (row["finished_product_id"],), one=True)
            stock_before = float(product["stock_qty"] if product else 0)
            restore_qty = qty_to_kg(float(row["quantity"]), row["unit"])
            stock_after = stock_before + restore_qty
            await execute_db_async("UPDATE finished_products SET stock_qty = %s WHERE id = %s", (stock_after, row["finished_product_id"]))
            await execute_db_async("DELETE FROM payments WHERE sale_kind = %s AND sale_id = %s", ("finished", row_id))
            await execute_db_async("DELETE FROM sales WHERE id = %s", (row_id,))
            await record_stock_movement("finished", int(row["finished_product_id"]), "in", restore_qty, "kg", stock_before, stock_after, "reverse_sale", "sale", row_id)
            if row["document_id"]:
                await recalc_sale_document_totals(int(row["document_id"]))
            return True
        row = await query_db_async("SELECT * FROM raw_sales WHERE id = %s", (row_id,), one=True)
        if not row:
            return False
        material = await query_db_async("SELECT * FROM raw_materials WHERE id = %s FOR UPDATE", (row["raw_material_id"],), one=True)
        stock_before = float(material["stock_qty"] if material else 0)
        restore_qty = qty_to_kg(float(row["quantity"]), row["unit"])
        stock_after = stock_before + restore_qty
        await execute_db_async("UPDATE raw_materials SET stock_qty = %s WHERE id = %s", (stock_after, row["raw_material_id"]))
        await execute_db_async("DELETE FROM payments WHERE sale_kind = %s AND raw_sale_id = %s", ("raw", row_id))
        await execute_db_async("DELETE FROM raw_sales WHERE id = %s", (row_id,))
        await record_stock_movement("raw", int(row["raw_material_id"]), "in", restore_qty, "kg", stock_before, stock_after, "reverse_sale", "raw_sale", row_id)
        if row["document_id"]:
            await recalc_sale_document_totals(int(row["document_id"]))
        return True


@async_compat
async def apply_raw_material_consumption(material, qty: float, reference_type: str, reference_id: int, reason: str = "production") -> None:
    material_id = int(material["id"])
    db_material = await query_db_async("SELECT * FROM raw_materials WHERE id = %s FOR UPDATE", (material_id,), one=True)
    if not db_material:
        raise ValueError(f"Matière première introuvable: {material_id}")
    stock_before = float(db_material["stock_qty"])
    stock_after = stock_before - float(qty)
    if stock_after < -1e-9:
        raise ValueError(f"Stock insuffisant pour {db_material['name']}.")
    await execute_db_async("UPDATE raw_materials SET stock_qty = %s WHERE id = %s", (stock_after, material_id))
    await record_stock_movement("raw", material_id, "out", float(qty), "kg", stock_before, stock_after, reason, reference_type, reference_id)


@async_compat
async def apply_finished_production(product, output_qty: float, total_cost: float, reference_id: int) -> None:
    product_id = int(product["id"])
    db_product = await query_db_async("SELECT * FROM finished_products WHERE id = %s FOR UPDATE", (product_id,), one=True)
    if not db_product:
        raise ValueError(f"Produit fini introuvable: {product_id}")
    stock_before = float(db_product["stock_qty"])
    current_value = stock_before * float(db_product["avg_cost"])
    new_value = current_value + float(total_cost)
    stock_after = stock_before + float(output_qty)
    new_avg = (new_value / stock_after) if stock_after > 0 else 0
    sale_price = float(db_product["sale_price"]) if float(db_product["sale_price"]) > 0 else new_avg * 1.15
    await execute_db_async("UPDATE finished_products SET stock_qty = %s, avg_cost = %s, sale_price = %s WHERE id = %s", (stock_after, new_avg, sale_price, product_id))
    await record_stock_movement("finished", product_id, "in", float(output_qty), "kg", stock_before, stock_after, "create_production", "production", reference_id)


@async_compat
async def reverse_production(batch_id: int) -> bool:
    with db_transaction():
        batch = await query_db_async("SELECT * FROM production_batches WHERE id = %s", (batch_id,), one=True)
        if not batch:
            return False
        product = await query_db_async("SELECT * FROM finished_products WHERE id = %s FOR UPDATE", (batch["finished_product_id"],), one=True)
        if not product or float(product["stock_qty"]) < float(batch["output_quantity"]):
            return False
        items = await query_db_async("SELECT * FROM production_batch_items WHERE batch_id = %s", (batch_id,))
        for item in items:
            material = await query_db_async("SELECT * FROM raw_materials WHERE id = %s FOR UPDATE", (item["raw_material_id"],), one=True)
            stock_before = float(material["stock_qty"] if material else 0)
            stock_after = stock_before + float(item["quantity"])
            await execute_db_async("UPDATE raw_materials SET stock_qty = %s WHERE id = %s", (stock_after, item["raw_material_id"]))
            await record_stock_movement("raw", int(item["raw_material_id"]), "in", float(item["quantity"]), "kg", stock_before, stock_after, "reverse_production", "production", batch_id)
            await recalc_raw_material_avg_cost(int(item["raw_material_id"]))
        stock_before = float(product["stock_qty"])
        stock_after = stock_before - float(batch["output_quantity"])
        
        current_value = stock_before * float(product["avg_cost"])
        removed_value = float(batch["production_cost"])
        restored_value = current_value - removed_value
        avg_cost_restored = restored_value / stock_after if stock_after > 0 else float(product["avg_cost"])
        
        await execute_db_async("UPDATE finished_products SET stock_qty = %s, avg_cost = %s WHERE id = %s", (stock_after, avg_cost_restored, batch["finished_product_id"]))
        await record_stock_movement("finished", int(batch["finished_product_id"]), "out", float(batch["output_quantity"]), "kg", stock_before, stock_after, "reverse_production", "production", batch_id)
        await execute_db_async("DELETE FROM production_batches WHERE id = %s", (batch_id,))
        return True
