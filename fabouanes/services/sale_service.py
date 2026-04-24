from __future__ import annotations

import json
from datetime import date

from fabouanes.core.activity import log_activity
from fabouanes.core.audit import audit_event
from fabouanes.core.db_access import db_transaction, execute_db, query_db
from fabouanes.core.helpers import create_sale_record, reverse_sale, to_float, unit_choices
from fabouanes.core.storage import backup_database
from fabouanes.repositories.sale_repository import (
    build_sellable_items,
    get_sale,
    get_sale_document,
    list_sale_document_lines,
    list_sales_page_context,
)


def sales_context():
    return _build_sales_context()


def sale_form_context():
    return {"sellable_items": build_sellable_items(), "units": unit_choices()}


def _build_sales_context():
    context = list_sales_page_context()
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


def _extract_sale_lines(form) -> list[dict[str, object]]:
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
            raise ValueError("Article de vente invalide.")
        item_kind, item_id_str = item_key.split(":", 1)
        qty = to_float(qty_raw)
        unit_price = to_float(unit_price_raw)
        if qty <= 0:
            raise ValueError("Chaque ligne de vente doit avoir une quantite superieure a zero.")
        if unit_price <= 0:
            raise ValueError("Chaque ligne de vente doit avoir un prix unitaire superieur a zero.")
        item_id = int(item_id_str)
        custom_item_name = custom_item_name.strip()
        if item_kind == "raw":
            if item_id not in other_cache:
                material = query_db("SELECT name FROM raw_materials WHERE id = ?", (item_id,), one=True)
                if not material:
                    raise ValueError("Matiere premiere introuvable.")
                other_cache[item_id] = str(material["name"] or "").strip().casefold() == "autre"
            if other_cache[item_id] and not custom_item_name:
                raise ValueError("Precise le nom du produit pour la ligne AUTRE.")
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
        raise ValueError("Ajoute au moins une ligne a la facture.")
    return lines


def _insert_sale_document(document_id, client_id, sale_type: str, sale_date: str, notes: str) -> int:
    if document_id:
        execute_db(
            """
            INSERT INTO sale_documents (id, client_id, sale_type, total, amount_paid, balance_due, sale_date, notes)
            VALUES (?, ?, ?, 0, 0, 0, ?, ?)
            """,
            (int(document_id), client_id, sale_type, sale_date, notes),
        )
        return int(document_id)
    return execute_db(
        """
        INSERT INTO sale_documents (client_id, sale_type, total, amount_paid, balance_due, sale_date, notes)
        VALUES (?, ?, 0, 0, 0, ?, ?)
        """,
        (client_id, sale_type, sale_date, notes),
    )


def _save_sale_document_header(document_id: int, client_id, sale_type: str, sale_date: str, notes: str) -> None:
    existing = query_db("SELECT id FROM sale_documents WHERE id = ?", (document_id,), one=True)
    if not existing:
        _insert_sale_document(document_id, client_id, sale_type, sale_date, notes)
        return
    execute_db(
        "UPDATE sale_documents SET client_id = ?, sale_type = ?, sale_date = ?, notes = ? WHERE id = ?",
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


def _client_payment_rows(client_id: int | None):
    if not client_id:
        return []
    return query_db(
        """
        SELECT id, sale_id, raw_sale_id, allocation_meta
        FROM payments
        WHERE client_id = ? AND payment_type = 'versement'
        """,
        (int(client_id),),
    )


def sale_document_has_linked_payments(document_id: int) -> bool:
    document = get_sale_document(document_id)
    if not document or not document["client_id"]:
        return False
    lines = list_sale_document_lines(document_id)
    refs = _sale_refs(lines)
    if not refs:
        return False
    for payment in _client_payment_rows(int(document["client_id"])):
        if _payment_references_sale(payment, refs):
            return True
    return False


def sale_line_has_linked_payments(kind: str, row_id: int, client_id) -> bool:
    if not client_id:
        return False
    refs = {(str(kind), int(row_id))}
    for payment in _client_payment_rows(int(client_id)):
        if _payment_references_sale(payment, refs):
            return True
    return False


def get_sale_document_context(document_id: int):
    document = get_sale_document(document_id)
    if not document:
        return None
    lines = list_sale_document_lines(document_id)
    return {
        "sale_document": dict(document),
        "sale_lines": _serialize_sale_lines(lines),
        "has_linked_payments": sale_document_has_linked_payments(document_id),
    }


def get_sale_edit_context(kind: str, row_id: int):
    sale = get_sale(kind, row_id)
    if not sale:
        return None
    if sale["document_id"]:
        context = get_sale_document_context(int(sale["document_id"]))
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
                "item_kind": "Produit fini" if sale["row_kind"] == "finished" else "Matiere premiere",
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


def create_sale_from_form(form):
    client_id = form.get("client_id") or None
    sale_date = form.get("sale_date") or date.today().isoformat()
    notes = form.get("notes", "").strip()
    sale_type = "credit" if client_id else "cash"
    lines = _extract_sale_lines(form)
    use_document = len(lines) > 1 or bool(form.getlist("item_key[]"))

    if not use_document:
        line = lines[0]
        created_kind, created_sale_id = create_sale_record(
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
        created = get_sale(created_kind, created_sale_id)
        log_activity("create_sale", "sale", created_sale_id, f"{line['item_kind']} #{line['item_id']} qty={line['quantity']} {line['unit']}")
        audit_event("create_sale", "sale", created_sale_id, after=created, meta={"kind": created_kind})
        backup_database("create_sale")
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
        document_id = _insert_sale_document(None, client_id, sale_type, sale_date, notes)
        created_lines: list[tuple[str, int]] = []
        for line in lines:
            created_lines.append(
                create_sale_record(
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

    created = query_db("SELECT * FROM sale_documents WHERE id = ?", (document_id,), one=True)
    log_activity("create_sale_document", "sale_document", document_id, f"{len(lines)} ligne(s)")
    audit_event("create_sale_document", "sale_document", document_id, after=created, meta={"line_count": len(lines)})
    backup_database("create_sale_document")
    return {
        "mode": "document",
        "document_id": document_id,
        "print_doc_type": "sale_document",
        "print_item_id": document_id,
        "line_count": len(lines),
        "first_line_kind": created_lines[0][0],
        "first_line_id": created_lines[0][1],
    }


def edit_sale_document_from_form(document_id: int, form):
    context = get_sale_document_context(document_id)
    if not context:
        raise ValueError("Facture introuvable.")
    if context["has_linked_payments"]:
        raise ValueError("Cette facture est deja liee a des versements.")

    client_id = form.get("client_id") or None
    sale_date = form.get("sale_date") or date.today().isoformat()
    notes = form.get("notes", "").strip()
    sale_type = "credit" if client_id else "cash"
    lines = _extract_sale_lines(form)
    before = {
        "document": dict(context["sale_document"]),
        "lines": [dict(line) for line in context["sale_lines"]],
    }

    with db_transaction():
        for line in context["sale_lines"]:
            if not reverse_sale(str(line["row_kind"]), int(line["row_id"])):
                raise ValueError("Impossible de modifier cette facture.")
        _insert_sale_document(document_id, client_id, sale_type, sale_date, notes)
        created_lines: list[tuple[str, int]] = []
        for line in lines:
            created_lines.append(
                create_sale_record(
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
        _save_sale_document_header(document_id, client_id, sale_type, sale_date, notes)

    after_context = get_sale_document_context(document_id)
    log_activity("update_sale_document", "sale_document", document_id, f"{len(lines)} ligne(s)")
    audit_event(
        "update_sale_document",
        "sale_document",
        document_id,
        before=before,
        after={"document": after_context["sale_document"], "lines": after_context["sale_lines"]} if after_context else None,
        meta={"line_count": len(lines)},
    )
    backup_database("update_sale_document")
    return {
        "mode": "document",
        "document_id": document_id,
        "print_doc_type": "sale_document",
        "print_item_id": document_id,
        "line_count": len(lines),
        "first_line_kind": created_lines[0][0],
        "first_line_id": created_lines[0][1],
    }


def edit_sale_from_form(kind: str, row_id: int, form):
    before = get_sale(kind, row_id)
    if not before:
        raise ValueError("Vente introuvable.")
    if before["document_id"]:
        raise ValueError("Cette ligne appartient deja a une facture multi-lignes.")

    client_id = form.get("client_id") or None
    sale_date = form.get("sale_date") or date.today().isoformat()
    notes = form.get("notes", "").strip()
    sale_type = "credit" if client_id else "cash"
    lines = _extract_sale_lines(form)

    if len(lines) > 1:
        if sale_line_has_linked_payments(kind, row_id, before["client_id"]):
            raise ValueError("Cette facture est deja liee a des versements.")
        with db_transaction():
            if not reverse_sale(kind, row_id):
                raise ValueError("Impossible de modifier cette vente.")
            document_id = _insert_sale_document(None, client_id, sale_type, sale_date, notes)
            created_lines: list[tuple[str, int]] = []
            for line in lines:
                created_lines.append(
                    create_sale_record(
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

        created = query_db("SELECT * FROM sale_documents WHERE id = ?", (document_id,), one=True)
        log_activity("update_sale_document", "sale_document", document_id, f"{len(lines)} ligne(s)")
        audit_event(
            "update_sale_document",
            "sale_document",
            document_id,
            before=dict(before),
            after=created,
            meta={"line_count": len(lines), "promoted_from_row_id": row_id},
        )
        backup_database("update_sale_document")
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
        if not reverse_sale(kind, row_id):
            raise ValueError("Impossible de modifier cette vente.")
        new_kind, new_sale_id = create_sale_record(
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

    after = get_sale(new_kind, new_sale_id)
    log_activity("update_sale", "sale", row_id, f"{line['item_kind']} #{line['item_id']} qty={line['quantity']} {line['unit']}")
    audit_event("update_sale", "sale", row_id, before=before, after=after, meta={"kind": new_kind, "document_id": None})
    backup_database("update_sale")
    return {
        "mode": "line",
        "document_id": None,
        "print_doc_type": "sale_finished" if new_kind == "finished" else "sale_raw",
        "print_item_id": new_sale_id,
        "line_count": 1,
        "first_line_kind": new_kind,
        "first_line_id": new_sale_id,
    }


def delete_sale_by_id(kind: str, row_id: int) -> bool:
    before = get_sale(kind, row_id)
    ok = reverse_sale(kind, row_id)
    if ok:
        log_activity("delete_sale", "sale", row_id, f"Suppression vente {kind}")
        audit_event("delete_sale", "sale", row_id, before=before, after=None, meta={"kind": kind})
        backup_database("delete_sale")
    return ok


def get_sale_or_none(kind: str, row_id: int):
    return get_sale(kind, row_id)
