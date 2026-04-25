from __future__ import annotations

from werkzeug.utils import secure_filename

from fabouanes.core.activity import log_activity
from fabouanes.core.audit import audit_event
from fabouanes.core.db_access import execute_db, query_db
from fabouanes.core.helpers import parse_excel_client_file, parse_excel_client_history, to_float
from fabouanes.core.perf_cache import cached_result
from fabouanes.core.storage import IMPORT_DIR, backup_database, ensure_runtime_dirs
from fabouanes.repositories.client_repository import find_client_by_name, get_client, insert_client, list_clients_with_stats, update_client


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
    backup_database("create_client")
    return client_id


def clients_context():
    return cached_result(("clients_context",), lambda: {"clients": list_clients_with_stats()}, ttl_seconds=6.0)


def get_client_detail_context(client_id: int):
    return cached_result(("client_detail_context", int(client_id)), lambda: _build_client_detail_context(client_id), ttl_seconds=6.0)


def _build_client_detail_context(client_id: int):
    client = get_client(client_id)
    if not client:
        return None
    finished_sales = query_db(
        """
        SELECT s.id AS row_id, s.document_id AS document_id, s.sale_date AS event_date, f.name || ' - ' || printf('%.2f', s.quantity) || ' ' || s.unit AS designation, s.total AS purchase_amount,
               0 AS payment_amount, 'sale_finished' AS event_type
        FROM sales s JOIN finished_products f ON f.id = s.finished_product_id
        WHERE s.client_id = ?
        """,
        (client_id,),
    )
    raw_sales = query_db(
        """
        SELECT rs.id AS row_id, rs.document_id AS document_id, rs.sale_date AS event_date, r.name || ' (matiere premiere) - ' || printf('%.2f', rs.quantity) || ' ' || rs.unit AS designation, rs.total AS purchase_amount,
               0 AS payment_amount, 'sale_raw' AS event_type
        FROM raw_sales rs JOIN raw_materials r ON r.id = rs.raw_material_id
        WHERE rs.client_id = ?
        """,
        (client_id,),
    )
    payments = query_db(
        """
        SELECT p.id AS row_id, p.payment_date AS event_date,
               CASE
                   WHEN p.sale_kind = 'raw' THEN 'Versement lie a vente matiere'
                   WHEN p.sale_kind = 'finished' THEN 'Versement lie a vente produit'
                   ELSE COALESCE(NULLIF(p.notes,''), CASE WHEN p.payment_type='avance' THEN 'Avance client' ELSE 'Versement client' END)
               END AS designation,
               CASE WHEN p.payment_type='avance' THEN p.amount ELSE 0 END AS purchase_amount,
               CASE WHEN p.payment_type='versement' THEN p.amount ELSE 0 END AS payment_amount,
               CASE WHEN p.payment_type='avance' THEN 'advance' ELSE 'payment' END AS event_type
        FROM payments p WHERE p.client_id = ?
        """,
        (client_id,),
    )
    timeline = []
    if float(client["opening_credit"]) > 0:
        timeline.append(
            {
                "row_id": None,
                "document_id": None,
                "event_date": client["created_at"][:10],
                "designation": "Credit initial (reprise Excel)",
                "purchase_amount": float(client["opening_credit"]),
                "payment_amount": 0.0,
                "event_type": "opening",
            }
        )
    timeline.extend([dict(x) for x in finished_sales])
    timeline.extend([dict(x) for x in raw_sales])
    timeline.extend([dict(x) for x in payments])
    timeline.sort(key=lambda item: (item["event_date"], 0 if item["event_type"] in ("opening", "sale_finished", "sale_raw") else 1))
    running = 0.0
    for item in timeline:
        running += float(item.get("purchase_amount", 0) or 0)
        running -= float(item.get("payment_amount", 0) or 0)
        item["running_balance"] = running
    stats = {
        "opening_credit": float(client["opening_credit"]),
        "credit_sales_total": sum(float(item["purchase_amount"]) for item in timeline if item["event_type"] in ("opening", "sale_finished", "sale_raw")),
        "total_paid": sum(float(item["payment_amount"]) for item in timeline if item["event_type"] in ("payment",)),
        "total_advance": sum(float(item["purchase_amount"]) for item in timeline if item["event_type"] == "advance"),
        "current_balance": running,
    }
    return {"client": client, "timeline": timeline, "stats": stats, "client_balance": running}


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
    backup_database("update_client")


def import_clients_from_files(files):
    ensure_runtime_dirs()
    created = 0
    updated = 0
    errors = []
    for uploaded in files:
        if not uploaded or not uploaded.filename:
            continue
        filename = secure_filename(uploaded.filename)
        if not filename.lower().endswith((".xlsx", ".xlsm")):
            continue
        temp_path = IMPORT_DIR / filename
        try:
            uploaded.save(temp_path)
            parsed = parse_excel_client_file(temp_path)
            last = parse_excel_client_history(temp_path)
            opening = last["last_balance"] if last["last_balance"] > 0 else parsed["opening_credit"]
            existing = find_client_by_name(parsed["name"])
            if existing:
                before = get_client(int(existing["id"]))
                execute_db(
                    """UPDATE clients
                       SET phone = CASE WHEN COALESCE(phone,'')='' THEN ? ELSE phone END,
                           opening_credit = ?
                       WHERE id = ?""",
                    (parsed["phone"], opening, int(existing["id"])),
                )
                after = get_client(int(existing["id"]))
                audit_event("import_client_update", "client", existing["id"], before=before, after=after, meta={"source_file": filename})
                updated += 1
            else:
                client_id = insert_client(parsed["name"], parsed["phone"], parsed["address"], "", opening)
                created_client = get_client(client_id)
                audit_event("import_client_create", "client", client_id, after=created_client, meta={"source_file": filename})
                created += 1
        except Exception as exc:
            errors.append(f"{filename}: {exc}")
        finally:
            try:
                if temp_path.exists():
                    temp_path.unlink()
            except Exception:
                pass
    log_activity("import_clients_excel", "client_import", None, f"{created} crees, {updated} mis a jour")
    audit_event(
        "import_clients_excel",
        "client_import",
        None,
        after={"created": created, "updated": updated},
        meta={"errors": errors[:10]},
    )
    backup_database("import_excel")
    return {"created": created, "updated": updated, "errors": errors}
