from __future__ import annotations

from datetime import date

from fabouanes.core.activity import log_activity
from fabouanes.core.audit import audit_event
from fabouanes.core.db_access import db_transaction, execute_db, query_db
from fabouanes.core.helpers import create_purchase_record, reverse_purchase, to_float, unit_choices
from fabouanes.core.storage import backup_database
from fabouanes.repositories.purchase_repository import (
    get_purchase,
    get_purchase_document,
    list_purchase_document_lines,
    list_purchase_form_context,
    list_purchase_page_context,
)


def purchases_context():
    return _build_purchases_context()


def purchase_form_context():
    context = list_purchase_form_context()
    context["units"] = unit_choices()
    return context


def _build_purchases_context():
    context = list_purchase_page_context()
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


def _extract_purchase_lines(form) -> list[dict[str, object]]:
    raw_ids = _form_list(form, "raw_material_id[]")
    quantities = _form_list(form, "quantity[]")
    units = _form_list(form, "unit[]")
    unit_prices = _form_list(form, "unit_price[]")
    custom_names = _form_list(form, "custom_item_name[]")
    line_count = max(len(raw_ids), len(quantities), len(units), len(unit_prices), len(custom_names))
    lines: list[dict[str, object]] = []
    other_cache: dict[int, bool] = {}
    for idx in range(line_count):
        raw_id = raw_ids[idx] if idx < len(raw_ids) else ""
        qty_raw = quantities[idx] if idx < len(quantities) else ""
        unit = units[idx] if idx < len(units) and units[idx] else "kg"
        unit_price_raw = unit_prices[idx] if idx < len(unit_prices) else ""
        custom_item_name = custom_names[idx] if idx < len(custom_names) else ""
        if not any([raw_id, qty_raw, unit_price_raw]):
            continue
        qty = to_float(qty_raw)
        unit_price = to_float(unit_price_raw)
        if qty <= 0:
            raise ValueError("Chaque ligne d'achat doit avoir une quantite superieure a zero.")
        if unit_price <= 0:
            raise ValueError("Chaque ligne d'achat doit avoir un prix unitaire superieur a zero.")
        raw_id_int = int(raw_id)
        if raw_id_int not in other_cache:
            material = query_db("SELECT name FROM raw_materials WHERE id = ?", (raw_id_int,), one=True)
            if not material:
                raise ValueError("Matiere premiere introuvable.")
            other_cache[raw_id_int] = str(material["name"] or "").strip().casefold() == "autre"
        custom_item_name = custom_item_name.strip()
        if other_cache[raw_id_int] and not custom_item_name:
            raise ValueError("Precise le nom du produit pour la ligne AUTRE.")
        lines.append(
            {
                "raw_id": raw_id_int,
                "quantity": qty,
                "unit": unit,
                "unit_price": unit_price,
                "custom_item_name": custom_item_name,
            }
        )
    if not lines:
        raise ValueError("Ajoute au moins une ligne a ce bon d'achat.")
    return lines


def _insert_purchase_document(document_id, supplier_id, purchase_date: str, notes: str) -> int:
    if document_id:
        execute_db(
            "INSERT INTO purchase_documents (id, supplier_id, total, purchase_date, notes) VALUES (?, ?, 0, ?, ?)",
            (int(document_id), supplier_id, purchase_date, notes),
        )
        return int(document_id)
    return execute_db(
        "INSERT INTO purchase_documents (supplier_id, total, purchase_date, notes) VALUES (?, 0, ?, ?)",
        (supplier_id, purchase_date, notes),
    )


def _save_purchase_document_header(document_id: int, supplier_id, purchase_date: str, notes: str) -> None:
    existing = query_db("SELECT id FROM purchase_documents WHERE id = ?", (document_id,), one=True)
    if not existing:
        _insert_purchase_document(document_id, supplier_id, purchase_date, notes)
        return
    execute_db(
        "UPDATE purchase_documents SET supplier_id = ?, purchase_date = ?, notes = ? WHERE id = ?",
        (supplier_id, purchase_date, notes, document_id),
    )


def _serialize_purchase_lines(lines) -> list[dict[str, object]]:
    payload = []
    for line in lines:
        payload.append(
            {
                "row_id": int(line["row_id"]),
                "document_id": int(line["document_id"]) if line["document_id"] else None,
                "raw_material_id": int(line["raw_material_id"]),
                "material_name": str(line["material_name"]),
                "quantity": float(line["display_quantity"]),
                "unit": str(line["display_unit"]),
                "unit_price": float(line["display_unit_price"]),
                "total": float(line["total"]),
                "custom_item_name": str(line["custom_item_name"] or ""),
            }
        )
    return payload


def get_purchase_document_context(document_id: int):
    document = get_purchase_document(document_id)
    if not document:
        return None
    lines = list_purchase_document_lines(document_id)
    return {
        "purchase_document": dict(document),
        "purchase_lines": _serialize_purchase_lines(lines),
    }


def get_purchase_edit_context(purchase_id: int):
    purchase = get_purchase(purchase_id)
    if not purchase:
        return None
    if purchase["document_id"]:
        context = get_purchase_document_context(int(purchase["document_id"]))
        if context:
            context["redirect_document_id"] = int(purchase["document_id"])
        return context
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
                "raw_material_id": int(purchase["raw_material_id"]),
                "material_name": str(purchase["material_name"]),
                "quantity": float(purchase["display_quantity"]),
                "unit": str(purchase["display_unit"]),
                "unit_price": float(purchase["display_unit_price"]),
                "total": float(purchase["total"]),
                "custom_item_name": str(purchase["custom_item_name"] or ""),
            }
        ],
    }


def create_purchase_from_form(form):
    supplier_id = form.get("supplier_id") or None
    purchase_date = form.get("purchase_date") or date.today().isoformat()
    notes = form.get("notes", "").strip()
    lines = _extract_purchase_lines(form)
    use_document = len(lines) > 1 or bool(form.getlist("raw_material_id[]"))

    if not use_document:
        line = lines[0]
        purchase_id = create_purchase_record(
            supplier_id,
            int(line["raw_id"]),
            float(line["quantity"]),
            float(line["unit_price"]),
            purchase_date,
            notes,
            str(line["unit"]),
            custom_item_name=str(line["custom_item_name"]),
        )
        created = get_purchase(purchase_id)
        log_activity("create_purchase", "purchase", purchase_id, f"matiere #{line['raw_id']} qty={line['quantity']}")
        audit_event("create_purchase", "purchase", purchase_id, after=created)
        backup_database("create_purchase")
        return {
            "mode": "line",
            "document_id": None,
            "print_doc_type": "purchase",
            "print_item_id": purchase_id,
            "line_count": 1,
            "first_purchase_id": purchase_id,
        }

    with db_transaction():
        document_id = _insert_purchase_document(None, supplier_id, purchase_date, notes)
        created_ids: list[int] = []
        for line in lines:
            created_ids.append(
                create_purchase_record(
                    supplier_id,
                    int(line["raw_id"]),
                    float(line["quantity"]),
                    float(line["unit_price"]),
                    purchase_date,
                    notes,
                    str(line["unit"]),
                    document_id=document_id,
                    custom_item_name=str(line["custom_item_name"]),
                )
            )

    created = query_db("SELECT * FROM purchase_documents WHERE id = ?", (document_id,), one=True)
    log_activity("create_purchase_document", "purchase_document", document_id, f"{len(lines)} ligne(s)")
    audit_event("create_purchase_document", "purchase_document", document_id, after=created, meta={"line_count": len(lines)})
    backup_database("create_purchase_document")
    return {
        "mode": "document",
        "document_id": document_id,
        "print_doc_type": "purchase_document",
        "print_item_id": document_id,
        "line_count": len(lines),
        "first_purchase_id": created_ids[0],
    }


def edit_purchase_document_from_form(document_id: int, form):
    context = get_purchase_document_context(document_id)
    if not context:
        raise ValueError("Bon d'achat introuvable.")

    supplier_id = form.get("supplier_id") or None
    purchase_date = form.get("purchase_date") or date.today().isoformat()
    notes = form.get("notes", "").strip()
    lines = _extract_purchase_lines(form)
    before = {
        "document": dict(context["purchase_document"]),
        "lines": [dict(line) for line in context["purchase_lines"]],
    }

    with db_transaction():
        for line in context["purchase_lines"]:
            if not reverse_purchase(int(line["row_id"])):
                raise ValueError("Impossible de modifier cet achat car le stock ne permet pas de l'annuler.")
        _insert_purchase_document(document_id, supplier_id, purchase_date, notes)
        created_ids: list[int] = []
        for line in lines:
            created_ids.append(
                create_purchase_record(
                    supplier_id,
                    int(line["raw_id"]),
                    float(line["quantity"]),
                    float(line["unit_price"]),
                    purchase_date,
                    notes,
                    str(line["unit"]),
                    document_id=document_id,
                    custom_item_name=str(line["custom_item_name"]),
                )
            )
        _save_purchase_document_header(document_id, supplier_id, purchase_date, notes)

    after_context = get_purchase_document_context(document_id)
    log_activity("update_purchase_document", "purchase_document", document_id, f"{len(lines)} ligne(s)")
    audit_event(
        "update_purchase_document",
        "purchase_document",
        document_id,
        before=before,
        after={"document": after_context["purchase_document"], "lines": after_context["purchase_lines"]} if after_context else None,
        meta={"line_count": len(lines)},
    )
    backup_database("update_purchase_document")
    return {
        "mode": "document",
        "document_id": document_id,
        "print_doc_type": "purchase_document",
        "print_item_id": document_id,
        "line_count": len(lines),
        "first_purchase_id": created_ids[0],
    }


def edit_purchase_from_form(purchase_id: int, form):
    before = get_purchase(purchase_id)
    if not before:
        raise ValueError("Achat introuvable.")
    if before["document_id"]:
        raise ValueError("Cette ligne appartient deja a un bon multi-lignes.")

    supplier_id = form.get("supplier_id") or None
    purchase_date = form.get("purchase_date") or date.today().isoformat()
    notes = form.get("notes", "").strip()
    lines = _extract_purchase_lines(form)

    if len(lines) > 1:
        with db_transaction():
            if not reverse_purchase(purchase_id):
                raise ValueError("Impossible de modifier cet achat car le stock ne permet pas de l'annuler.")
            document_id = _insert_purchase_document(None, supplier_id, purchase_date, notes)
            created_ids: list[int] = []
            for line in lines:
                created_ids.append(
                    create_purchase_record(
                        supplier_id,
                        int(line["raw_id"]),
                        float(line["quantity"]),
                        float(line["unit_price"]),
                        purchase_date,
                        notes,
                        str(line["unit"]),
                        document_id=document_id,
                        custom_item_name=str(line["custom_item_name"]),
                    )
                )

        created = query_db("SELECT * FROM purchase_documents WHERE id = ?", (document_id,), one=True)
        log_activity("update_purchase_document", "purchase_document", document_id, f"{len(lines)} ligne(s)")
        audit_event(
            "update_purchase_document",
            "purchase_document",
            document_id,
            before=dict(before),
            after=created,
            meta={"line_count": len(lines), "promoted_from_purchase_id": purchase_id},
        )
        backup_database("update_purchase_document")
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
        if not reverse_purchase(purchase_id):
            raise ValueError("Impossible de modifier cet achat car le stock ne permet pas de l'annuler.")
        new_purchase_id = create_purchase_record(
            supplier_id,
            int(line["raw_id"]),
            float(line["quantity"]),
            float(line["unit_price"]),
            purchase_date,
            notes,
            str(line["unit"]),
            custom_item_name=str(line["custom_item_name"]),
        )

    latest = get_purchase(new_purchase_id)
    log_activity("update_purchase", "purchase", purchase_id, f"matiere #{line['raw_id']} qty={line['quantity']}")
    audit_event("update_purchase", "purchase", purchase_id, before=before, after=latest, meta={"document_id": None})
    backup_database("update_purchase")
    return {
        "mode": "line",
        "document_id": None,
        "print_doc_type": "purchase",
        "print_item_id": new_purchase_id,
        "line_count": 1,
        "first_purchase_id": new_purchase_id,
    }


def delete_purchase_by_id(purchase_id: int) -> bool:
    before = get_purchase(purchase_id)
    ok = reverse_purchase(purchase_id)
    if ok:
        log_activity("delete_purchase", "purchase", purchase_id, "Suppression achat")
        audit_event("delete_purchase", "purchase", purchase_id, before=before, after=None)
        backup_database("delete_purchase")
    return ok


def get_purchase_or_none(purchase_id: int):
    return get_purchase(purchase_id)
