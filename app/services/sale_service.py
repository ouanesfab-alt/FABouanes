from __future__ import annotations

import json
import asyncio
from datetime import date

from app.core.activity import log_activity
from app.core.audit import audit_event, audit_delete_event
from app.core.db_access import db_transaction, execute_db_async, query_db_async
from app.core.helpers import create_sale_record, reverse_sale, to_float, unit_choices
from app.core.storage import mark_backup_needed
from app.core.exceptions import ValidationError, ConflictError, NotFoundError
from app.repositories.sale_repository import (
    build_sellable_items,
    get_sale,
    get_sale_document,
    invalidate_sellable_items_cache,
    list_sale_document_lines,
)
from app.repositories.client_repository import async_compat


@async_compat
async def sale_form_context():
    items = await build_sellable_items.async_()
    return {"sellable_items": items, "units": unit_choices()}


def _form_list(form, key: str) -> list[str]:
    values = [str(v).strip() for v in form.getlist(key)]
    if values:
        return values
    fallback_key = key[:-2] if key.endswith("[]") else key
    value = form.get(fallback_key)
    if value is None:
        return []
    return [str(value).strip()]


async def _extract_sale_lines(form) -> list[dict[str, object]]:
    item_keys = _form_list(form, "item_key[]")
    quantities = _form_list(form, "quantity[]")
    units = _form_list(form, "unit[]")
    unit_prices = _form_list(form, "unit_price[]")
    custom_names = _form_list(form, "custom_item_name[]")
    line_count = max(len(item_keys), len(quantities), len(units), len(unit_prices), len(custom_names))
    lines: list[dict[str, object]] = []
    other_cache: dict[int, bool] = {}
    for idx in range(line_count):
        item_key = item_keys[idx] if idx < len(item_keys) else ""
        qty_raw = quantities[idx] if idx < len(quantities) else ""
        unit = units[idx] if idx < len(units) and units[idx] else "kg"
        unit_price_raw = unit_prices[idx] if idx < len(unit_prices) else ""
        custom_item_name = custom_names[idx] if idx < len(custom_names) else ""
        if not any([item_key, qty_raw, unit_price_raw]):
            continue
        if ":" not in item_key:
            raise ValidationError("Article de vente invalide.", field="item_key")
        item_kind, item_id_str = item_key.split(":", 1)
        qty = to_float(qty_raw)
        unit_price = to_float(unit_price_raw)
        if qty <= 0:
            raise ValidationError("Chaque ligne de vente doit avoir une quantité supérieure à zéro.", field="quantity")
        if unit_price <= 0:
            raise ValidationError("Chaque ligne de vente doit avoir un prix unitaire supérieur à zéro.", field="unit_price")
        item_id = int(item_id_str)
        custom_item_name = custom_item_name.strip()
        if item_kind == "raw":
            if item_id not in other_cache:
                material = await query_db_async("SELECT name FROM raw_materials WHERE id = %s", (item_id,), one=True)
                if not material:
                    raise ValidationError("Matière première introuvable.", field="item_key")
                other_cache[item_id] = str(material["name"] or "").strip().casefold() == "autre"
            if other_cache[item_id] and not custom_item_name:
                raise ValidationError("Précisez le nom du produit pour la ligne AUTRE.", field="custom_item_name")
        lines.append(
            {
                "item_key": item_key,
                "item_kind": item_kind,
                "item_id": item_id,
                "quantity": qty,
                "unit": unit,
                "unit_price": unit_price,
                "custom_item_name": custom_item_name,
            }
        )
    if not lines:
        raise ValidationError("Ajoutez au moins une ligne à la facture.")

    return lines


async def _insert_sale_document(document_id, client_id, sale_type: str, sale_date: str, notes: str) -> int:
    from app.core.document_numbering import next_doc_number
    try:
        year = int(sale_date.split("-")[0])
    except Exception:
        year = date.today().year
    doc_number = await next_doc_number.async_("BV", year)

    if document_id:
        await execute_db_async(
            """
            INSERT INTO sale_documents (id, doc_number, client_id, sale_type, total, amount_paid, balance_due, sale_date, notes)
            VALUES (%s, %s, %s, %s, 0, 0, 0, %s, %s)
            """,
            (int(document_id), doc_number, client_id, sale_type, sale_date, notes),
        )
        return int(document_id)
    return await execute_db_async(
        """
        INSERT INTO sale_documents (doc_number, client_id, sale_type, total, amount_paid, balance_due, sale_date, notes)
        VALUES (%s, %s, %s, 0, 0, 0, %s, %s)
        """,
        (doc_number, client_id, sale_type, sale_date, notes),
    )


async def _save_sale_document_header(document_id: int, client_id, sale_type: str, sale_date: str, notes: str) -> None:
    existing = await query_db_async("SELECT id FROM sale_documents WHERE id = %s", (document_id,), one=True)
    if not existing:
        await _insert_sale_document(document_id, client_id, sale_type, sale_date, notes)
        return
    await execute_db_async(
        "UPDATE sale_documents SET client_id = %s, sale_type = %s, sale_date = %s, notes = %s WHERE id = %s",
        (client_id, sale_type, sale_date, notes, document_id),
    )


def _serialize_sale_lines(lines) -> list[dict[str, object]]:
    payload = []
    for line in lines:
        payload.append(
            {
                "row_id": int(line["row_id"]),
                "document_id": int(line["document_id"]) if line["document_id"] else None,
                "row_kind": str(line["row_kind"]),
                "item_key": str(line["item_key"]),
                "item_name": str(line["item_name"]),
                "item_kind": str(line["item_kind"]),
                "quantity": float(line["quantity"]),
                "unit": str(line["unit"]),
                "unit_price": float(line["unit_price"]),
                "total": float(line["total"]),
                "amount_paid": float(line["amount_paid"]),
                "balance_due": float(line["balance_due"]),
                "custom_item_name": str(line["custom_item_name"] or ""),
            }
        )
    return payload


def _sale_refs(lines) -> set[tuple[str, int]]:
    return {(str(line["row_kind"]), int(line["row_id"])) for line in lines}


def _payment_references_sale(payment_row, sale_refs: set[tuple[str, int]]) -> bool:
    if payment_row["sale_id"] and ("finished", int(payment_row["sale_id"])) in sale_refs:
        return True
    if payment_row["raw_sale_id"] and ("raw", int(payment_row["raw_sale_id"])) in sale_refs:
        return True
    meta_raw = payment_row["allocation_meta"] if "allocation_meta" in payment_row.keys() else None
    if not meta_raw:
        return False
    try:
        allocations = json.loads(meta_raw)
    except Exception:
        return False
    for allocation in allocations or []:
        try:
            ref = (str(allocation.get("kind") or ""), int(allocation.get("id") or 0))
        except Exception:
            continue
        if ref in sale_refs:
            return True
    return False


async def _client_payment_rows(client_id: int | None):
    if not client_id:
        return []
    return await query_db_async(
        """
        SELECT id, sale_id, raw_sale_id, allocation_meta
        FROM payments
        WHERE client_id = %s AND payment_type = 'versement'
        """,
        (int(client_id),),
    )


async def sale_document_has_linked_payments(document_id: int) -> bool:
    document = await get_sale_document.async_(document_id)
    if not document or not document["client_id"]:
        return False
    lines = await list_sale_document_lines.async_(document_id)
    refs = _sale_refs(lines)
    if not refs:
        return False
    for payment in await _client_payment_rows(int(document["client_id"])):
        if _payment_references_sale(payment, refs):
            return True
    return False


async def sale_line_has_linked_payments(kind: str, row_id: int, client_id) -> bool:
    if not client_id:
        return False
    refs = {(str(kind), int(row_id))}
    for payment in await _client_payment_rows(int(client_id)):
        if _payment_references_sale(payment, refs):
            return True
    return False


@async_compat
async def get_sale_document_context(document_id: int):
    document = await get_sale_document.async_(document_id)
    if not document:
        return None
    lines = await list_sale_document_lines.async_(document_id)
    has_linked = await sale_document_has_linked_payments(document_id)
    return {
        "sale_document": dict(document),
        "sale_lines": _serialize_sale_lines(lines),
        "has_linked_payments": has_linked,
    }


@async_compat
async def get_sale_edit_context(kind: str, row_id: int):
    sale = await get_sale.async_(kind, row_id)
    if not sale:
        return None
    if sale["document_id"]:
        context = await get_sale_document_context(int(sale["document_id"]))
        if context:
            context["redirect_document_id"] = int(sale["document_id"])
        return context
    return {
        "sale_document": {
            "id": None,
            "client_id": sale["client_id"],
            "sale_type": sale["sale_type"],
            "sale_date": sale["sale_date"],
            "notes": sale["notes"] or "",
        },
        "sale_lines": [
            {
                "row_id": int(sale["id"]),
                "document_id": None,
                "row_kind": str(sale["row_kind"]),
                "item_key": str(sale["item_key"]),
                "item_name": str(sale["item_name"]),
                "item_kind": "Produit final" if sale["row_kind"] == "finished" else "Matière première",
                "quantity": float(sale["quantity"]),
                "unit": str(sale["unit"]),
                "unit_price": float(sale["unit_price"]),
                "total": float(sale["total"]),
                "amount_paid": float(sale["amount_paid"]),
                "balance_due": float(sale["balance_due"]),
                "custom_item_name": str(sale["custom_item_name"] or ""),
            }
        ],
        "has_linked_payments": False,
    }


@async_compat
async def create_sale_from_form(form):
    client_id = form.get("client_id") or None
    sale_date = form.get("sale_date") or date.today().isoformat()
    notes = form.get("notes", "").strip()
    sale_type = "credit" if client_id else "cash"
    lines = await _extract_sale_lines(form)
    use_document = len(lines) > 1 or bool(form.getlist("item_key[]"))

    if not use_document:
        line = lines[0]
        created_kind, created_sale_id = await create_sale_record(
            client_id,
            str(line["item_kind"]),
            int(line["item_id"]),
            float(line["quantity"]),
            str(line["unit"]),
            float(line["unit_price"]),
            sale_type,
            sale_date,
            notes,
            0 if client_id else float(line["quantity"]) * float(line["unit_price"]),
            custom_item_name=str(line["custom_item_name"]),
        )
        created = await get_sale.async_(created_kind, created_sale_id)
        log_activity("create_sale", "sale", created_sale_id, f"{line['item_kind']} #{line['item_id']} qty={line['quantity']} {line['unit']}")
        audit_event("create_sale", "sale", created_sale_id, after=created, meta={"kind": created_kind})
        invalidate_sellable_items_cache()
        mark_backup_needed("create_sale")
        return {
            "mode": "line",
            "document_id": None,
            "print_doc_type": "sale_finished" if created_kind == "finished" else "sale_raw",
            "print_item_id": created_sale_id,
            "line_count": 1,
            "first_line_kind": created_kind,
            "first_line_id": created_sale_id,
        }

    with db_transaction():
        document_id = await _insert_sale_document(None, client_id, sale_type, sale_date, notes)
        created_lines: list[tuple[str, int]] = []
        for line in lines:
            created_lines.append(
                await create_sale_record(
                    client_id,
                    str(line["item_kind"]),
                    int(line["item_id"]),
                    float(line["quantity"]),
                    str(line["unit"]),
                    float(line["unit_price"]),
                    sale_type,
                    sale_date,
                    notes,
                    0 if client_id else float(line["quantity"]) * float(line["unit_price"]),
                    document_id=document_id,
                    custom_item_name=str(line["custom_item_name"]),
                )
            )

    created = await query_db_async("SELECT * FROM sale_documents WHERE id = %s", (document_id,), one=True)
    log_activity("create_sale_document", "sale_document", document_id, f"{len(lines)} ligne(s)")
    audit_event("create_sale_document", "sale_document", document_id, after=created, meta={"line_count": len(lines)})
    invalidate_sellable_items_cache()
    mark_backup_needed("create_sale_document")
    return {
        "mode": "document",
        "document_id": document_id,
        "print_doc_type": "sale_document",
        "print_item_id": document_id,
        "line_count": len(lines),
        "first_line_kind": created_lines[0][0],
        "first_line_id": created_lines[0][1],
    }


@async_compat
async def edit_sale_document_from_form(document_id: int, form):
    context = await get_sale_document_context(document_id)
    if not context:
        raise NotFoundError("Facture", document_id)
    if context["has_linked_payments"]:
        raise ConflictError("Cette facture est deja liee a des versements.")

    client_id = form.get("client_id") or None
    sale_date = form.get("sale_date") or date.today().isoformat()
    notes = form.get("notes", "").strip()
    sale_type = "credit" if client_id else "cash"
    lines = await _extract_sale_lines(form)
    before = {
        "document": dict(context["sale_document"]),
        "lines": [dict(line) for line in context["sale_lines"]],
    }

    with db_transaction():
        for line in context["sale_lines"]:
            if not await reverse_sale(str(line["row_kind"]), int(line["row_id"])):
                raise ValueError("Impossible de modifier cette facture.")

        existing = await query_db_async("SELECT id FROM sale_documents WHERE id = %s", (document_id,), one=True)
        if not existing:
            doc_number = before["document"]["doc_number"]
            await execute_db_async(
                """
                INSERT INTO sale_documents (id, doc_number, client_id, sale_type, total, amount_paid, balance_due, sale_date, notes)
                VALUES (%s, %s, %s, %s, 0, 0, 0, %s, %s)
                """,
                (int(document_id), doc_number, client_id, sale_type, sale_date, notes),
            )

        created_lines: list[tuple[str, int]] = []
        for line in lines:
            created_lines.append(
                await create_sale_record(
                    client_id,
                    str(line["item_kind"]),
                    int(line["item_id"]),
                    float(line["quantity"]),
                    str(line["unit"]),
                    float(line["unit_price"]),
                    sale_type,
                    sale_date,
                    notes,
                    0 if client_id else float(line["quantity"]) * float(line["unit_price"]),
                    document_id=document_id,
                    custom_item_name=str(line["custom_item_name"]),
                )
            )
        await _save_sale_document_header(document_id, client_id, sale_type, sale_date, notes)

    after_context = await get_sale_document_context(document_id)
    log_activity("update_sale_document", "sale_document", document_id, f"{len(lines)} ligne(s)")
    audit_event(
        "update_sale_document",
        "sale_document",
        document_id,
        before=before,
        after={"document": after_context["sale_document"], "lines": after_context["sale_lines"]} if after_context else None,
        meta={"line_count": len(lines)},
    )
    invalidate_sellable_items_cache()
    mark_backup_needed("update_sale_document")
    return {
        "mode": "document",
        "document_id": document_id,
        "print_doc_type": "sale_document",
        "print_item_id": document_id,
        "line_count": len(lines),
        "first_line_kind": created_lines[0][0],
        "first_line_id": created_lines[0][1],
    }


@async_compat
async def edit_sale_from_form(kind: str, row_id: int, form):
    before = await get_sale.async_(kind, row_id)
    if not before:
        raise NotFoundError("Vente", f"{kind}:{row_id}")
    if before["document_id"]:
        raise ConflictError("Cette ligne appartient deja a une facture multi-lignes.")

    client_id = form.get("client_id") or None
    sale_date = form.get("sale_date") or date.today().isoformat()
    notes = form.get("notes", "").strip()
    sale_type = "credit" if client_id else "cash"
    lines = await _extract_sale_lines(form)

    if len(lines) > 1:
        if await sale_line_has_linked_payments(kind, row_id, before["client_id"]):
            raise ConflictError("Cette facture est deja liee a des versements.")

        with db_transaction():
            if not await reverse_sale(kind, row_id):
                raise ValueError("Impossible de modifier cette vente.")
            document_id = await _insert_sale_document(None, client_id, sale_type, sale_date, notes)
            created_lines: list[tuple[str, int]] = []
            for line in lines:
                created_lines.append(
                    await create_sale_record(
                        client_id,
                        str(line["item_kind"]),
                        int(line["item_id"]),
                        float(line["quantity"]),
                        str(line["unit"]),
                        float(line["unit_price"]),
                        sale_type,
                        sale_date,
                        notes,
                        0 if client_id else float(line["quantity"]) * float(line["unit_price"]),
                        document_id=document_id,
                        custom_item_name=str(line["custom_item_name"]),
                    )
                )

        created = await query_db_async("SELECT * FROM sale_documents WHERE id = %s", (document_id,), one=True)
        log_activity("update_sale_document", "sale_document", document_id, f"{len(lines)} ligne(s)")
        audit_event(
            "update_sale_document",
            "sale_document",
            document_id,
            before=dict(before),
            after=created,
            meta={"line_count": len(lines), "promoted_from_row_id": row_id},
        )
        invalidate_sellable_items_cache()
        mark_backup_needed("update_sale_document")
        return {
            "mode": "document",
            "document_id": document_id,
            "print_doc_type": "sale_document",
            "print_item_id": document_id,
            "line_count": len(lines),
            "first_line_kind": created_lines[0][0],
            "first_line_id": created_lines[0][1],
        }

    line = lines[0]
    with db_transaction():
        if not await reverse_sale(kind, row_id):
            raise ValueError("Impossible de modifier cette vente.")
        new_kind, new_sale_id = await create_sale_record(
            client_id,
            str(line["item_kind"]),
            int(line["item_id"]),
            float(line["quantity"]),
            str(line["unit"]),
            float(line["unit_price"]),
            sale_type,
            sale_date,
            notes,
            0 if client_id else float(line["quantity"]) * float(line["unit_price"]),
            custom_item_name=str(line["custom_item_name"]),
        )

    after = await get_sale.async_(new_kind, new_sale_id)
    log_activity("update_sale", "sale", row_id, f"{line['item_kind']} #{line['item_id']} qty={line['quantity']} {line['unit']}")
    audit_event("update_sale", "sale", row_id, before=before, after=after, meta={"kind": new_kind, "document_id": None})
    invalidate_sellable_items_cache()
    mark_backup_needed("update_sale")
    return {
        "mode": "line",
        "document_id": None,
        "print_doc_type": "sale_finished" if new_kind == "finished" else "sale_raw",
        "print_item_id": new_sale_id,
        "line_count": 1,
        "first_line_kind": new_kind,
        "first_line_id": new_sale_id,
    }


@async_compat
async def delete_sale_by_id(kind: str, row_id: int) -> bool:
    before = await get_sale.async_(kind, row_id)
    if before:
        audit_delete_event("sale", row_id, dict(before))
    ok = await reverse_sale(kind, row_id)
    if ok:
        log_activity("delete_sale", "sale", row_id, f"Suppression vente {kind}")
        audit_event("delete_sale", "sale", row_id, before=before, after=None, meta={"kind": kind})
        invalidate_sellable_items_cache()
        mark_backup_needed("delete_sale")
    return ok
