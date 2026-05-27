from __future__ import annotations

import asyncio
from datetime import date

from app.core.activity import log_activity
from app.core.audit import audit_event
from app.core.db_access import db_transaction, execute_db_async, query_db_async
from app.core.helpers import create_purchase_record, reverse_purchase, to_float, unit_choices
from app.core.storage import mark_backup_needed
from app.repositories.purchase_repository import (
    get_purchase,
    get_purchase_document,
    list_purchase_document_lines,
    list_purchase_form_context,
)
from app.repositories.sale_repository import invalidate_sellable_items_cache
from app.repositories.client_repository import async_compat
from app.core.exceptions import ValidationError


@async_compat
async def purchase_form_context():
    context = await asyncio.to_thread(list_purchase_form_context)
    context["units"] = unit_choices()
    return context


def _form_list(form, key: str) -> list[str]:
    values = [str(v).strip() for v in form.getlist(key)]
    if values:
        return values
    fallback_key = key[:-2] if key.endswith("[]") else key
    value = form.get(fallback_key)
    if value is None:
        return []
    return [str(value).strip()]


async def _extract_purchase_lines(form) -> list[dict[str, object]]:
    raw_ids = _form_list(form, "raw_material_id[]")
    quantities = _form_list(form, "quantity[]")
    units = _form_list(form, "unit[]")
    unit_prices = _form_list(form, "unit_price[]")
    custom_names = _form_list(form, "custom_item_name[]")
    line_count = max(len(raw_ids), len(quantities), len(units), len(unit_prices), len(custom_names))
    lines: list[dict[str, object]] = []
    
    for idx in range(line_count):
        raw_val = raw_ids[idx] if idx < len(raw_ids) else ""
        qty_raw = quantities[idx] if idx < len(quantities) else ""
        unit = units[idx] if idx < len(units) and units[idx] else "kg"
        unit_price_raw = unit_prices[idx] if idx < len(unit_prices) else ""
        custom_item_name = custom_names[idx] if idx < len(custom_names) else ""
        if not any([raw_val, qty_raw, unit_price_raw]):
            continue
        qty = to_float(qty_raw)
        unit_price = to_float(unit_price_raw)
        if qty <= 0:
            raise ValidationError("Chaque ligne d'achat doit avoir une quantité supérieure à zéro.", field="quantity")
        if unit_price <= 0:
            raise ValidationError("Chaque ligne d'achat doit avoir un prix unitaire supérieur à zéro.", field="unit_price")
        
        if ":" in raw_val:
            kind, real_id_str = raw_val.split(":", 1)
            real_id = int(real_id_str)
        else:
            kind = "raw"
            real_id = int(raw_val) if raw_val.isdigit() else 0
            
        if kind == "raw":
            material = await query_db_async("SELECT name FROM raw_materials WHERE id = %s", (real_id,), one=True)
            if not material:
                raise ValidationError("Matière première introuvable.", field="raw_material_id")
            is_autre = str(material["name"] or "").strip().casefold() == "autre"
        else:
            product = await query_db_async("SELECT name FROM finished_products WHERE id = %s", (real_id,), one=True)
            if not product:
                raise ValidationError("Produit fini introuvable.", field="raw_material_id")
            is_autre = False
            
        custom_item_name = custom_item_name.strip()
        if is_autre and not custom_item_name:
            raise ValidationError("Précisez le nom du produit pour la ligne AUTRE.", field="custom_item_name")
            
        lines.append(
            {
                "kind": kind,
                "real_id": real_id,
                "quantity": qty,
                "unit": unit,
                "unit_price": unit_price,
                "custom_item_name": custom_item_name,
            }
        )
    if not lines:
        raise ValidationError("Ajoutez au moins une ligne à ce bon d'achat.")
    return lines


async def _insert_purchase_document(document_id, supplier_id, purchase_date: str, notes: str) -> int:
    from app.core.document_numbering import next_doc_number
    try:
        year = int(purchase_date.split("-")[0])
    except Exception:
        year = date.today().year
    doc_number = await asyncio.to_thread(next_doc_number, "BA", year)

    if document_id:
        await execute_db_async(
            "INSERT INTO purchase_documents (id, doc_number, supplier_id, total, purchase_date, notes) VALUES (%s, %s, %s, 0, %s, %s)",
            (int(document_id), doc_number, supplier_id, purchase_date, notes),
        )
        return int(document_id)
    return await execute_db_async(
        "INSERT INTO purchase_documents (doc_number, supplier_id, total, purchase_date, notes) VALUES (%s, %s, 0, %s, %s)",
        (doc_number, supplier_id, purchase_date, notes),
    )


async def _save_purchase_document_header(document_id: int, supplier_id, purchase_date: str, notes: str) -> None:
    existing = await query_db_async("SELECT id FROM purchase_documents WHERE id = %s", (document_id,), one=True)
    if not existing:
        await _insert_purchase_document(document_id, supplier_id, purchase_date, notes)
        return
    await execute_db_async(
        "UPDATE purchase_documents SET supplier_id = %s, purchase_date = %s, notes = %s WHERE id = %s",
        (supplier_id, purchase_date, notes, document_id),
    )


def _serialize_purchase_lines(lines) -> list[dict[str, object]]:
    payload = []
    for line in lines:
        item_id = f"finished:{line['finished_product_id']}" if line.get("finished_product_id") else f"raw:{line['raw_material_id']}"
        payload.append(
            {
                "row_id": int(line["row_id"]),
                "document_id": int(line["document_id"]) if line["document_id"] else None,
                "raw_material_id": item_id,
                "material_name": str(line["material_name"]),
                "quantity": float(line["display_quantity"]),
                "unit": str(line["display_unit"]),
                "unit_price": float(line["display_unit_price"]),
                "total": float(line["total"]),
                "custom_item_name": str(line["custom_item_name"] or ""),
            }
        )
    return payload


@async_compat
async def get_purchase_document_context(document_id: int):
    document = await asyncio.to_thread(get_purchase_document, document_id)
    if not document:
        return None
    lines = await asyncio.to_thread(list_purchase_document_lines, document_id)
    return {
        "purchase_document": dict(document),
        "purchase_lines": _serialize_purchase_lines(lines),
    }


@async_compat
async def get_purchase_edit_context(purchase_id: int):
    purchase = await asyncio.to_thread(get_purchase, purchase_id)
    if not purchase:
        return None
    if purchase["document_id"]:
        context = await get_purchase_document_context(int(purchase["document_id"]))
        if context:
            context["redirect_document_id"] = int(purchase["document_id"])
        return context
    item_id = f"finished:{purchase['finished_product_id']}" if purchase["finished_product_id"] else f"raw:{purchase['raw_material_id']}"
    return {
        "purchase_document": {
            "id": None,
            "supplier_id": purchase["supplier_id"],
            "purchase_date": purchase["purchase_date"],
            "notes": purchase["notes"] or "",
        },
        "purchase_lines": [
            {
                "row_id": int(purchase["id"]),
                "document_id": None,
                "raw_material_id": item_id,
                "material_name": str(purchase["material_name"]),
                "quantity": float(purchase["display_quantity"]),
                "unit": str(purchase["display_unit"]),
                "unit_price": float(purchase["display_unit_price"]),
                "total": float(purchase["total"]),
                "custom_item_name": str(purchase["custom_item_name"] or ""),
            }
        ],
    }


@async_compat
async def create_purchase_from_form(form):
    supplier_id = form.get("supplier_id") or None
    purchase_date = form.get("purchase_date") or date.today().isoformat()
    notes = form.get("notes", "").strip()
    lines = await _extract_purchase_lines(form)
    use_document = len(lines) > 1 or bool(form.getlist("raw_material_id[]"))

    if not use_document:
        line = lines[0]
        purchase_id = await create_purchase_record(
            supplier_id,
            line["kind"],
            float(line["quantity"]),
            float(line["unit_price"]),
            purchase_date,
            notes,
            str(line["unit"]),
            custom_item_name=str(line["custom_item_name"]),
            item_id=line["real_id"],
        )
        created = await asyncio.to_thread(get_purchase, purchase_id)
        log_activity("create_purchase", "purchase", purchase_id, f"{line['kind']} #{line['real_id']} qty={line['quantity']}")
        audit_event("create_purchase", "purchase", purchase_id, after=created)
        await asyncio.to_thread(invalidate_sellable_items_cache)
        mark_backup_needed("create_purchase")
        return {
            "mode": "line",
            "document_id": None,
            "print_doc_type": "purchase",
            "print_item_id": purchase_id,
            "line_count": 1,
            "first_purchase_id": purchase_id,
        }

    with db_transaction():
        document_id = await _insert_purchase_document(None, supplier_id, purchase_date, notes)
        created_ids: list[int] = []
        for line in lines:
            created_ids.append(
                await create_purchase_record(
                    supplier_id,
                    line["kind"],
                    float(line["quantity"]),
                    float(line["unit_price"]),
                    purchase_date,
                    notes,
                    str(line["unit"]),
                    document_id=document_id,
                    custom_item_name=str(line["custom_item_name"]),
                    item_id=line["real_id"],
                )
            )

    created = await query_db_async("SELECT * FROM purchase_documents WHERE id = %s", (document_id,), one=True)
    log_activity("create_purchase_document", "purchase_document", document_id, f"{len(lines)} ligne(s)")
    audit_event("create_purchase_document", "purchase_document", document_id, after=created, meta={"line_count": len(lines)})
    await asyncio.to_thread(invalidate_sellable_items_cache)
    mark_backup_needed("create_purchase_document")
    return {
        "mode": "document",
        "document_id": document_id,
        "print_doc_type": "purchase_document",
        "print_item_id": document_id,
        "line_count": len(lines),
        "first_purchase_id": created_ids[0],
    }


@async_compat
async def edit_purchase_document_from_form(document_id: int, form):
    context = await get_purchase_document_context(document_id)
    if not context:
        raise ValueError("Bon d'achat introuvable.")

    supplier_id = form.get("supplier_id") or None
    purchase_date = form.get("purchase_date") or date.today().isoformat()
    notes = form.get("notes", "").strip()
    lines = await _extract_purchase_lines(form)
    before = {
        "document": dict(context["purchase_document"]),
        "lines": [dict(line) for line in context["purchase_lines"]],
    }

    with db_transaction():
        for line in context["purchase_lines"]:
            if not await reverse_purchase(int(line["row_id"])):
                raise ValueError("Impossible de modifier cet achat car le stock ne permet pas de l'annuler.")
        await _insert_purchase_document(document_id, supplier_id, purchase_date, notes)
        created_ids: list[int] = []
        for line in lines:
            created_ids.append(
                await create_purchase_record(
                    supplier_id,
                    line["kind"],
                    float(line["quantity"]),
                    float(line["unit_price"]),
                    purchase_date,
                    notes,
                    str(line["unit"]),
                    document_id=document_id,
                    custom_item_name=str(line["custom_item_name"]),
                    item_id=line["real_id"],
                )
            )
        await _save_purchase_document_header(document_id, supplier_id, purchase_date, notes)

    after_context = await get_purchase_document_context(document_id)
    log_activity("update_purchase_document", "purchase_document", document_id, f"{len(lines)} ligne(s)")
    audit_event(
        "update_purchase_document",
        "purchase_document",
        document_id,
        before=before,
        after={"document": after_context["purchase_document"], "lines": after_context["purchase_lines"]} if after_context else None,
        meta={"line_count": len(lines)},
    )
    await asyncio.to_thread(invalidate_sellable_items_cache)
    mark_backup_needed("update_purchase_document")
    return {
        "mode": "document",
        "document_id": document_id,
        "print_doc_type": "purchase_document",
        "print_item_id": document_id,
        "line_count": len(lines),
        "first_purchase_id": created_ids[0],
    }


@async_compat
async def edit_purchase_from_form(purchase_id: int, form):
    before = await asyncio.to_thread(get_purchase, purchase_id)
    if not before:
        raise ValueError("Achat introuvable.")
    if before["document_id"]:
        raise ValueError("Cette ligne appartient deja a un bon multi-lignes.")

    supplier_id = form.get("supplier_id") or None
    purchase_date = form.get("purchase_date") or date.today().isoformat()
    notes = form.get("notes", "").strip()
    lines = await _extract_purchase_lines(form)

    if len(lines) > 1:
        with db_transaction():
            if not await reverse_purchase(purchase_id):
                raise ValueError("Impossible de modifier cet achat car le stock ne permet pas de l'annuler.")
            document_id = await _insert_purchase_document(None, supplier_id, purchase_date, notes)
            created_ids: list[int] = []
            for line in lines:
                created_ids.append(
                    await create_purchase_record(
                        supplier_id,
                        line["kind"],
                        float(line["quantity"]),
                        float(line["unit_price"]),
                        purchase_date,
                        notes,
                        str(line["unit"]),
                        document_id=document_id,
                        custom_item_name=str(line["custom_item_name"]),
                        item_id=line["real_id"],
                    )
                )

        created = await query_db_async("SELECT * FROM purchase_documents WHERE id = %s", (document_id,), one=True)
        log_activity("update_purchase_document", "purchase_document", document_id, f"{len(lines)} ligne(s)")
        audit_event(
            "update_purchase_document",
            "purchase_document",
            document_id,
            before=dict(before),
            after=created,
            meta={"line_count": len(lines), "promoted_from_purchase_id": purchase_id},
        )
        await asyncio.to_thread(invalidate_sellable_items_cache)
        mark_backup_needed("update_purchase_document")
        return {
            "mode": "document",
            "document_id": document_id,
            "print_doc_type": "purchase_document",
            "print_item_id": document_id,
            "line_count": len(lines),
            "first_purchase_id": created_ids[0],
        }

    line = lines[0]
    with db_transaction():
        if not await reverse_purchase(purchase_id):
            raise ValueError("Impossible de modifier cet achat car le stock ne permet pas de l'annuler.")
        new_purchase_id = await create_purchase_record(
            supplier_id,
            line["kind"],
            float(line["quantity"]),
            float(line["unit_price"]),
            purchase_date,
            notes,
            str(line["unit"]),
            custom_item_name=str(line["custom_item_name"]),
            item_id=line["real_id"],
        )

    latest = await asyncio.to_thread(get_purchase, new_purchase_id)
    log_activity("update_purchase", "purchase", purchase_id, f"{line['kind']} #{line['real_id']} qty={line['quantity']}")
    audit_event("update_purchase", "purchase", purchase_id, before=before, after=latest, meta={"document_id": None})
    await asyncio.to_thread(invalidate_sellable_items_cache)
    mark_backup_needed("update_purchase")
    return {
        "mode": "line",
        "document_id": None,
        "print_doc_type": "purchase",
        "print_item_id": new_purchase_id,
        "line_count": 1,
        "first_purchase_id": new_purchase_id,
    }


@async_compat
async def delete_purchase_by_id(purchase_id: int) -> bool:
    before = await asyncio.to_thread(get_purchase, purchase_id)
    ok = await reverse_purchase(purchase_id)
    if ok:
        log_activity("delete_purchase", "purchase", purchase_id, "Suppression achat")
        audit_event("delete_purchase", "purchase", purchase_id, before=before, after=None)
        await asyncio.to_thread(invalidate_sellable_items_cache)
        mark_backup_needed("delete_purchase")
    return ok
