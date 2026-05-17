from __future__ import annotations

from datetime import date

from app.core.db_access import db_transaction, execute_db, query_db
from app.core.request_state import get_state_value
from app.repositories.stock_repository import insert_stock_movement
from app.core.exceptions import ValidationError, NotFoundError


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


def kg_to_display(quantity_kg: float, unit: str | None) -> float:
    unit_name = (unit or "kg").strip().lower()
    if unit_name == "sac":
        return quantity_kg / 50
    if unit_name in {"qt", "quintal"}:
        return quantity_kg / 100
    return quantity_kg


def unit_display_factor(unit: str | None) -> float:
    unit_name = (unit or "kg").strip().lower()
    if unit_name == "sac":
        return 50.0
    if unit_name in {"qt", "quintal"}:
        return 100.0
    return 1.0


def unit_price_to_display(unit_price_kg: float, unit: str | None) -> float:
    return float(unit_price_kg or 0) * unit_display_factor(unit)


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


def record_stock_movement(
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
        insert_stock_movement(item_kind, item_id, direction, quantity, unit, stock_before, stock_after, reason, reference_type, reference_id, _actor_username())
    except Exception:
        pass


def recalc_raw_material_avg_cost(material_id: int) -> None:
    material = query_db("SELECT id, stock_qty, avg_cost FROM raw_materials WHERE id = ?", (material_id,), one=True)
    if not material:
        return
    stock_qty = float(material["stock_qty"])
    purchases = query_db("SELECT quantity, unit_price FROM purchases WHERE raw_material_id = ? ORDER BY purchase_date, id", (material_id,))
    purchased_qty = sum(float(row["quantity"]) for row in purchases)
    base_qty = max(0.0, stock_qty - purchased_qty)
    total_qty = base_qty
    total_value = base_qty * float(material["avg_cost"])
    for row in purchases:
        total_qty += float(row["quantity"])
        total_value += float(row["quantity"]) * float(row["unit_price"])
    execute_db("UPDATE raw_materials SET avg_cost = ? WHERE id = ?", ((total_value / total_qty) if total_qty > 0 else 0.0, material_id))


def recalc_finished_product_avg_cost(product_id: int) -> None:
    product = query_db("SELECT id, stock_qty, avg_cost FROM finished_products WHERE id = ?", (product_id,), one=True)
    if not product:
        return
    stock_qty = float(product["stock_qty"])
    productions = query_db(
        "SELECT output_quantity, production_cost FROM production_batches WHERE finished_product_id = ? ORDER BY production_date, id",
        (product_id,),
    )
    produced_qty = sum(float(row["output_quantity"]) for row in productions)
    base_qty = max(0.0, stock_qty - produced_qty)
    total_qty = base_qty
    total_value = base_qty * float(product["avg_cost"])
    for row in productions:
        total_qty += float(row["output_quantity"])
        total_value += float(row["production_cost"])
    execute_db("UPDATE finished_products SET avg_cost = ? WHERE id = ?", ((total_value / total_qty) if total_qty > 0 else 0.0, product_id))


def recalc_purchase_document_totals(document_id: int | None) -> None:
    if not document_id:
        return
    totals = query_db(
        "SELECT COUNT(*) AS line_count, COALESCE(SUM(total), 0) AS total_amount FROM purchases WHERE document_id = ?",
        (document_id,),
        one=True,
    )
    if not totals or int(totals["line_count"] or 0) <= 0:
        execute_db("DELETE FROM purchase_documents WHERE id = ?", (document_id,))
        return
    execute_db("UPDATE purchase_documents SET total = ? WHERE id = ?", (float(totals["total_amount"] or 0), document_id))


def recalc_sale_document_totals(document_id: int | None) -> None:
    if not document_id:
        return
    finished = query_db(
        "SELECT COUNT(*) AS line_count, COALESCE(SUM(total), 0) AS total_amount, COALESCE(SUM(amount_paid), 0) AS paid_amount, COALESCE(SUM(balance_due), 0) AS due_amount FROM sales WHERE document_id = ?",
        (document_id,),
        one=True,
    )
    raw = query_db(
        "SELECT COUNT(*) AS line_count, COALESCE(SUM(total), 0) AS total_amount, COALESCE(SUM(amount_paid), 0) AS paid_amount, COALESCE(SUM(balance_due), 0) AS due_amount FROM raw_sales WHERE document_id = ?",
        (document_id,),
        one=True,
    )
    line_count = int((finished["line_count"] if finished else 0) or 0) + int((raw["line_count"] if raw else 0) or 0)
    if line_count <= 0:
        execute_db("DELETE FROM sale_documents WHERE id = ?", (document_id,))
        return
    total = float((finished["total_amount"] if finished else 0) or 0) + float((raw["total_amount"] if raw else 0) or 0)
    paid = float((finished["paid_amount"] if finished else 0) or 0) + float((raw["paid_amount"] if raw else 0) or 0)
    due = float((finished["due_amount"] if finished else 0) or 0) + float((raw["due_amount"] if raw else 0) or 0)
    execute_db("UPDATE sale_documents SET total = ?, amount_paid = ?, balance_due = ? WHERE id = ?", (total, paid, due, document_id))


def refresh_sale_profits_for_item(item_kind: str, item_id: int, avg_cost: float, sale_price: float | None = None) -> None:
    if item_kind == "raw":
        rows = query_db("SELECT id, quantity, unit, unit_price FROM raw_sales WHERE raw_material_id = ?", (item_id,))
        for row in rows:
            qty_kg = qty_to_kg(float(row["quantity"]), row["unit"])
            total = float(row["quantity"]) * float(row["unit_price"])
            execute_db("UPDATE raw_sales SET cost_price_snapshot = ?, profit_amount = ? WHERE id = ?", (avg_cost, total - qty_kg * avg_cost, row["id"]))
        return
    rows = query_db("SELECT id, quantity, unit, unit_price FROM sales WHERE finished_product_id = ?", (item_id,))
    for row in rows:
        qty_kg = qty_to_kg(float(row["quantity"]), row["unit"])
        total = float(row["quantity"]) * float(row["unit_price"])
        execute_db("UPDATE sales SET cost_price_snapshot = ?, profit_amount = ? WHERE id = ?", (avg_cost, total - qty_kg * avg_cost, row["id"]))


def create_purchase_record(
    supplier_id,
    raw_id: int,
    qty: float,
    unit_price: float,
    purchase_date: str,
    notes: str,
    unit: str = "kg",
    document_id: int | None = None,
    custom_item_name: str = "",
) -> int:
    with db_transaction():
        material = query_db("SELECT * FROM raw_materials WHERE id = ?", (raw_id,), one=True)
        if not material:
            raise NotFoundError("Matière première", raw_id)
        if purchase_date and purchase_date > date.today().isoformat():
            raise ValidationError("La date d'achat ne peut pas être dans le futur.", field="purchase_date")
        custom_item_name = str(custom_item_name or "").strip()
        if is_other_operation_name(material["name"]):
            unit = OTHER_OPERATION_UNIT
            if not custom_item_name:
                raise ValidationError("Précise le nom du produit pour la ligne AUTRE.", field="custom_item_name")

        else:
            custom_item_name = ""
        total = qty * unit_price
        qty_kg = qty_to_kg(qty, unit)
        unit_price_kg = unit_price_to_kg(unit_price, unit)
        purchase_id = execute_db(
            """
            INSERT INTO purchases (supplier_id, document_id, raw_material_id, quantity, unit, unit_price, total, purchase_date, notes, custom_item_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (supplier_id, document_id, raw_id, qty_kg, unit, unit_price_kg, total, purchase_date, notes, custom_item_name),
        )
        stock_before = float(material["stock_qty"])
        stock_after = stock_before + qty_kg
        current_value = stock_before * float(material["avg_cost"])
        added_value = qty_kg * unit_price_kg
        avg_cost = (current_value + added_value) / stock_after if stock_after > 0 else 0
        sale_price = float(material["sale_price"]) or unit_price
        execute_db("UPDATE raw_materials SET stock_qty = ?, avg_cost = ?, sale_price = ? WHERE id = ?", (stock_after, avg_cost, sale_price, raw_id))
        record_stock_movement("raw", raw_id, "in", qty_kg, "kg", stock_before, stock_after, "create_purchase", "purchase", purchase_id)
        recalc_purchase_document_totals(document_id)
        return purchase_id


def create_sale_record(
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
            item = query_db("SELECT * FROM finished_products WHERE id = ?", (item_id,), one=True)
            if not item:
                raise NotFoundError("Produit fini", item_id)
            stock_before = float(item["stock_qty"])
            if qty_kg > stock_before:
                raise ValidationError(f"Stock produit insuffisant (disponible: {stock_before:.2f} kg, requis: {qty_kg:.2f} kg).", field="quantity")

            cost_snapshot = float(item["avg_cost"])
            profit_amount = total - qty_kg * cost_snapshot
            row_id = execute_db(
                """
                INSERT INTO sales (client_id, document_id, finished_product_id, quantity, unit, unit_price, total, sale_type, amount_paid, balance_due, cost_price_snapshot, profit_amount, sale_date, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (client_id, document_id, item_id, qty, unit, unit_price, total, requested_sale_type, amount_paid, balance_due, cost_snapshot, profit_amount, sale_date, notes),
            )
            stock_after = stock_before - qty_kg
            execute_db("UPDATE finished_products SET stock_qty = ? WHERE id = ?", (stock_after, item_id))
            record_stock_movement("finished", item_id, "out", qty_kg, "kg", stock_before, stock_after, "create_sale", "sale", row_id)
            if amount_paid > 0 and client_id:
                execute_db(
                    "INSERT INTO payments (client_id, sale_id, sale_kind, payment_type, amount, payment_date, notes) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (client_id, row_id, "finished", "versement", amount_paid, sale_date, "Paiement initial vente"),
                )
            recalc_sale_document_totals(document_id)
            if unit_price_kg < cost_snapshot * 0.97 and cost_snapshot > 0:
                _flash_warning(f"Vente sous cout : {unit_price_kg:.2f} DA/kg < cout de revient {cost_snapshot:.2f} DA/kg.")
            return "finished", row_id

        item = query_db("SELECT * FROM raw_materials WHERE id = ?", (item_id,), one=True)
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
        row_id = execute_db(
            """
            INSERT INTO raw_sales (client_id, document_id, raw_material_id, quantity, unit, unit_price, total, sale_type, amount_paid, balance_due, cost_price_snapshot, profit_amount, sale_date, notes, custom_item_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (client_id, document_id, item_id, qty, unit, unit_price, total, requested_sale_type, amount_paid, balance_due, cost_snapshot, profit_amount, sale_date, notes, custom_item_name),
        )
        stock_after = stock_before - qty_kg
        execute_db("UPDATE raw_materials SET stock_qty = ? WHERE id = ?", (stock_after, item_id))
        record_stock_movement("raw", item_id, "out", qty_kg, "kg", stock_before, stock_after, "create_sale", "raw_sale", row_id)
        if amount_paid > 0 and client_id:
            execute_db(
                "INSERT INTO payments (client_id, raw_sale_id, sale_kind, payment_type, amount, payment_date, notes) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (client_id, row_id, "raw", "versement", amount_paid, sale_date, "Paiement initial vente"),
            )
        recalc_sale_document_totals(document_id)
        if unit_price_kg < cost_snapshot * 0.97 and cost_snapshot > 0:
            _flash_warning(f"Vente sous cout : {unit_price_kg:.2f} DA/kg < cout de revient {cost_snapshot:.2f} DA/kg.")
        return "raw", row_id


def reverse_purchase(purchase_id: int) -> bool:
    with db_transaction():
        row = query_db("SELECT * FROM purchases WHERE id = ?", (purchase_id,), one=True)
        if not row:
            return False
        material = query_db("SELECT * FROM raw_materials WHERE id = ?", (row["raw_material_id"],), one=True)
        if not material or float(material["stock_qty"]) < float(row["quantity"]):
            return False
        stock_before = float(material["stock_qty"])
        stock_after = stock_before - float(row["quantity"])
        execute_db("UPDATE raw_materials SET stock_qty = ? WHERE id = ?", (stock_after, row["raw_material_id"]))
        execute_db("DELETE FROM purchases WHERE id = ?", (purchase_id,))
        record_stock_movement("raw", int(row["raw_material_id"]), "out", float(row["quantity"]), "kg", stock_before, stock_after, "reverse_purchase", "purchase", purchase_id)
        recalc_raw_material_avg_cost(int(row["raw_material_id"]))
        recalc_purchase_document_totals(int(row["document_id"])) if row["document_id"] else None
        return True


def reverse_sale(kind: str, row_id: int) -> bool:
    with db_transaction():
        if kind == "finished":
            row = query_db("SELECT * FROM sales WHERE id = ?", (row_id,), one=True)
            if not row:
                return False
            product = query_db("SELECT stock_qty FROM finished_products WHERE id = ?", (row["finished_product_id"],), one=True)
            stock_before = float(product["stock_qty"] if product else 0)
            restore_qty = qty_to_kg(float(row["quantity"]), row["unit"])
            stock_after = stock_before + restore_qty
            execute_db("UPDATE finished_products SET stock_qty = ? WHERE id = ?", (stock_after, row["finished_product_id"]))
            execute_db("DELETE FROM payments WHERE sale_kind = ? AND sale_id = ?", ("finished", row_id))
            execute_db("DELETE FROM sales WHERE id = ?", (row_id,))
            record_stock_movement("finished", int(row["finished_product_id"]), "in", restore_qty, "kg", stock_before, stock_after, "reverse_sale", "sale", row_id)
            recalc_sale_document_totals(int(row["document_id"])) if row["document_id"] else None
            return True
        row = query_db("SELECT * FROM raw_sales WHERE id = ?", (row_id,), one=True)
        if not row:
            return False
        material = query_db("SELECT stock_qty FROM raw_materials WHERE id = ?", (row["raw_material_id"],), one=True)
        stock_before = float(material["stock_qty"] if material else 0)
        restore_qty = qty_to_kg(float(row["quantity"]), row["unit"])
        stock_after = stock_before + restore_qty
        execute_db("UPDATE raw_materials SET stock_qty = ? WHERE id = ?", (stock_after, row["raw_material_id"]))
        execute_db("DELETE FROM payments WHERE sale_kind = ? AND raw_sale_id = ?", ("raw", row_id))
        execute_db("DELETE FROM raw_sales WHERE id = ?", (row_id,))
        record_stock_movement("raw", int(row["raw_material_id"]), "in", restore_qty, "kg", stock_before, stock_after, "reverse_sale", "raw_sale", row_id)
        recalc_sale_document_totals(int(row["document_id"])) if row["document_id"] else None
        return True


def apply_raw_material_consumption(material, qty: float, reference_type: str, reference_id: int, reason: str = "production") -> None:
    stock_before = float(material["stock_qty"])
    stock_after = stock_before - float(qty)
    if stock_after < -1e-9:
        raise ValueError(f"Stock insuffisant pour {material['name']}.")
    execute_db("UPDATE raw_materials SET stock_qty = ? WHERE id = ?", (stock_after, int(material["id"])))
    record_stock_movement("raw", int(material["id"]), "out", float(qty), "kg", stock_before, stock_after, reason, reference_type, reference_id)


def apply_finished_production(product, output_qty: float, total_cost: float, reference_id: int) -> None:
    stock_before = float(product["stock_qty"])
    current_value = stock_before * float(product["avg_cost"])
    new_value = current_value + float(total_cost)
    stock_after = stock_before + float(output_qty)
    new_avg = (new_value / stock_after) if stock_after > 0 else 0
    sale_price = float(product["sale_price"]) if float(product["sale_price"]) > 0 else new_avg * 1.15
    execute_db("UPDATE finished_products SET stock_qty = ?, avg_cost = ?, sale_price = ? WHERE id = ?", (stock_after, new_avg, sale_price, int(product["id"])))
    record_stock_movement("finished", int(product["id"]), "in", float(output_qty), "kg", stock_before, stock_after, "create_production", "production", reference_id)


def reverse_production(batch_id: int) -> bool:
    with db_transaction():
        batch = query_db("SELECT * FROM production_batches WHERE id = ?", (batch_id,), one=True)
        if not batch:
            return False
        product = query_db("SELECT * FROM finished_products WHERE id = ?", (batch["finished_product_id"],), one=True)
        if not product or float(product["stock_qty"]) < float(batch["output_quantity"]):
            return False
        items = query_db("SELECT * FROM production_batch_items WHERE batch_id = ?", (batch_id,))
        for item in items:
            material = query_db("SELECT stock_qty FROM raw_materials WHERE id = ?", (item["raw_material_id"],), one=True)
            stock_before = float(material["stock_qty"] if material else 0)
            stock_after = stock_before + float(item["quantity"])
            execute_db("UPDATE raw_materials SET stock_qty = ? WHERE id = ?", (stock_after, item["raw_material_id"]))
            record_stock_movement("raw", int(item["raw_material_id"]), "in", float(item["quantity"]), "kg", stock_before, stock_after, "reverse_production", "production", batch_id)
            recalc_raw_material_avg_cost(int(item["raw_material_id"]))
        stock_before = float(product["stock_qty"])
        stock_after = stock_before - float(batch["output_quantity"])
        execute_db("UPDATE finished_products SET stock_qty = ? WHERE id = ?", (stock_after, batch["finished_product_id"]))
        record_stock_movement("finished", int(batch["finished_product_id"]), "out", float(batch["output_quantity"]), "kg", stock_before, stock_after, "reverse_production", "production", batch_id)
        execute_db("DELETE FROM production_batches WHERE id = ?", (batch_id,))
        recalc_finished_product_avg_cost(int(batch["finished_product_id"]))
        return True


def smart_profit_for_sale(item_kind: str, item_id: int, qty_kg: float, total: float) -> tuple[float, float]:
    table = "finished_products" if item_kind == "finished" else "raw_materials"
    row = query_db(f"SELECT avg_cost FROM {table} WHERE id = ?", (item_id,), one=True)
    cost_snapshot = float(row["avg_cost"]) if row else 0.0
    return cost_snapshot, round(float(total) - float(qty_kg) * cost_snapshot, 2)
