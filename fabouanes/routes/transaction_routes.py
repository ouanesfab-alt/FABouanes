from __future__ import annotations

from flask import render_template, request

from fabouanes.core.decorators import login_required
from fabouanes.repositories.transaction_repository import list_transactions_context
from fabouanes.routes.route_utils import bind_route


def register_transaction_routes(app):
    @login_required
    def transactions():
        return render_template("transactions.html", **list_transactions_context(request.args))

    bind_route(app, "/operations", "operations", transactions, ["GET"])
    bind_route(app, "/transactions", "transactions", transactions, ["GET"])
