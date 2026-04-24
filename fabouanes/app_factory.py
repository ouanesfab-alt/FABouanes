from __future__ import annotations

from fabouanes.runtime_app import app as runtime_app, ensure_runtime_dirs, init_db
from fabouanes.routes.admin_routes import register_admin_routes
from fabouanes.routes.api_v1_routes import register_api_v1_routes
from fabouanes.routes.auth_routes import register_auth_routes
from fabouanes.routes.catalog_routes import register_catalog_routes
from fabouanes.routes.contact_routes import register_contact_routes
from fabouanes.routes.client_routes import register_client_routes
from fabouanes.routes.core_routes import register_core_routes
from fabouanes.routes.payment_routes import register_payment_routes
from fabouanes.routes.print_routes import register_print_routes
from fabouanes.routes.production_routes import register_production_routes
from fabouanes.routes.purchase_routes import register_purchase_routes
from fabouanes.routes.sale_routes import register_sale_routes
from fabouanes.routes.tools_routes import register_tools_routes
from fabouanes.routes.transaction_routes import register_transaction_routes


def create_app():
    if not runtime_app.config.get("_FAB_BOOTSTRAPPED"):
        ensure_runtime_dirs()
        init_db()
        runtime_app.reset_routes({"static"})
        for registrar in (
            register_auth_routes,
            register_core_routes,
            register_admin_routes,
            register_api_v1_routes,
            register_client_routes,
            register_contact_routes,
            register_catalog_routes,
            register_purchase_routes,
            register_sale_routes,
            register_payment_routes,
            register_production_routes,
            register_transaction_routes,
            register_tools_routes,
            register_print_routes,
        ):
            registrar(runtime_app)
        runtime_app.config["_FAB_BOOTSTRAPPED"] = True
    return runtime_app
