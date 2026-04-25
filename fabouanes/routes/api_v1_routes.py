from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Any

from flask import current_app, g, jsonify, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.datastructures import MultiDict

from fabouanes.core.activity import log_activity
from fabouanes.core.audit import audit_event
from fabouanes.core.db_access import execute_db, query_db
from fabouanes.core.permissions import (
    PERMISSION_API_ACCESS,
    PERMISSION_AUDIT_READ,
    PERMISSION_CATALOG_DELETE,
    PERMISSION_CATALOG_READ,
    PERMISSION_CATALOG_WRITE,
    PERMISSION_CONTACTS_DELETE,
    PERMISSION_CONTACTS_READ,
    PERMISSION_CONTACTS_WRITE,
    PERMISSION_DASHBOARD_READ,
    PERMISSION_OPERATIONS_DELETE,
    PERMISSION_OPERATIONS_READ,
    PERMISSION_OPERATIONS_WRITE,
    PERMISSION_PRODUCTION_DELETE,
    PERMISSION_PRODUCTION_READ,
    PERMISSION_PRODUCTION_WRITE,
    has_permission,
)
from fabouanes.repositories.client_repository import client_stats_query, get_client_with_stats
from fabouanes.repositories.payment_repository import get_payment
from fabouanes.repositories.purchase_repository import get_purchase
from fabouanes.repositories.sale_repository import build_sellable_items
from fabouanes.repositories.sale_repository import get_sale
from fabouanes.repositories.user_repository import get_user_by_id
from fabouanes.routes.route_utils import bind_route
from fabouanes.services.auth_service import attempt_login
from fabouanes.services.client_service import create_client_from_form, get_client_detail_context, update_client_from_form
from fabouanes.services.payment_service import create_payment_from_form, delete_payment_by_id, edit_payment_from_form
from fabouanes.services.production_service import create_production_from_form, delete_production_by_id
from fabouanes.services.purchase_service import (
    create_purchase_from_form,
    delete_purchase_by_id,
    edit_purchase_document_from_form,
    edit_purchase_from_form,
    get_purchase_document_context,
)
from fabouanes.services.sale_service import (
    create_sale_from_form,
    delete_sale_by_id,
    edit_sale_document_from_form,
    edit_sale_from_form,
    get_sale_document_context,
)

ACCESS_TOKEN_TTL_SECONDS = 15 * 60
REFRESH_TOKEN_TTL_DAYS = 30


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="fabouanes-api-access")


def _api_success(data: Any, meta: dict[str, Any] | None = None, status: int = 200):
    payload = {"data": data, "meta": meta or {}}
    return jsonify(payload), status


def _api_error(code: str, message: str, status: int, details: Any = None):
    return jsonify({"error": {"code": code, "message": message, "details": details}}), status


def _access_token_for_user(user) -> str:
    return _serializer().dumps({"sub": int(user["id"]), "role": user["role"], "username": user["username"]})


def _refresh_token_hash(token: str) -> str:
    return hashlib.sha256((token or "").encode("utf-8")).hexdigest()


def _create_refresh_token(user) -> str:
    raw_token = secrets.token_urlsafe(48)
    expires_at = (datetime.utcnow() + timedelta(days=REFRESH_TOKEN_TTL_DAYS)).strftime("%Y-%m-%d %H:%M:%S")
    execute_db(
        """
        INSERT INTO api_refresh_tokens (user_id, token_hash, token_hint, created_ip, user_agent, expires_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            int(user["id"]),
            _refresh_token_hash(raw_token),
            raw_token[-8:],
            request.remote_addr or "",
            request.headers.get("User-Agent", "")[:500],
            expires_at,
        ),
    )
    return raw_token


def _revoke_refresh_token(raw_token: str) -> None:
    execute_db(
        "UPDATE api_refresh_tokens SET revoked_at = CURRENT_TIMESTAMP WHERE token_hash = ? AND revoked_at IS NULL",
        (_refresh_token_hash(raw_token),),
    )


def _revoke_all_user_tokens(user_id: int) -> None:
    execute_db(
        "UPDATE api_refresh_tokens SET revoked_at = CURRENT_TIMESTAMP WHERE user_id = ? AND revoked_at IS NULL",
        (int(user_id),),
    )


def _validate_refresh_token(raw_token: str):
    row = query_db(
        """
        SELECT *
        FROM api_refresh_tokens
        WHERE token_hash = ?
          AND revoked_at IS NULL
          AND expires_at >= CURRENT_TIMESTAMP
        """,
        (_refresh_token_hash(raw_token),),
        one=True,
    )
    if not row:
        return None
    user = get_user_by_id(int(row["user_id"]))
    if not user or not int(user.get("is_active", 1) or 0):
        _revoke_refresh_token(raw_token)
        return None
    execute_db("UPDATE api_refresh_tokens SET last_used_at = CURRENT_TIMESTAMP WHERE id = ?", (int(row["id"]),))
    return user


def _decode_access_token(raw_token: str):
    try:
        payload = _serializer().loads(raw_token, max_age=ACCESS_TOKEN_TTL_SECONDS)
    except SignatureExpired:
        return None, _api_error("access_token_expired", "Le jeton d'acces a expire.", 401)
    except BadSignature:
        return None, _api_error("access_token_invalid", "Jeton d'acces invalide.", 401)
    user = get_user_by_id(int(payload.get("sub", 0) or 0))
    if not user or not int(user.get("is_active", 1) or 0):
        return None, _api_error("unauthorized", "Utilisateur indisponible.", 401)
    return user, None


def _bearer_token() -> str:
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()
    return ""


def _pagination_meta():
    page = max(request.args.get("page", 1, type=int), 1)
    page_size = min(max(request.args.get("page_size", 50, type=int), 1), 200)
    offset = (page - 1) * page_size
    return page, page_size, offset


def _json_payload() -> dict[str, Any]:
    return dict(request.get_json(silent=True) or {})


def _form_payload_from_json(payload: dict[str, Any]) -> MultiDict:
    items: list[tuple[str, Any]] = []
    for key, value in payload.items():
        if isinstance(value, list):
            for item in value:
                items.append((key, item))
        else:
            items.append((key, value))
    return MultiDict(items)


def _api_token_required(permission: str):
    def decorator(view):
        def wrapped(*args, **kwargs):
            raw_token = _bearer_token()
            if not raw_token:
                return _api_error("unauthorized", "Jeton Bearer requis.", 401)
            user, error_response = _decode_access_token(raw_token)
            if error_response:
                return error_response
            if not has_permission(user, PERMISSION_API_ACCESS) or not has_permission(user, permission):
                audit_event(
                    "permission_denied",
                    "api",
                    request.path,
                    source="api",
                    status="failure",
                    actor={"id": user["id"], "username": user["username"], "role": user["role"]},
                    meta={"permission": permission},
                )
                return _api_error("forbidden", "Permission refusee.", 403, {"permission": permission})
            g.user = user
            g.audit_source = "api"
            return view(*args, **kwargs)

        wrapped.__name__ = f"{view.__name__}_wrapped"
        return wrapped

    return decorator


def _query_list(query: str, params: tuple[Any, ...] = ()):
    page, page_size, offset = _pagination_meta()
    count_row = query_db(f"SELECT COUNT(*) AS c FROM ({query}) list_query", tuple(params), one=True)
    paged_query = f"{query} LIMIT ? OFFSET ?"
    rows = query_db(paged_query, tuple(params) + (page_size, offset))
    return [dict(row) for row in rows], {"page": page, "page_size": page_size, "returned": len(rows), "total": int(count_row["c"] if count_row else 0)}


def _like_value() -> str:
    return f"%{request.args.get('q', '').strip()}%"


def _append_text_search(where: list[str], params: list[Any], *fields: str) -> None:
    if not request.args.get("q", "").strip():
        return
    clause = " OR ".join(f"LOWER(COALESCE({field}, '')) LIKE LOWER(?)" for field in fields)
    where.append(f"({clause})")
    like = _like_value()
    params.extend([like] * len(fields))


def _append_date_range(where: list[str], params: list[Any], field: str) -> None:
    date_from = str(request.args.get("date_from", "") or "").strip()
    date_to = str(request.args.get("date_to", "") or "").strip()
    if date_from:
        where.append(f"{field} >= ?")
        params.append(date_from)
    if date_to:
        where.append(f"{field} <= ?")
        params.append(date_to)


def _api_cors_origin() -> str:
    return request.headers.get("Origin", "*") or "*"


def _apply_api_cors(response):
    if request.path.startswith("/api/v1/"):
        response.headers["Access-Control-Allow-Origin"] = _api_cors_origin()
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type, X-Requested-With"
        response.headers["Access-Control-Max-Age"] = "86400"
        response.headers["Vary"] = "Origin"
        if request.headers.get("Access-Control-Request-Private-Network"):
            response.headers["Access-Control-Allow-Private-Network"] = "true"
    return response


def _ping_payload() -> dict[str, Any]:
    return {"ok": True, "service": "FABOuanes", "version": "v10.12"}


def _client_payload(client_id: int):
    row = get_client_with_stats(client_id)
    return dict(row) if row else None


def _supplier_payload(supplier_id: int):
    row = query_db("SELECT * FROM suppliers WHERE id = ?", (supplier_id,), one=True)
    return dict(row) if row else None


def _raw_material_payload(material_id: int):
    row = query_db(
        """
        SELECT *,
               CASE WHEN stock_qty <= COALESCE(NULLIF(threshold_qty, 0), alert_threshold) THEN 1 ELSE 0 END AS is_low_stock,
               'raw' AS item_type
        FROM raw_materials
        WHERE id = ?
        """,
        (material_id,),
        one=True,
    )
    return dict(row) if row else None


def _finished_product_payload(product_id: int):
    row = query_db(
        """
        SELECT *, 'finished' AS item_type
        FROM finished_products
        WHERE id = ?
        """,
        (product_id,),
        one=True,
    )
    return dict(row) if row else None


def _production_payload(batch_id: int):
    row = query_db(
        """
        SELECT pb.*, fp.name AS product_name, fp.default_unit AS product_unit
        FROM production_batches pb
        JOIN finished_products fp ON fp.id = pb.finished_product_id
        WHERE pb.id = ?
        """,
        (batch_id,),
        one=True,
    )
    return dict(row) if row else None


def _purchase_payload(purchase_id: int):
    row = query_db(
        """
        SELECT p.*, COALESCE(s.name, 'Sans fournisseur') AS supplier_name, COALESCE(NULLIF(p.custom_item_name, ''), r.name) AS material_name, r.unit AS material_unit
        FROM purchases p
        LEFT JOIN suppliers s ON s.id = p.supplier_id
        JOIN raw_materials r ON r.id = p.raw_material_id
        WHERE p.id = ?
        """,
        (purchase_id,),
        one=True,
    )
    return dict(row) if row else None


def _sale_payload(kind: str, row_id: int):
    if kind == "finished":
        row = query_db(
            """
            SELECT s.*, COALESCE(c.name, 'Comptoir') AS client_name, f.name AS item_name,
                   'Produit fini' AS item_kind, 'finished' AS row_kind, 'finished:' || s.finished_product_id AS item_key
            FROM sales s
            LEFT JOIN clients c ON c.id = s.client_id
            JOIN finished_products f ON f.id = s.finished_product_id
            WHERE s.id = ?
            """,
            (row_id,),
            one=True,
        )
    else:
        row = query_db(
            """
            SELECT rs.*, COALESCE(c.name, 'Comptoir') AS client_name, COALESCE(NULLIF(rs.custom_item_name, ''), r.name) AS item_name,
                   'Matiere premiere' AS item_kind, 'raw' AS row_kind, 'raw:' || rs.raw_material_id AS item_key
            FROM raw_sales rs
            LEFT JOIN clients c ON c.id = rs.client_id
            JOIN raw_materials r ON r.id = rs.raw_material_id
            WHERE rs.id = ?
            """,
            (row_id,),
            one=True,
        )
    return dict(row) if row else None


def _purchase_document_payload(document_id: int):
    context = get_purchase_document_context(document_id)
    if not context:
        return None
    return {
        "document": dict(context["purchase_document"]),
        "lines": [dict(line) for line in context["purchase_lines"]],
        "line_count": len(context["purchase_lines"]),
    }


def _sale_document_payload(document_id: int):
    context = get_sale_document_context(document_id)
    if not context:
        return None
    return {
        "document": dict(context["sale_document"]),
        "lines": [dict(line) for line in context["sale_lines"]],
        "line_count": len(context["sale_lines"]),
        "has_linked_payments": bool(context["has_linked_payments"]),
    }


def _payment_payload(payment_id: int):
    row = query_db(
        """
        SELECT p.*, c.name AS client_name,
               CASE
                   WHEN p.sale_kind = 'finished' AND p.sale_id IS NOT NULL THEN 'finished:' || p.sale_id
                   WHEN p.sale_kind = 'raw' AND p.raw_sale_id IS NOT NULL THEN 'raw:' || p.raw_sale_id
                   ELSE ''
               END AS sale_link,
               CASE
                   WHEN p.sale_kind = 'finished' AND p.sale_id IS NOT NULL THEN 'Produit #' || p.sale_id
                   WHEN p.sale_kind = 'raw' AND p.raw_sale_id IS NOT NULL THEN 'Matiere #' || p.raw_sale_id
                   ELSE '-'
               END AS sale_ref
        FROM payments p
        JOIN clients c ON c.id = p.client_id
        WHERE p.id = ?
        """,
        (payment_id,),
        one=True,
    )
    return dict(row) if row else None


def register_api_v1_routes(app):
    if not app.config.get("_FAB_API_V1_CORS"):
        app.after_request(_apply_api_cors)
        app.config["_FAB_API_V1_CORS"] = True

    def api_ping():
        return _api_success(_ping_payload())

    def api_auth_login():
        payload = _json_payload()
        result = attempt_login(payload.get("username", ""), payload.get("password", ""))
        if not result["ok"]:
            return _api_error("login_failed", result["message"], int(result.get("status") or 401))
        user = result["user"]
        access_token = _access_token_for_user(user)
        refresh_token = _create_refresh_token(user)
        audit_event("api_login", "user", user["id"], source="api", after={"username": user["username"]})
        return _api_success(
            {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "Bearer",
                "expires_in": ACCESS_TOKEN_TTL_SECONDS,
                "user": {
                    "id": user["id"],
                    "username": user["username"],
                    "role": user["role"],
                    "must_change_password": bool(int(user.get("must_change_password", 0) or 0)),
                },
            }
        )

    def api_auth_refresh():
        payload = _json_payload()
        raw_refresh = str(payload.get("refresh_token", "") or "").strip()
        user = _validate_refresh_token(raw_refresh)
        if not user:
            return _api_error("refresh_token_invalid", "Jeton de renouvellement invalide.", 401)
        access_token = _access_token_for_user(user)
        audit_event("api_refresh", "user", user["id"], source="api", after={"username": user["username"]})
        return _api_success({"access_token": access_token, "token_type": "Bearer", "expires_in": ACCESS_TOKEN_TTL_SECONDS})

    @_api_token_required(PERMISSION_API_ACCESS)
    def api_auth_logout():
        payload = _json_payload()
        raw_refresh = str(payload.get("refresh_token", "") or "").strip()
        if raw_refresh:
            _revoke_refresh_token(raw_refresh)
        else:
            _revoke_all_user_tokens(int(g.user["id"]))
        log_activity("api_logout", "user", g.user["id"], f"API logout {g.user['username']}")
        audit_event("api_logout", "user", g.user["id"], source="api", after={"username": g.user["username"]})
        return _api_success({"revoked": True})

    @_api_token_required(PERMISSION_DASHBOARD_READ)
    def api_auth_me():
        return _api_success(
            {
                "id": g.user["id"],
                "username": g.user["username"],
                "role": g.user["role"],
                "must_change_password": bool(int(g.user.get("must_change_password", 0) or 0)),
                "last_login_at": g.user.get("last_login_at"),
                "last_password_change_at": g.user.get("last_password_change_at"),
            }
        )

    @_api_token_required(PERMISSION_DASHBOARD_READ)
    def api_dashboard_summary():
        from fabouanes.repositories.dashboard_repository import get_dashboard_snapshot

        snapshot = get_dashboard_snapshot(request.args.get("date"))
        return _api_success(dict(snapshot))

    @_api_token_required(PERMISSION_CONTACTS_READ)
    def api_clients():
        if request.method == "POST":
            if not has_permission(g.user, PERMISSION_CONTACTS_WRITE):
                return _api_error("forbidden", "Permission refusee.", 403)
            payload = _json_payload()
            client_id = create_client_from_form(payload)
            return _api_success(_client_payload(client_id), status=201)
        where: list[str] = []
        params: list[Any] = []
        _append_text_search(where, params, "c.name", "c.phone", "c.address")
        query = client_stats_query()
        if where:
            query = client_stats_query(" AND ".join(where))
        query += " ORDER BY c.name"
        rows, meta = _query_list(query, tuple(params))
        return _api_success(rows, meta)

    @_api_token_required(PERMISSION_CONTACTS_READ)
    def api_client_detail(client_id: int):
        client = _client_payload(client_id)
        if not client:
            return _api_error("not_found", "Client introuvable.", 404)
        if request.method == "PUT":
            if not has_permission(g.user, PERMISSION_CONTACTS_WRITE):
                return _api_error("forbidden", "Permission refusee.", 403)
            update_client_from_form(client_id, _json_payload())
            client = _client_payload(client_id)
        detail_context = get_client_detail_context(client_id) or {}
        client["summary"] = detail_context.get("stats", {})
        return _api_success(client)

    @_api_token_required(PERMISSION_CONTACTS_READ)
    def api_client_history(client_id: int):
        detail_context = get_client_detail_context(client_id)
        if not detail_context:
            return _api_error("not_found", "Client introuvable.", 404)
        return _api_success(
            {
                "client": _client_payload(client_id),
                "history": detail_context.get("timeline", []),
                "stats": detail_context.get("stats", {}),
                "current_balance": float(detail_context.get("client_balance") or 0),
            }
        )

    @_api_token_required(PERMISSION_CONTACTS_READ)
    def api_suppliers():
        if request.method == "POST":
            if not has_permission(g.user, PERMISSION_CONTACTS_WRITE):
                return _api_error("forbidden", "Permission refusee.", 403)
            payload = _json_payload()
            supplier_id = execute_db(
                "INSERT INTO suppliers (name, phone, address, notes) VALUES (?, ?, ?, ?)",
                (payload.get("name", "").strip(), payload.get("phone", "").strip(), payload.get("address", "").strip(), payload.get("notes", "").strip()),
            )
            supplier = _supplier_payload(supplier_id)
            audit_event("create_supplier", "supplier", supplier_id, source="api", after=supplier)
            log_activity("create_supplier", "supplier", supplier_id, payload.get("name", "").strip())
            return _api_success(supplier, status=201)
        where: list[str] = []
        params: list[Any] = []
        _append_text_search(where, params, "name", "phone", "address")
        query = "SELECT * FROM suppliers"
        if where:
            query += " WHERE " + " AND ".join(where)
        query += " ORDER BY name"
        rows, meta = _query_list(query, tuple(params))
        return _api_success(rows, meta)

    @_api_token_required(PERMISSION_CONTACTS_READ)
    def api_supplier_detail(supplier_id: int):
        supplier = _supplier_payload(supplier_id)
        if not supplier:
            return _api_error("not_found", "Fournisseur introuvable.", 404)
        if request.method == "PUT":
            if not has_permission(g.user, PERMISSION_CONTACTS_WRITE):
                return _api_error("forbidden", "Permission refusee.", 403)
            payload = _json_payload()
            before = dict(supplier)
            execute_db(
                "UPDATE suppliers SET name = ?, phone = ?, address = ?, notes = ? WHERE id = ?",
                (payload.get("name", supplier["name"]), payload.get("phone", supplier["phone"]), payload.get("address", supplier["address"]), payload.get("notes", supplier["notes"]), supplier_id),
            )
            supplier = _supplier_payload(supplier_id)
            audit_event("update_supplier", "supplier", supplier_id, source="api", before=before, after=supplier)
        elif request.method == "DELETE":
            if not has_permission(g.user, PERMISSION_CONTACTS_DELETE):
                return _api_error("forbidden", "Permission refusee.", 403)
            before = dict(supplier)
            execute_db("DELETE FROM suppliers WHERE id = ?", (supplier_id,))
            audit_event("delete_supplier", "supplier", supplier_id, source="api", before=before, after=None)
            return _api_success({"deleted": True})
        return _api_success(supplier)

    @_api_token_required(PERMISSION_CATALOG_READ)
    def api_raw_materials():
        if request.method == "POST":
            if not has_permission(g.user, PERMISSION_CATALOG_WRITE):
                return _api_error("forbidden", "Permission refusee.", 403)
            payload = _json_payload()
            material_id = execute_db(
                "INSERT INTO raw_materials (name, unit, stock_qty, avg_cost, sale_price, alert_threshold, threshold_qty) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    payload.get("name", "").strip(),
                    payload.get("unit", "kg"),
                    float(payload.get("stock_qty", 0) or 0),
                    float(payload.get("avg_cost", 0) or 0),
                    float(payload.get("sale_price", 0) or 0),
                    float(payload.get("alert_threshold", 0) or 0),
                    float(payload.get("threshold_qty", payload.get("alert_threshold", 0)) or 0),
                ),
            )
            material = _raw_material_payload(material_id)
            audit_event("create_raw_material", "raw_material", material_id, source="api", after=material)
            return _api_success(material, status=201)
        where: list[str] = []
        params: list[Any] = []
        _append_text_search(where, params, "name", "unit")
        status = str(request.args.get("status", "") or "").strip().lower()
        if status == "low":
            where.append("stock_qty <= COALESCE(NULLIF(threshold_qty, 0), alert_threshold)")
        query = """
            SELECT *,
                   CASE WHEN stock_qty <= COALESCE(NULLIF(threshold_qty, 0), alert_threshold) THEN 1 ELSE 0 END AS is_low_stock,
                   'raw' AS item_type
            FROM raw_materials
        """
        if where:
            query += " WHERE " + " AND ".join(where)
        query += " ORDER BY name"
        rows, meta = _query_list(query, tuple(params))
        return _api_success(rows, meta)

    @_api_token_required(PERMISSION_CATALOG_READ)
    def api_raw_material_detail(material_id: int):
        material = _raw_material_payload(material_id)
        if not material:
            return _api_error("not_found", "Matiere premiere introuvable.", 404)
        if request.method == "PUT":
            if not has_permission(g.user, PERMISSION_CATALOG_WRITE):
                return _api_error("forbidden", "Permission refusee.", 403)
            payload = _json_payload()
            before = dict(material)
            execute_db(
                "UPDATE raw_materials SET name = ?, unit = ?, stock_qty = ?, avg_cost = ?, sale_price = ?, alert_threshold = ?, threshold_qty = ? WHERE id = ?",
                (
                    payload.get("name", material["name"]),
                    payload.get("unit", material["unit"]),
                    float(payload.get("stock_qty", material["stock_qty"]) or 0),
                    float(payload.get("avg_cost", material["avg_cost"]) or 0),
                    float(payload.get("sale_price", material["sale_price"]) or 0),
                    float(payload.get("alert_threshold", material["alert_threshold"]) or 0),
                    float(payload.get("threshold_qty", material["threshold_qty"]) or 0),
                    material_id,
                ),
            )
            material = _raw_material_payload(material_id)
            audit_event("update_raw_material", "raw_material", material_id, source="api", before=before, after=material)
        elif request.method == "DELETE":
            if not has_permission(g.user, PERMISSION_CATALOG_DELETE):
                return _api_error("forbidden", "Permission refusee.", 403)
            before = dict(material)
            execute_db("DELETE FROM raw_materials WHERE id = ?", (material_id,))
            audit_event("delete_raw_material", "raw_material", material_id, source="api", before=before, after=None)
            return _api_success({"deleted": True})
        return _api_success(material)

    @_api_token_required(PERMISSION_CATALOG_READ)
    def api_finished_products():
        if request.method == "POST":
            if not has_permission(g.user, PERMISSION_CATALOG_WRITE):
                return _api_error("forbidden", "Permission refusee.", 403)
            payload = _json_payload()
            product_id = execute_db(
                "INSERT INTO finished_products (name, default_unit, stock_qty, sale_price, avg_cost) VALUES (?, ?, ?, ?, ?)",
                (
                    payload.get("name", "").strip(),
                    payload.get("default_unit", "kg"),
                    float(payload.get("stock_qty", 0) or 0),
                    float(payload.get("sale_price", 0) or 0),
                    float(payload.get("avg_cost", 0) or 0),
                ),
            )
            product = _finished_product_payload(product_id)
            audit_event("create_finished_product", "finished_product", product_id, source="api", after=product)
            return _api_success(product, status=201)
        where: list[str] = []
        params: list[Any] = []
        _append_text_search(where, params, "name", "default_unit")
        query = "SELECT *, 'finished' AS item_type FROM finished_products"
        if where:
            query += " WHERE " + " AND ".join(where)
        query += " ORDER BY name"
        rows, meta = _query_list(query, tuple(params))
        return _api_success(rows, meta)

    @_api_token_required(PERMISSION_CATALOG_READ)
    def api_finished_product_detail(product_id: int):
        product = _finished_product_payload(product_id)
        if not product:
            return _api_error("not_found", "Produit fini introuvable.", 404)
        if request.method == "PUT":
            if not has_permission(g.user, PERMISSION_CATALOG_WRITE):
                return _api_error("forbidden", "Permission refusee.", 403)
            payload = _json_payload()
            before = dict(product)
            execute_db(
                "UPDATE finished_products SET name = ?, default_unit = ?, stock_qty = ?, sale_price = ?, avg_cost = ? WHERE id = ?",
                (
                    payload.get("name", product["name"]),
                    payload.get("default_unit", product["default_unit"]),
                    float(payload.get("stock_qty", product["stock_qty"]) or 0),
                    float(payload.get("sale_price", product["sale_price"]) or 0),
                    float(payload.get("avg_cost", product["avg_cost"]) or 0),
                    product_id,
                ),
            )
            product = _finished_product_payload(product_id)
            audit_event("update_finished_product", "finished_product", product_id, source="api", before=before, after=product)
        elif request.method == "DELETE":
            if not has_permission(g.user, PERMISSION_CATALOG_DELETE):
                return _api_error("forbidden", "Permission refusee.", 403)
            before = dict(product)
            execute_db("DELETE FROM finished_products WHERE id = ?", (product_id,))
            audit_event("delete_finished_product", "finished_product", product_id, source="api", before=before, after=None)
            return _api_success({"deleted": True})
        return _api_success(product)

    @_api_token_required(PERMISSION_OPERATIONS_READ)
    def api_purchases():
        if request.method == "POST":
            if not has_permission(g.user, PERMISSION_OPERATIONS_WRITE):
                return _api_error("forbidden", "Permission refusee.", 403)
            created = create_purchase_from_form(_form_payload_from_json(_json_payload()))
            if created["mode"] == "line":
                payload = {"mode": "line", "purchase": _purchase_payload(int(created["print_item_id"]))}
            else:
                payload = {
                    "mode": "document",
                    "document_id": int(created["document_id"]),
                    "line_count": int(created["line_count"]),
                    "print_doc_type": created["print_doc_type"],
                    "print_item_id": int(created["print_item_id"]),
                }
            return _api_success(payload, status=201)
        where: list[str] = []
        params: list[Any] = []
        _append_text_search(where, params, "COALESCE(s.name, '')", "COALESCE(NULLIF(p.custom_item_name, ''), r.name)", "p.notes")
        _append_date_range(where, params, "p.purchase_date")
        query = """
            SELECT p.*, COALESCE(s.name, 'Sans fournisseur') AS supplier_name, COALESCE(NULLIF(p.custom_item_name, ''), r.name) AS material_name, r.unit AS material_unit
            FROM purchases p
            LEFT JOIN suppliers s ON s.id = p.supplier_id
            JOIN raw_materials r ON r.id = p.raw_material_id
        """
        if where:
            query += " WHERE " + " AND ".join(where)
        query += " ORDER BY p.purchase_date DESC, p.id DESC"
        rows, meta = _query_list(query, tuple(params))
        return _api_success(rows, meta)

    @_api_token_required(PERMISSION_OPERATIONS_READ)
    def api_purchase_detail(purchase_id: int):
        purchase = _purchase_payload(purchase_id)
        if not purchase:
            return _api_error("not_found", "Achat introuvable.", 404)
        if request.method == "PUT":
            if not has_permission(g.user, PERMISSION_OPERATIONS_WRITE):
                return _api_error("forbidden", "Permission refusee.", 403)
            if purchase.get("document_id"):
                return _api_error(
                    "document_edit_required",
                    "Cette ligne appartient deja a un bon multi-lignes.",
                    409,
                    {"document_id": int(purchase["document_id"])},
                )
            try:
                result = edit_purchase_from_form(purchase_id, _form_payload_from_json(_json_payload()))
            except ValueError as exc:
                return _api_error("purchase_update_invalid", str(exc), 400)
            if result["mode"] == "document":
                return _api_success(
                    {
                        "mode": "document",
                        "document_id": int(result["document_id"]),
                        "document": _purchase_document_payload(int(result["document_id"])),
                    }
                )
            purchase = _purchase_payload(int(result["print_item_id"]))
        elif request.method == "DELETE":
            if not has_permission(g.user, PERMISSION_OPERATIONS_DELETE):
                return _api_error("forbidden", "Permission refusee.", 403)
            ok = delete_purchase_by_id(purchase_id)
            if not ok:
                return _api_error("conflict", "Suppression impossible.", 409)
            return _api_success({"deleted": True})
        return _api_success(purchase)

    @_api_token_required(PERMISSION_OPERATIONS_READ)
    def api_purchase_document_detail(document_id: int):
        document = _purchase_document_payload(document_id)
        if not document:
            return _api_error("not_found", "Bon d'achat introuvable.", 404)
        if request.method == "PUT":
            if not has_permission(g.user, PERMISSION_OPERATIONS_WRITE):
                return _api_error("forbidden", "Permission refusee.", 403)
            try:
                edit_purchase_document_from_form(document_id, _form_payload_from_json(_json_payload()))
            except ValueError as exc:
                return _api_error("purchase_document_invalid", str(exc), 400)
            document = _purchase_document_payload(document_id)
        return _api_success(document)

    @_api_token_required(PERMISSION_OPERATIONS_READ)
    def api_sales():
        if request.method == "POST":
            if not has_permission(g.user, PERMISSION_OPERATIONS_WRITE):
                return _api_error("forbidden", "Permission refusee.", 403)
            created = create_sale_from_form(_form_payload_from_json(_json_payload()))
            if created["mode"] == "line":
                payload = {
                    "mode": "line",
                    "kind": created["first_line_kind"],
                    "sale": _sale_payload(created["first_line_kind"], int(created["first_line_id"])),
                }
            else:
                payload = {
                    "mode": "document",
                    "document_id": int(created["document_id"]),
                    "line_count": int(created["line_count"]),
                    "print_doc_type": created["print_doc_type"],
                    "print_item_id": int(created["print_item_id"]),
                }
            return _api_success(payload, status=201)
        where: list[str] = []
        params: list[Any] = []
        _append_text_search(where, params, "client_name", "item_name", "notes")
        _append_date_range(where, params, "sale_date")
        kind_filter = str(request.args.get("kind", "") or "").strip().lower()
        status = str(request.args.get("status", "") or "").strip().lower()
        if kind_filter in {"finished", "raw"}:
            where.append("row_kind = ?")
            params.append(kind_filter)
        if status == "paid":
            where.append("balance_due <= 0")
        elif status == "due":
            where.append("balance_due > 0")
        elif status in {"cash", "credit"}:
            where.append("sale_type = ?")
            params.append(status)
        query = """
            SELECT * FROM (
                SELECT s.id, s.sale_date, COALESCE(c.name, 'Comptoir') AS client_name, f.name AS item_name,
                       s.document_id, s.quantity, s.unit, s.total, s.amount_paid, s.balance_due, s.profit_amount, s.sale_type, s.notes,
                       'Produit fini' AS item_kind, 'finished' AS row_kind
                FROM sales s
                LEFT JOIN clients c ON c.id = s.client_id
                JOIN finished_products f ON f.id = s.finished_product_id
                UNION ALL
                SELECT rs.id, rs.sale_date, COALESCE(c.name, 'Comptoir') AS client_name, COALESCE(NULLIF(rs.custom_item_name, ''), r.name) AS item_name,
                       rs.document_id, rs.quantity, rs.unit, rs.total, rs.amount_paid, rs.balance_due, rs.profit_amount, rs.sale_type, rs.notes,
                       'Matiere premiere' AS item_kind, 'raw' AS row_kind
                FROM raw_sales rs
                LEFT JOIN clients c ON c.id = rs.client_id
                JOIN raw_materials r ON r.id = rs.raw_material_id
            ) x
        """
        if where:
            query += " WHERE " + " AND ".join(where)
        query += " ORDER BY sale_date DESC, id DESC"
        rows, meta = _query_list(query, tuple(params))
        return _api_success(rows, meta)

    @_api_token_required(PERMISSION_OPERATIONS_READ)
    def api_sale_detail(kind: str, row_id: int):
        sale = _sale_payload(kind, row_id)
        if not sale:
            return _api_error("not_found", "Vente introuvable.", 404)
        if request.method == "PUT":
            if not has_permission(g.user, PERMISSION_OPERATIONS_WRITE):
                return _api_error("forbidden", "Permission refusee.", 403)
            if sale.get("document_id"):
                return _api_error(
                    "document_edit_required",
                    "Cette ligne appartient deja a une facture multi-lignes.",
                    409,
                    {"document_id": int(sale["document_id"])},
                )
            try:
                result = edit_sale_from_form(kind, row_id, _form_payload_from_json(_json_payload()))
            except ValueError as exc:
                if "versements" in str(exc).lower():
                    return _api_error("document_has_payments", str(exc), 409)
                return _api_error("sale_update_invalid", str(exc), 400)
            if result["mode"] == "document":
                return _api_success(
                    {
                        "mode": "document",
                        "document_id": int(result["document_id"]),
                        "document": _sale_document_payload(int(result["document_id"])),
                    }
                )
            sale = _sale_payload(result["first_line_kind"], int(result["first_line_id"])) or sale
        elif request.method == "DELETE":
            if not has_permission(g.user, PERMISSION_OPERATIONS_DELETE):
                return _api_error("forbidden", "Permission refusee.", 403)
            ok = delete_sale_by_id(kind, row_id)
            if not ok:
                return _api_error("conflict", "Suppression impossible.", 409)
            return _api_success({"deleted": True})
        return _api_success(sale)

    @_api_token_required(PERMISSION_OPERATIONS_READ)
    def api_sale_document_detail(document_id: int):
        document = _sale_document_payload(document_id)
        if not document:
            return _api_error("not_found", "Facture introuvable.", 404)
        if request.method == "PUT":
            if not has_permission(g.user, PERMISSION_OPERATIONS_WRITE):
                return _api_error("forbidden", "Permission refusee.", 403)
            try:
                edit_sale_document_from_form(document_id, _form_payload_from_json(_json_payload()))
            except ValueError as exc:
                if "versements" in str(exc).lower():
                    return _api_error("document_has_payments", str(exc), 409, {"document_id": document_id})
                return _api_error("sale_document_invalid", str(exc), 400)
            document = _sale_document_payload(document_id)
        return _api_success(document)

    @_api_token_required(PERMISSION_OPERATIONS_READ)
    def api_payments():
        if request.method == "POST":
            if not has_permission(g.user, PERMISSION_OPERATIONS_WRITE):
                return _api_error("forbidden", "Permission refusee.", 403)
            payment_id, payment_type = create_payment_from_form(_json_payload())
            return _api_success({"payment_type": payment_type, "payment": _payment_payload(payment_id)}, status=201)
        where: list[str] = []
        params: list[Any] = []
        _append_text_search(where, params, "c.name", "p.notes")
        _append_date_range(where, params, "p.payment_date")
        kind_filter = str(request.args.get("kind", "") or "").strip().lower()
        if kind_filter in {"versement", "avance"}:
            where.append("p.payment_type = ?")
            params.append(kind_filter)
        query = """
            SELECT p.*, c.name AS client_name,
                   CASE
                       WHEN p.sale_kind = 'finished' AND p.sale_id IS NOT NULL THEN 'Produit #' || p.sale_id
                       WHEN p.sale_kind = 'raw' AND p.raw_sale_id IS NOT NULL THEN 'Matiere #' || p.raw_sale_id
                       ELSE '-'
                   END AS sale_ref
            FROM payments p
            JOIN clients c ON c.id = p.client_id
        """
        if where:
            query += " WHERE " + " AND ".join(where)
        query += " ORDER BY p.payment_date DESC, p.id DESC"
        rows, meta = _query_list(query, tuple(params))
        return _api_success(rows, meta)

    @_api_token_required(PERMISSION_OPERATIONS_READ)
    def api_payment_detail(payment_id: int):
        payment = _payment_payload(payment_id)
        if not payment:
            return _api_error("not_found", "Paiement introuvable.", 404)
        if request.method == "PUT":
            if not has_permission(g.user, PERMISSION_OPERATIONS_WRITE):
                return _api_error("forbidden", "Permission refusee.", 403)
            new_payment_id = edit_payment_from_form(payment_id, _json_payload())
            payment = _payment_payload(int(new_payment_id))
        elif request.method == "DELETE":
            if not has_permission(g.user, PERMISSION_OPERATIONS_DELETE):
                return _api_error("forbidden", "Permission refusee.", 403)
            ok = delete_payment_by_id(payment_id)
            if not ok:
                return _api_error("conflict", "Suppression impossible.", 409)
            return _api_success({"deleted": True})
        return _api_success(payment)

    @_api_token_required(PERMISSION_PRODUCTION_READ)
    def api_production_batches():
        if request.method == "POST":
            if not has_permission(g.user, PERMISSION_PRODUCTION_WRITE):
                return _api_error("forbidden", "Permission refusee.", 403)
            payload = _json_payload()
            form_payload = _form_payload_from_json(
                {
                    "finished_product_id": payload.get("finished_product_id"),
                    "output_quantity": payload.get("output_quantity"),
                    "production_date": payload.get("production_date"),
                    "notes": payload.get("notes", ""),
                    "recipe_name": payload.get("recipe_name", ""),
                    "save_recipe": payload.get("save_recipe", 0),
                    "raw_material_id[]": payload.get("raw_material_id[]", payload.get("raw_material_ids", [])),
                    "quantity[]": payload.get("quantity[]", payload.get("quantities", [])),
                }
            )
            result = create_production_from_form(form_payload)
            return _api_success({"batch": _production_payload(result["batch_id"]), "recipe_id": result["recipe_id"]}, status=201)
        where: list[str] = []
        params: list[Any] = []
        _append_text_search(where, params, "fp.name", "pb.notes")
        _append_date_range(where, params, "pb.production_date")
        query = """
            SELECT pb.*, fp.name AS product_name, fp.default_unit AS product_unit
            FROM production_batches pb
            JOIN finished_products fp ON fp.id = pb.finished_product_id
        """
        if where:
            query += " WHERE " + " AND ".join(where)
        query += " ORDER BY pb.production_date DESC, pb.id DESC"
        rows, meta = _query_list(query, tuple(params))
        return _api_success(rows, meta)

    @_api_token_required(PERMISSION_PRODUCTION_READ)
    def api_production_batch_detail(batch_id: int):
        batch = _production_payload(batch_id)
        if not batch:
            return _api_error("not_found", "Production introuvable.", 404)
        if request.method == "DELETE":
            if not has_permission(g.user, PERMISSION_PRODUCTION_DELETE):
                return _api_error("forbidden", "Permission refusee.", 403)
            ok = delete_production_by_id(batch_id)
            if not ok:
                return _api_error("conflict", "Suppression impossible.", 409)
            return _api_success({"deleted": True})
        items = query_db("SELECT * FROM production_batch_items WHERE batch_id = ? ORDER BY id", (batch_id,))
        payload = dict(batch)
        payload["items"] = [dict(item) for item in items]
        return _api_success(payload)

    @_api_token_required(PERMISSION_PRODUCTION_READ)
    def api_recipes():
        rows, meta = _query_list(
            """
            SELECT sr.*, fp.name AS finished_product_name
            FROM saved_recipes sr
            JOIN finished_products fp ON fp.id = sr.finished_product_id
            ORDER BY sr.id DESC
            """
        )
        return _api_success(rows, meta)

    @_api_token_required(PERMISSION_PRODUCTION_READ)
    def api_recipe_detail(recipe_id: int):
        row = query_db("SELECT * FROM saved_recipes WHERE id = ?", (recipe_id,), one=True)
        if not row:
            return _api_error("not_found", "Recette introuvable.", 404)
        items = query_db("SELECT * FROM saved_recipe_items WHERE recipe_id = ? ORDER BY position, id", (recipe_id,))
        payload = dict(row)
        payload["items"] = [dict(item) for item in items]
        return _api_success(payload)

    @_api_token_required(PERMISSION_CATALOG_READ)
    def api_sellable_items():
        items = [dict(item) for item in build_sellable_items()]
        term = str(request.args.get("q", "") or "").strip().lower()
        kind_filter = str(request.args.get("kind", "") or "").strip().lower()
        if term:
            items = [item for item in items if term in str(item.get("label", "")).lower() or term in str(item.get("key", "")).lower()]
        if kind_filter in {"finished", "raw"}:
            items = [item for item in items if str(item.get("key", "")).startswith(f"{kind_filter}:")]
        return _api_success(items, {"returned": len(items)})

    @_api_token_required(PERMISSION_OPERATIONS_READ)
    def api_recent_operations():
        where: list[str] = []
        params: list[Any] = []
        _append_text_search(where, params, "partner_name", "item_name", "notes", "operation_label")
        _append_date_range(where, params, "event_date")
        kind_filter = str(request.args.get("kind", "") or "").strip().lower()
        if kind_filter in {"sale", "payment", "purchase", "production"}:
            where.append("operation_type = ?")
            params.append(kind_filter)
        query = """
            SELECT * FROM (
                SELECT 'sale' AS operation_type, s.id AS row_id, s.sale_date AS event_date,
                       COALESCE(c.name, 'Comptoir') AS partner_name, f.name AS item_name, s.notes,
                       s.total AS amount, s.balance_due AS balance_due, 'Vente produit final' AS operation_label
                FROM sales s
                LEFT JOIN clients c ON c.id = s.client_id
                JOIN finished_products f ON f.id = s.finished_product_id
                UNION ALL
                SELECT 'sale' AS operation_type, rs.id AS row_id, rs.sale_date AS event_date,
                       COALESCE(c.name, 'Comptoir') AS partner_name, COALESCE(NULLIF(rs.custom_item_name, ''), r.name) AS item_name, rs.notes,
                       rs.total AS amount, rs.balance_due AS balance_due, 'Vente matiere premiere' AS operation_label
                FROM raw_sales rs
                LEFT JOIN clients c ON c.id = rs.client_id
                JOIN raw_materials r ON r.id = rs.raw_material_id
                UNION ALL
                SELECT 'payment' AS operation_type, p.id AS row_id, p.payment_date AS event_date,
                       c.name AS partner_name,
                       CASE WHEN p.payment_type = 'avance' THEN 'Avance client' ELSE 'Versement client' END AS item_name,
                       p.notes, p.amount AS amount, 0 AS balance_due,
                       CASE WHEN p.payment_type = 'avance' THEN 'Avance' ELSE 'Versement' END AS operation_label
                FROM payments p
                JOIN clients c ON c.id = p.client_id
                UNION ALL
                SELECT 'purchase' AS operation_type, p.id AS row_id, p.purchase_date AS event_date,
                       COALESCE(s.name, 'Sans fournisseur') AS partner_name, COALESCE(NULLIF(p.custom_item_name, ''), r.name) AS item_name, p.notes,
                       p.total AS amount, 0 AS balance_due, 'Achat' AS operation_label
                FROM purchases p
                LEFT JOIN suppliers s ON s.id = p.supplier_id
                JOIN raw_materials r ON r.id = p.raw_material_id
                UNION ALL
                SELECT 'production' AS operation_type, pb.id AS row_id, pb.production_date AS event_date,
                       '' AS partner_name, fp.name AS item_name, pb.notes,
                       pb.production_cost AS amount, 0 AS balance_due, 'Production' AS operation_label
                FROM production_batches pb
                JOIN finished_products fp ON fp.id = pb.finished_product_id
            ) x
        """
        if where:
            query += " WHERE " + " AND ".join(where)
        query += " ORDER BY event_date DESC, row_id DESC"
        rows, meta = _query_list(query, tuple(params))
        return _api_success(rows, meta)

    @_api_token_required(PERMISSION_AUDIT_READ)
    def api_audit_logs():
        rows, meta = _query_list("SELECT * FROM audit_logs ORDER BY id DESC")
        return _api_success(rows, meta)

    bind_route(app, "/api/v1/ping", "api_v1_ping", api_ping, ["GET"])
    bind_route(app, "/api/v1/auth/login", "api_v1_auth_login", api_auth_login, ["POST"])
    bind_route(app, "/api/v1/auth/refresh", "api_v1_auth_refresh", api_auth_refresh, ["POST"])
    bind_route(app, "/api/v1/auth/logout", "api_v1_auth_logout", api_auth_logout, ["POST"])
    bind_route(app, "/api/v1/auth/me", "api_v1_auth_me", api_auth_me, ["GET"])
    bind_route(app, "/api/v1/dashboard/summary", "api_v1_dashboard_summary", api_dashboard_summary, ["GET"])
    bind_route(app, "/api/v1/clients", "api_v1_clients", api_clients, ["GET", "POST"])
    bind_route(app, "/api/v1/clients/<int:client_id>", "api_v1_client_detail", api_client_detail, ["GET", "PUT"])
    bind_route(app, "/api/v1/clients/<int:client_id>/history", "api_v1_client_history", api_client_history, ["GET"])
    bind_route(app, "/api/v1/suppliers", "api_v1_suppliers", api_suppliers, ["GET", "POST"])
    bind_route(app, "/api/v1/suppliers/<int:supplier_id>", "api_v1_supplier_detail", api_supplier_detail, ["GET", "PUT", "DELETE"])
    bind_route(app, "/api/v1/raw-materials", "api_v1_raw_materials", api_raw_materials, ["GET", "POST"])
    bind_route(app, "/api/v1/raw-materials/<int:material_id>", "api_v1_raw_material_detail", api_raw_material_detail, ["GET", "PUT", "DELETE"])
    bind_route(app, "/api/v1/finished-products", "api_v1_finished_products", api_finished_products, ["GET", "POST"])
    bind_route(app, "/api/v1/finished-products/<int:product_id>", "api_v1_finished_product_detail", api_finished_product_detail, ["GET", "PUT", "DELETE"])
    bind_route(app, "/api/v1/sellable-items", "api_v1_sellable_items", api_sellable_items, ["GET"])
    bind_route(app, "/api/v1/purchases", "api_v1_purchases", api_purchases, ["GET", "POST"])
    bind_route(app, "/api/v1/purchases/<int:purchase_id>", "api_v1_purchase_detail", api_purchase_detail, ["GET", "PUT", "DELETE"])
    bind_route(app, "/api/v1/purchase-documents/<int:document_id>", "api_v1_purchase_document_detail", api_purchase_document_detail, ["GET", "PUT"])
    bind_route(app, "/api/v1/sales", "api_v1_sales", api_sales, ["GET", "POST"])
    bind_route(app, "/api/v1/sales/<kind>/<int:row_id>", "api_v1_sale_detail", api_sale_detail, ["GET", "PUT", "DELETE"])
    bind_route(app, "/api/v1/sale-documents/<int:document_id>", "api_v1_sale_document_detail", api_sale_document_detail, ["GET", "PUT"])
    bind_route(app, "/api/v1/payments", "api_v1_payments", api_payments, ["GET", "POST"])
    bind_route(app, "/api/v1/payments/<int:payment_id>", "api_v1_payment_detail", api_payment_detail, ["GET", "PUT", "DELETE"])
    bind_route(app, "/api/v1/recent-operations", "api_v1_recent_operations", api_recent_operations, ["GET"])
    bind_route(app, "/api/v1/production-batches", "api_v1_production_batches", api_production_batches, ["GET", "POST"])
    bind_route(app, "/api/v1/production-batches/<int:batch_id>", "api_v1_production_batch_detail", api_production_batch_detail, ["GET", "DELETE"])
    bind_route(app, "/api/v1/recipes", "api_v1_recipes", api_recipes, ["GET"])
    bind_route(app, "/api/v1/recipes/<int:recipe_id>", "api_v1_recipe_detail", api_recipe_detail, ["GET"])
    bind_route(app, "/api/v1/audit-logs", "api_v1_audit_logs", api_audit_logs, ["GET"])
