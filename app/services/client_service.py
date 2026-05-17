from __future__ import annotations

import json
import shutil
import secrets
from time import time

from werkzeug.utils import secure_filename

from app.core.activity import log_activity
from app.core.audit import audit_event
from app.core.db_access import db_transaction, execute_db, query_db
from app.core.helpers import parse_excel_client_file, parse_excel_client_history, to_float
from app.core.perf_cache import cached_result
from app.core.storage import IMPORT_DIR, ensure_runtime_dirs, mark_backup_needed
from app.repositories.client_repository import find_client_by_name, get_client, insert_client, update_client

_IMPORT_PREVIEW_TTL_SECONDS = 30 * 60


def create_client_from_form(form):
    name = form["name"].strip()
    client_id = insert_client(
        name,
        form.get("phone", "").strip(),
        form.get("address", "").strip(),
        form.get("notes", "").strip(),
        to_float(form.get("opening_credit")),
    )
    created = get_client(client_id)
    log_activity("create_client", "client", client_id, name)
    audit_event("create_client", "client", client_id, after=created)
    mark_backup_needed("create_client")
    return client_id


def get_client_detail_context(client_id: int):
    return cached_result(("client_detail_context", int(client_id)), lambda: _build_client_detail_context(client_id), ttl_seconds=30.0)


def _build_client_detail_context(client_id: int):
    client = get_client(client_id)
    if not client:
        return None
    events = query_db(
        """
        SELECT row_id, document_id, sort_sequence, event_date, designation, item_name, quantity, unit, purchase_amount, payment_amount, event_type
        FROM (
            SELECT s.id AS row_id, s.document_id AS document_id, COALESCE(s.document_id, s.id) AS sort_sequence, s.sale_date AS event_date,
                   NULL AS designation, f.name AS item_name, s.quantity AS quantity, s.unit AS unit,
                   s.total AS purchase_amount, 0.0 AS payment_amount, 'sale_finished' AS event_type
            FROM sales s
            JOIN finished_products f ON f.id = s.finished_product_id
            WHERE s.client_id = ?
            UNION ALL
            SELECT rs.id AS row_id, rs.document_id AS document_id, COALESCE(rs.document_id, rs.id) AS sort_sequence, rs.sale_date AS event_date,
                   NULL AS designation, COALESCE(NULLIF(rs.custom_item_name, ''), r.name) AS item_name, rs.quantity AS quantity, rs.unit AS unit,
                   rs.total AS purchase_amount, 0.0 AS payment_amount, 'sale_raw' AS event_type
            FROM raw_sales rs
            JOIN raw_materials r ON r.id = rs.raw_material_id
            WHERE rs.client_id = ?
            UNION ALL
            SELECT p.id AS row_id, NULL AS document_id, p.id AS sort_sequence, p.payment_date AS event_date,
                   CASE
                       WHEN p.sale_kind = 'raw' THEN 'Versement lie a vente matière'
                       WHEN p.sale_kind = 'finished' THEN 'Versement lie a vente produit'
                       ELSE COALESCE(NULLIF(p.notes,''), CASE WHEN p.payment_type='avance' THEN 'Avance client' ELSE 'Versement client' END)
                   END AS designation,
                   NULL AS item_name, NULL AS quantity, NULL AS unit,
                   CASE WHEN p.payment_type='avance' THEN p.amount ELSE 0 END AS purchase_amount,
                   CASE WHEN p.payment_type='versement' THEN p.amount ELSE 0 END AS payment_amount,
                   CASE WHEN p.payment_type='avance' THEN 'advance' ELSE 'payment' END AS event_type
            FROM payments p
            WHERE p.client_id = ?
        ) events
        ORDER BY event_date,
                 CASE WHEN event_type IN ('sale_finished', 'sale_raw') THEN 0 ELSE 1 END,
                 row_id
        """,
        (client_id, client_id, client_id),
    )
    timeline = []
    if float(client["opening_credit"]) > 0:
        timeline.append(
            {
                "row_id": None,
                "document_id": None,
                "sort_sequence": 0,
                "event_date": client["created_at"][:10],
                "designation": "Credit initial (reprise Excel)",
                "purchase_amount": float(client["opening_credit"]),
                "payment_amount": 0.0,
                "event_type": "opening",
            }
        )
    for row in events:
        item = dict(row)
        if item["event_type"] in ("sale_finished", "sale_raw"):
            suffix = " (matière première)" if item["event_type"] == "sale_raw" else ""
            item["designation"] = f"{item['item_name']}{suffix} - {_format_quantity(item['quantity'])} {item['unit'] or ''}".strip()
        timeline.append(item)
    timeline.sort(key=lambda item: (item["event_date"], 0 if item["event_type"] in ("opening", "sale_finished", "sale_raw") else 1, int(item.get("sort_sequence") or 0)))
    running = 0.0
    for item in timeline:
        running += float(item.get("purchase_amount", 0) or 0)
        running -= float(item.get("payment_amount", 0) or 0)
        item["running_balance"] = running
    total_sales = sum(float(item["purchase_amount"]) for item in timeline if item["event_type"] in ("sale_finished", "sale_raw"))
    total_advance = sum(float(item["purchase_amount"]) for item in timeline if item["event_type"] == "advance")
    total_paid = sum(float(item["payment_amount"]) for item in timeline if item["event_type"] == "payment")
    stats = {
        "opening_credit": float(client["opening_credit"]),
        "total_sales": total_sales,
        "credit_sales_total": float(client["opening_credit"]) + total_sales,
        "total_paid": total_paid,
        "total_advance": total_advance,
        "current_balance": running,
    }
    return {"client": client, "timeline": timeline, "stats": stats, "client_balance": running}


def _format_quantity(value) -> str:
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        return "0.00"
    return f"{number:.2f}".rstrip("0").rstrip(".")


def update_client_from_form(client_id: int, form):
    before = get_client(client_id)
    update_client(
        client_id,
        form["name"].strip(),
        form.get("phone", "").strip(),
        form.get("address", "").strip(),
        form.get("notes", "").strip(),
        to_float(form.get("opening_credit")),
    )
    updated = get_client(client_id)
    log_activity("update_client", "client", client_id, form["name"].strip())
    audit_event("update_client", "client", client_id, before=before, after=updated)
    mark_backup_needed("update_client")


def _preview_path(token: str):
    clean = "".join(ch for ch in str(token or "") if ch.isalnum() or ch in {"-", "_"})
    if not clean:
        raise ValueError("Jeton de previsualisation invalide")
    return IMPORT_DIR / f"client_import_preview_{clean}.json"


def _save_client_import_preview(rows: list[dict]) -> str:
    ensure_runtime_dirs()
    token = secrets.token_urlsafe(24)
    payload = {"created_at": time(), "rows": rows}
    _preview_path(token).write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")
    return token


def _load_client_import_preview(token: str) -> list[dict]:
    path = _preview_path(token)
    if not path.exists():
        raise ValueError("Previsualisation expiree ou introuvable")
    payload = json.loads(path.read_text(encoding="utf-8"))
    created_at = float(payload.get("created_at") or 0)
    if created_at <= 0 or (time() - created_at) > _IMPORT_PREVIEW_TTL_SECONDS:
        try:
            path.unlink()
        except Exception:
            pass
        raise ValueError("Previsualisation expiree")
    rows = payload.get("rows") or []
    if not isinstance(rows, list):
        raise ValueError("Previsualisation invalide")
    return rows


def _discard_client_import_preview(token: str) -> None:
    try:
        _preview_path(token).unlink()
    except Exception:
        pass


def _parse_client_import_files(files):
    ensure_runtime_dirs()
    parsed_rows = []
    errors = []
    seen: set[str] = set()
    duplicates: list[str] = []
    for index, uploaded in enumerate(files):
        if not uploaded or not uploaded.filename:
            continue
        filename = secure_filename(uploaded.filename)
        if not filename.lower().endswith((".xlsx", ".xlsm")):
            errors.append(f"{filename}: format non supporte")
            continue
        temp_path = IMPORT_DIR / f"{index}_{filename}"
        try:
            _save_uploaded_file(uploaded, temp_path)
            parsed = parse_excel_client_file(temp_path)
            last = parse_excel_client_history(temp_path)
            opening = last["last_balance"] if last["last_balance"] > 0 else parsed["opening_credit"]
            name_key = str(parsed["name"]).strip().casefold()
            if not name_key:
                errors.append(f"{filename}: nom client introuvable")
                continue
            if name_key in seen:
                duplicates.append(parsed["name"])
                continue
            seen.add(name_key)
            existing = find_client_by_name(str(parsed["name"]))
            parsed_rows.append(
                {
                    "filename": filename,
                    "name": parsed["name"],
                    "phone": parsed["phone"],
                    "address": parsed["address"],
                    "opening_credit": opening,
                    "history_count": int(last.get("history_count", 0) or 0),
                    "status": "update" if existing else "create",
                    "existing_id": int(existing["id"]) if existing else None,
                }
            )
        except Exception as exc:
            errors.append(f"{filename}: {exc}")
        finally:
            try:
                if temp_path.exists():
                    temp_path.unlink()
            except Exception:
                pass
    return {"rows": parsed_rows, "errors": errors, "duplicates": duplicates}


def _save_uploaded_file(uploaded, temp_path) -> None:
    if hasattr(uploaded, "save"):
        uploaded.save(temp_path)
        return
    file_obj = getattr(uploaded, "file", None)
    if file_obj is not None:
        try:
            file_obj.seek(0)
        except Exception:
            pass
        with open(temp_path, "wb") as output:
            shutil.copyfileobj(file_obj, output)
        return
    content = uploaded if isinstance(uploaded, (bytes, bytearray)) else bytes(uploaded)
    with open(temp_path, "wb") as output:
        output.write(content)


def preview_clients_from_files(files):
    parsed = _parse_client_import_files(files)
    token = ""
    if parsed["rows"] and not parsed["errors"] and not parsed["duplicates"]:
        token = _save_client_import_preview(parsed["rows"])
    return {
        "rows": parsed["rows"],
        "errors": parsed["errors"],
        "duplicates": parsed["duplicates"],
        "created": sum(1 for row in parsed["rows"] if row["status"] == "create"),
        "updated": sum(1 for row in parsed["rows"] if row["status"] == "update"),
        "token": token,
    }


def _import_parsed_client_rows(rows: list[dict]):
    seen: set[str] = set()
    duplicate_names: list[str] = []
    for row in rows:
        name_key = str(row.get("name") or "").strip().casefold()
        if not name_key:
            duplicate_names.append(str(row.get("filename") or "ligne sans nom"))
        elif name_key in seen:
            duplicate_names.append(str(row.get("name") or name_key))
        seen.add(name_key)
    if duplicate_names:
        return {
            "created": 0,
            "updated": 0,
            "errors": [f"Doublon dans les fichiers: {name}" for name in duplicate_names],
            "preview": rows,
        }

    created = 0
    updated = 0
    errors = []
    try:
        with db_transaction():
            for row in rows:
                existing = find_client_by_name(str(row["name"]))
                existing_id = int(existing["id"]) if existing else 0
                if existing_id:
                    before = get_client(existing_id)
                    execute_db(
                        """UPDATE clients
                           SET phone = CASE WHEN COALESCE(phone,'')='' THEN ? ELSE phone END,
                               opening_credit = ?
                           WHERE id = ?""",
                        (row["phone"], row["opening_credit"], existing_id),
                    )
                    after = get_client(existing_id)
                    audit_event("import_client_update", "client", existing_id, before=before, after=after, meta={"source_file": row["filename"]})
                    updated += 1
                else:
                    client_id = insert_client(row["name"], row["phone"], row["address"], "", row["opening_credit"])
                    created_client = get_client(client_id)
                    audit_event("import_client_create", "client", client_id, after=created_client, meta={"source_file": row["filename"]})
                    created += 1
    except Exception as exc:
        errors.append(f"Import annule: {exc}")
        created = 0
        updated = 0
    if not errors:
        log_activity("import_clients_excel", "client_import", None, f"{created} crees, {updated} mis a jour")
        audit_event(
            "import_clients_excel",
            "client_import",
            None,
            after={"created": created, "updated": updated},
            meta={"errors": []},
        )
        mark_backup_needed("import_excel")
    return {"created": created, "updated": updated, "errors": errors, "preview": rows}


def import_clients_from_preview(token: str):
    try:
        rows = _load_client_import_preview(token)
    except Exception as exc:
        return {"created": 0, "updated": 0, "errors": [str(exc)], "preview": []}
    result = _import_parsed_client_rows(rows)
    if not result["errors"]:
        _discard_client_import_preview(token)
    return result


def import_clients_from_files(files):
    parsed = _parse_client_import_files(files)
    if parsed["errors"] or parsed["duplicates"]:
        errors = list(parsed["errors"])
        errors.extend(f"Doublon dans les fichiers: {name}" for name in parsed["duplicates"])
        return {"created": 0, "updated": 0, "errors": errors, "preview": parsed["rows"]}
    return _import_parsed_client_rows(parsed["rows"])
