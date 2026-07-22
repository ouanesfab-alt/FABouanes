from __future__ import annotations

import threading
from collections.abc import Callable
from functools import wraps

from fastapi.responses import JSONResponse, RedirectResponse

from app.core.request_state import get_state_value

ROLE_ADMIN = "admin"
ROLE_MANAGER = "manager"
ROLE_OPERATOR = "operator"

PERMISSION_DASHBOARD_READ = "dashboard.read"
PERMISSION_CONTACTS_READ = "contacts.read"
PERMISSION_CONTACTS_WRITE = "contacts.write"
PERMISSION_CONTACTS_DELETE = "contacts.delete"
PERMISSION_CATALOG_READ = "catalog.read"
PERMISSION_CATALOG_WRITE = "catalog.write"
PERMISSION_CATALOG_DELETE = "catalog.delete"
PERMISSION_OPERATIONS_READ = "operations.read"
PERMISSION_OPERATIONS_WRITE = "operations.write"
PERMISSION_OPERATIONS_DELETE = "operations.delete"
PERMISSION_PRODUCTION_READ = "production.read"
PERMISSION_PRODUCTION_WRITE = "production.write"
PERMISSION_PRODUCTION_DELETE = "production.delete"
PERMISSION_AUDIT_READ = "audit.read"
PERMISSION_USERS_MANAGE = "users.manage"
PERMISSION_SETTINGS_MANAGE = "settings.manage"
PERMISSION_BACKUP_RESTORE = "backup.restore"
PERMISSION_TOOLS_READ = "tools.read"
PERMISSION_API_ACCESS = "api.access"

ALL_PERMISSIONS = {
    PERMISSION_DASHBOARD_READ,
    PERMISSION_CONTACTS_READ,
    PERMISSION_CONTACTS_WRITE,
    PERMISSION_CONTACTS_DELETE,
    PERMISSION_CATALOG_READ,
    PERMISSION_CATALOG_WRITE,
    PERMISSION_CATALOG_DELETE,
    PERMISSION_OPERATIONS_READ,
    PERMISSION_OPERATIONS_WRITE,
    PERMISSION_OPERATIONS_DELETE,
    PERMISSION_PRODUCTION_READ,
    PERMISSION_PRODUCTION_WRITE,
    PERMISSION_PRODUCTION_DELETE,
    PERMISSION_AUDIT_READ,
    PERMISSION_USERS_MANAGE,
    PERMISSION_SETTINGS_MANAGE,
    PERMISSION_BACKUP_RESTORE,
    PERMISSION_TOOLS_READ,
    PERMISSION_API_ACCESS,
}

MANAGER_PERMISSIONS = {
    PERMISSION_DASHBOARD_READ,
    PERMISSION_CONTACTS_READ,
    PERMISSION_CATALOG_READ,
    PERMISSION_OPERATIONS_READ,
    PERMISSION_PRODUCTION_READ,
    PERMISSION_AUDIT_READ,
    PERMISSION_TOOLS_READ,
    PERMISSION_API_ACCESS,
    PERMISSION_OPERATIONS_WRITE,
}

ROLE_PERMISSIONS = {
    ROLE_ADMIN: ALL_PERMISSIONS,
    ROLE_MANAGER: MANAGER_PERMISSIONS,
    ROLE_OPERATOR: {
        PERMISSION_DASHBOARD_READ,
        PERMISSION_CONTACTS_READ,
        PERMISSION_CONTACTS_WRITE,
        PERMISSION_CATALOG_READ,
        PERMISSION_OPERATIONS_READ,
        PERMISSION_OPERATIONS_WRITE,
        PERMISSION_PRODUCTION_READ,
        PERMISSION_PRODUCTION_WRITE,
        PERMISSION_TOOLS_READ,
        PERMISSION_API_ACCESS,
    },
}

PUBLIC_ENDPOINTS = {
    "login",
    "health",
    "static",
}

ENDPOINT_PERMISSIONS: dict[str, dict[str, str]] = {
    "index": {"*": PERMISSION_DASHBOARD_READ},
    "dashboard": {"*": PERMISSION_DASHBOARD_READ},
    "api_kpi_date": {"*": PERMISSION_DASHBOARD_READ},
    "api_kpi_at_date": {"*": PERMISSION_DASHBOARD_READ},
    "reports": {"*": PERMISSION_DASHBOARD_READ},
    "contacts": {"*": PERMISSION_CONTACTS_READ},
    "clients": {"GET": PERMISSION_CONTACTS_READ, "POST": PERMISSION_CONTACTS_WRITE},
    "new_client": {"GET": PERMISSION_CONTACTS_WRITE, "POST": PERMISSION_CONTACTS_WRITE},
    "import_clients_excel": {"GET": PERMISSION_CONTACTS_WRITE, "POST": PERMISSION_CONTACTS_WRITE},
    "client_detail": {"*": PERMISSION_CONTACTS_READ},
    "print_client_history": {"*": PERMISSION_CONTACTS_READ},
    "edit_client": {"GET": PERMISSION_CONTACTS_WRITE, "POST": PERMISSION_CONTACTS_WRITE},
    "delete_client": {"POST": PERMISSION_CONTACTS_DELETE},
    "suppliers": {"GET": PERMISSION_CONTACTS_READ, "POST": PERMISSION_CONTACTS_WRITE},
    "new_supplier": {"GET": PERMISSION_CONTACTS_WRITE, "POST": PERMISSION_CONTACTS_WRITE},
    "supplier_detail": {"*": PERMISSION_CONTACTS_READ},
    "edit_supplier": {"GET": PERMISSION_CONTACTS_WRITE, "POST": PERMISSION_CONTACTS_WRITE},
    "delete_supplier": {"POST": PERMISSION_CONTACTS_DELETE},
    "catalog": {"*": PERMISSION_CATALOG_READ},
    "raw_materials": {"*": PERMISSION_CATALOG_READ},
    "products": {"*": PERMISSION_CATALOG_READ},
    "finished_products": {"*": PERMISSION_CATALOG_READ},
    "quick_add": {"*": PERMISSION_TOOLS_READ},
    "new_catalog_item": {"GET": PERMISSION_CATALOG_WRITE, "POST": PERMISSION_CATALOG_WRITE},
    "edit_raw_material": {"GET": PERMISSION_CATALOG_WRITE, "POST": PERMISSION_CATALOG_WRITE},
    "edit_product": {"GET": PERMISSION_CATALOG_WRITE, "POST": PERMISSION_CATALOG_WRITE},
    "edit_finished_product": {"GET": PERMISSION_CATALOG_WRITE, "POST": PERMISSION_CATALOG_WRITE},
    "delete_raw_material": {"POST": PERMISSION_CATALOG_DELETE},
    "delete_product": {"POST": PERMISSION_CATALOG_DELETE},
    "delete_finished_product": {"POST": PERMISSION_CATALOG_DELETE},
    "operations": {"*": PERMISSION_OPERATIONS_READ},
    "transactions": {"*": PERMISSION_OPERATIONS_READ},
    "purchases": {"GET": PERMISSION_OPERATIONS_READ, "POST": PERMISSION_OPERATIONS_WRITE},
    "new_purchase": {"GET": PERMISSION_OPERATIONS_WRITE, "POST": PERMISSION_OPERATIONS_WRITE},
    "edit_purchase": {"GET": PERMISSION_OPERATIONS_WRITE, "POST": PERMISSION_OPERATIONS_WRITE},
    "edit_purchase_document": {"GET": PERMISSION_OPERATIONS_WRITE, "POST": PERMISSION_OPERATIONS_WRITE},
    "delete_purchase": {"POST": PERMISSION_OPERATIONS_DELETE},
    "sales": {"GET": PERMISSION_OPERATIONS_READ, "POST": PERMISSION_OPERATIONS_WRITE},
    "new_sale": {"GET": PERMISSION_OPERATIONS_WRITE, "POST": PERMISSION_OPERATIONS_WRITE},
    "edit_sale": {"GET": PERMISSION_OPERATIONS_WRITE, "POST": PERMISSION_OPERATIONS_WRITE},
    "edit_sale_document": {"GET": PERMISSION_OPERATIONS_WRITE, "POST": PERMISSION_OPERATIONS_WRITE},
    "delete_sale": {"POST": PERMISSION_OPERATIONS_DELETE},
    "payments": {"GET": PERMISSION_OPERATIONS_READ, "POST": PERMISSION_OPERATIONS_WRITE},
    "new_payment": {"GET": PERMISSION_OPERATIONS_WRITE, "POST": PERMISSION_OPERATIONS_WRITE},
    "edit_payment": {"GET": PERMISSION_OPERATIONS_WRITE, "POST": PERMISSION_OPERATIONS_WRITE},
    "delete_payment": {"POST": PERMISSION_OPERATIONS_DELETE},
    "production": {"GET": PERMISSION_PRODUCTION_READ, "POST": PERMISSION_PRODUCTION_WRITE},
    "new_production": {"GET": PERMISSION_PRODUCTION_WRITE, "POST": PERMISSION_PRODUCTION_WRITE},
    "delete_production": {"POST": PERMISSION_PRODUCTION_DELETE},
    "notes_page": {"*": PERMISSION_TOOLS_READ},
    "bons_space": {"*": PERMISSION_TOOLS_READ},
    "bons_pdf_file": {"*": PERMISSION_TOOLS_READ},
    "pdf_reader": {"*": PERMISSION_TOOLS_READ},
    "pdf_reader_file": {"*": PERMISSION_TOOLS_READ},
    "mobile_connect": {"*": PERMISSION_DASHBOARD_READ},
    "admin_panel": {"GET": PERMISSION_SETTINGS_MANAGE, "POST": PERMISSION_SETTINGS_MANAGE},
    "users": {"*": PERMISSION_USERS_MANAGE},
    "admin_audit_page": {"*": PERMISSION_AUDIT_READ},
    "admin_audit_export": {"*": PERMISSION_AUDIT_READ},
    "admin_system_status": {"*": PERMISSION_SETTINGS_MANAGE},
    "admin_system_status_export": {"*": PERMISSION_SETTINGS_MANAGE},
}


def normalize_role(role: str | None) -> str:
    raw = (role or ROLE_OPERATOR).strip().lower()
    if raw in ROLE_PERMISSIONS:
        return raw
    if raw == "user":
        return ROLE_OPERATOR
    return ROLE_OPERATOR


_dynamic_permissions_cache: dict[str, set[str]] | None = None
_dynamic_lock = threading.Lock()

def _get_dynamic_permissions(role: str) -> set[str]:
    global _dynamic_permissions_cache
    if _dynamic_permissions_cache is not None:
        return _dynamic_permissions_cache.get(role, set())

    with _dynamic_lock:
        if _dynamic_permissions_cache is not None:
            return _dynamic_permissions_cache.get(role, set())

        cache = {}
        try:
            from app.core.registry import get_enabled_modules
            for module in get_enabled_modules():
                if hasattr(module, "role_permissions") and module.role_permissions:
                    for r, perms in module.role_permissions.items():
                        norm_role = normalize_role(r)
                        if norm_role not in cache:
                            cache[norm_role] = set()
                        cache[norm_role].update(perms)
        except Exception:
            pass
        _dynamic_permissions_cache = cache
        return _dynamic_permissions_cache.get(role, set())


def has_permission(user, permission: str | None) -> bool:
    if permission is None:
        return True
    if not user:
        return False

    # Extract fine-grained custom permissions assigned directly to user
    custom_perms = []
    if isinstance(user, dict):
        custom_perms = user.get("custom_permissions") or []
        if not custom_perms and "custom_permissions_json" in user:
            try:
                import json
                custom_perms = json.loads(user["custom_permissions_json"] or "[]")
            except Exception:
                pass
    else:
        custom_perms = getattr(user, "custom_permissions_list", [])
        if not custom_perms:
            custom_json = getattr(user, "custom_permissions_json", "[]")
            try:
                import json
                custom_perms = json.loads(custom_json or "[]")
            except Exception:
                pass

    if permission in custom_perms:
        return True

    role = normalize_role(user.get("role") if isinstance(user, dict) else getattr(user, "role", None))

    # L'admin a le droit de tout faire, y compris sur les modules dynamiques
    if role == ROLE_ADMIN:
        return True

    if role == ROLE_MANAGER:
        if permission not in MANAGER_PERMISSIONS:
            return False
        if permission == PERMISSION_OPERATIONS_WRITE:
            state_request = get_state_value("request")
            if state_request:
                path = state_request.url.path.lower()
                if "purchase" in path or "achat" in path:
                    return False
                query_params = state_request.query_params
                if query_params.get("type") == "purchase" or query_params.get("mode") == "achat":
                    return False
        return True

    # Les autres rôles doivent avoir la permission explicite ou héritée
    if permission in ROLE_PERMISSIONS.get(role, set()):
        return True

    # Vérification des permissions dynamiques déclarées par les modules (cache O(1))
    if permission in _get_dynamic_permissions(role):
        return True

    return False


def permission_for_endpoint(endpoint: str | None, method: str | None = None) -> str | None:
    if not endpoint or endpoint in PUBLIC_ENDPOINTS:
        return None
    mapping = ENDPOINT_PERMISSIONS.get(endpoint)
    if not mapping:
        return None
    key = (method or "GET").upper()
    if key == "OPTIONS":
        return None
    return mapping.get(key) or mapping.get("*")


def _audit_permission_denied(permission: str | None) -> None:
    try:
        from app.core.audit import audit_event

        state_request = get_state_value("request")
        route = state_request.scope.get("route") if state_request else None
        endpoint = getattr(route, "name", "") if route else ""

        audit_event(
            action="permission_denied",
            entity_type="permission",
            entity_id=permission,
            status="failure",
            meta={
                "endpoint": endpoint,
                "method": state_request.method if state_request else "",
                "path": state_request.url.path if state_request else "",
                "permission": permission,
            },
        )
    except Exception:
        pass


def permission_denied_response(permission: str | None, login_endpoint: str = "login"):
    state_request = get_state_value("request")
    path = state_request.url.path if state_request is not None else ""
    if get_state_value("user") is None:
        if path.startswith("/api/"):
            return JSONResponse({"error": {"code": "unauthorized", "message": "Authentification requise.", "details": None}}, status_code=401)
        return RedirectResponse(f"/{login_endpoint}", status_code=303)
    _audit_permission_denied(permission)
    if path.startswith("/api/"):
        return JSONResponse({"error": {"code": "forbidden", "message": "Permission refusee.", "details": {"permission": permission}}}, status_code=403)
    if state_request is not None:
        from app.web.deps import flash

        flash(state_request, "Acces refuse pour cette action.", "danger")
    return RedirectResponse("/", status_code=303)


def require_permission(permission: str | None) -> Callable:
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = get_state_value("user")
            if user is None:
                return permission_denied_response(permission)
            if not has_permission(user, permission):
                return permission_denied_response(permission)
            return view(*args, **kwargs)

        return wrapped

    return decorator
