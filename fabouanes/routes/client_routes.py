from __future__ import annotations

from datetime import datetime

from flask import flash, redirect, render_template, request, url_for

from fabouanes.core.decorators import login_required
from fabouanes.repositories.client_repository import get_client
from fabouanes.routes.route_utils import bind_route
from fabouanes.services.client_service import (
    clients_context,
    create_client_from_form,
    get_client_detail_context,
    import_clients_from_files,
    update_client_from_form,
)


def register_client_routes(app):
    @login_required
    def clients():
        if request.method == "POST":
            create_client_from_form(request.form)
            flash("Client ajoute avec succes.", "success")
            return redirect(url_for("clients"))
        return render_template("clients.html", **clients_context())

    @login_required
    def new_client():
        if request.method == "POST":
            create_client_from_form(request.form)
            flash("Client ajoute avec succes.", "success")
            return redirect(url_for("clients"))
        return render_template("client_new.html")

    @login_required
    def import_clients_excel():
        if request.method == "POST":
            files = request.files.getlist("excel_files")
            if not files:
                flash("Ajoute au moins un fichier Excel.", "warning")
                return redirect(url_for("import_clients_excel"))
            result = import_clients_from_files(files)
            for err in result["errors"][:5]:
                flash(err, "danger")
            level = "success" if (result["created"] or result["updated"]) else "warning"
            flash(
                f"Import termine : {result['created']} client(s) crees, {result['updated']} mis a jour avec dernier solde.",
                level,
            )
            return redirect(url_for("clients"))
        return render_template("client_import.html")

    @login_required
    def client_detail(client_id: int):
        context = get_client_detail_context(client_id)
        if not context:
            flash("Client introuvable.", "danger")
            return redirect(url_for("clients"))
        return render_template("client_detail.html", **context)

    @login_required
    def print_client_history(client_id: int):
        context = get_client_detail_context(client_id)
        if not context:
            flash("Client introuvable.", "danger")
            return redirect(url_for("clients"))
        printed_at = datetime.now()
        return render_template(
            "client_history_print.html",
            printed_date=printed_at.strftime("%Y-%m-%d"),
            printed_time=printed_at.strftime("%H:%M"),
            **context,
        )

    @login_required
    def edit_client(client_id: int):
        client = get_client(client_id)
        if not client:
            flash("Client introuvable.", "danger")
            return redirect(url_for("clients"))
        if request.method == "POST":
            update_client_from_form(client_id, request.form)
            flash("Client modifie avec succes.", "success")
            return redirect(url_for("client_detail", client_id=client_id))
        return render_template("client_edit.html", client=client)

    bind_route(app, "/clients", "clients", clients, ["GET", "POST"])
    bind_route(app, "/clients/new", "new_client", new_client, ["GET", "POST"])
    bind_route(app, "/clients/import-excel", "import_clients_excel", import_clients_excel, ["GET", "POST"])
    bind_route(app, "/clients/<int:client_id>", "client_detail", client_detail, ["GET"])
    bind_route(app, "/clients/<int:client_id>/print-history", "print_client_history", print_client_history, ["GET"])
    bind_route(app, "/clients/<int:client_id>/edit", "edit_client", edit_client, ["GET", "POST"])
