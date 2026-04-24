from __future__ import annotations

from fabouanes.fastapi_compat import flash, redirect, render_template, request, url_for

from fabouanes.core.db_access import query_db
from fabouanes.core.decorators import login_required
from fabouanes.core.helpers import wants_print_after_submit
from fabouanes.core.pagination import request_pagination
from fabouanes.routes.route_utils import bind_route, flash_route_exception
from fabouanes.services.sale_service import (
    create_sale_from_form,
    delete_sale_by_id,
    edit_sale_document_from_form,
    edit_sale_from_form,
    get_sale_document_context,
    get_sale_edit_context,
    sale_form_context,
    sales_context,
)


def register_sale_routes(app):
    @login_required
    def sales():
        if request.method == "POST":
            try:
                created = create_sale_from_form(request.form)
                flash("Vente enregistree avec benefice estime.", "success")
                if wants_print_after_submit():
                    return redirect(url_for("print_document", doc_type=created["print_doc_type"], item_id=created["print_item_id"]))
                return redirect(url_for("sales"))
            except Exception as exc:
                flash_route_exception(exc)
                return redirect(url_for("sales"))
        page, page_size = request_pagination()
        return render_template("sales.html", **sales_context(page=page, page_size=page_size))

    @login_required
    def new_sale():
        if request.method == "POST":
            try:
                created = create_sale_from_form(request.form)
                flash("Vente enregistree avec benefice estime.", "success")
                if wants_print_after_submit():
                    return redirect(url_for("print_document", doc_type=created["print_doc_type"], item_id=created["print_item_id"]))
                return redirect(url_for("sales"))
            except Exception as exc:
                flash_route_exception(exc)
                return redirect(url_for("new_sale"))
        context = sale_form_context()
        context["clients"] = query_db("SELECT * FROM clients ORDER BY name")
        return render_template("sale_new.html", **context)

    @login_required
    def edit_sale(kind: str, row_id: int):
        context = get_sale_edit_context(kind, row_id)
        if not context:
            flash("Vente introuvable.", "danger")
            return redirect(url_for("transactions", type="sale"))
        if context.get("redirect_document_id"):
            return redirect(url_for("edit_sale_document", document_id=context["redirect_document_id"]))
        if request.method == "POST":
            try:
                edit_sale_from_form(kind, row_id, request.form)
                flash("Vente modifiee.", "success")
                return redirect(url_for("transactions", type="sale"))
            except Exception as exc:
                flash_route_exception(exc)
                return redirect(request.url)
        form_context = sale_form_context()
        form_context.update(context)
        form_context["clients"] = query_db("SELECT * FROM clients ORDER BY name")
        return render_template("sale_edit.html", **form_context)

    @login_required
    def edit_sale_document(document_id: int):
        context = get_sale_document_context(document_id)
        if not context:
            flash("Facture introuvable.", "danger")
            return redirect(url_for("transactions", type="sale"))
        if request.method == "POST":
            try:
                edit_sale_document_from_form(document_id, request.form)
                flash("Facture modifiee.", "success")
                return redirect(url_for("transactions", type="sale"))
            except Exception as exc:
                flash_route_exception(exc)
                return redirect(request.url)
        form_context = sale_form_context()
        form_context.update(context)
        form_context["clients"] = query_db("SELECT * FROM clients ORDER BY name")
        return render_template("sale_edit.html", **form_context)

    @login_required
    def delete_sale(kind: str, row_id: int):
        if delete_sale_by_id(kind, row_id):
            flash("Vente supprimee et stock corrige.", "success")
        else:
            flash("Vente introuvable.", "danger")
        return redirect(url_for("sales"))

    bind_route(app, "/sales", "sales", sales, ["GET", "POST"])
    bind_route(app, "/sales/new", "new_sale", new_sale, ["GET", "POST"])
    bind_route(app, "/sales/document/<int:document_id>/edit", "edit_sale_document", edit_sale_document, ["GET", "POST"])
    bind_route(app, "/sales/<kind>/<int:row_id>/edit", "edit_sale", edit_sale, ["GET", "POST"])
    bind_route(app, "/sales/<kind>/<int:row_id>/delete", "delete_sale", delete_sale, ["POST"])
