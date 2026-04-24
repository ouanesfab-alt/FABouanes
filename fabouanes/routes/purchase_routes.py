from __future__ import annotations

from fabouanes.fastapi_compat import flash, redirect, render_template, request, url_for

from fabouanes.core.decorators import login_required
from fabouanes.core.helpers import wants_print_after_submit
from fabouanes.core.pagination import request_pagination
from fabouanes.routes.route_utils import bind_route, flash_route_exception
from fabouanes.services.purchase_service import (
    create_purchase_from_form,
    delete_purchase_by_id,
    edit_purchase_document_from_form,
    edit_purchase_from_form,
    get_purchase_document_context,
    get_purchase_edit_context,
    purchase_form_context,
    purchases_context,
)


def register_purchase_routes(app):
    @login_required
    def purchases():
        if request.method == "POST":
            try:
                create_purchase_from_form(request.form)
                flash("Achat enregistre et stock mis a jour.", "success")
                return redirect(url_for("purchases"))
            except Exception as exc:
                flash_route_exception(exc)
                return redirect(url_for("purchases"))
        page, page_size = request_pagination()
        return render_template("purchases.html", **purchases_context(page=page, page_size=page_size))

    @login_required
    def new_purchase():
        if request.method == "POST":
            try:
                created = create_purchase_from_form(request.form)
                flash("Achat enregistre avec succes.", "success")
                if wants_print_after_submit():
                    return redirect(url_for("print_document", doc_type=created["print_doc_type"], item_id=created["print_item_id"]))
                return redirect(url_for("purchases"))
            except Exception as exc:
                flash_route_exception(exc)
                return redirect(url_for("new_purchase"))
        return render_template("purchase_new.html", **purchase_form_context())

    @login_required
    def edit_purchase(purchase_id: int):
        context = get_purchase_edit_context(purchase_id)
        if not context:
            flash("Achat introuvable.", "danger")
            return redirect(url_for("transactions", type="purchase"))
        if context.get("redirect_document_id"):
            return redirect(url_for("edit_purchase_document", document_id=context["redirect_document_id"]))
        if request.method == "POST":
            try:
                edit_purchase_from_form(purchase_id, request.form)
                flash("Achat modifie.", "success")
                return redirect(url_for("transactions", type="purchase"))
            except Exception as exc:
                flash_route_exception(exc)
                return redirect(request.url)
        form_context = purchase_form_context()
        form_context.update(context)
        return render_template("purchase_edit.html", **form_context)

    @login_required
    def edit_purchase_document(document_id: int):
        context = get_purchase_document_context(document_id)
        if not context:
            flash("Bon d'achat introuvable.", "danger")
            return redirect(url_for("transactions", type="purchase"))
        if request.method == "POST":
            try:
                edit_purchase_document_from_form(document_id, request.form)
                flash("Bon d'achat modifie.", "success")
                return redirect(url_for("transactions", type="purchase"))
            except Exception as exc:
                flash_route_exception(exc)
                return redirect(request.url)
        form_context = purchase_form_context()
        form_context.update(context)
        return render_template("purchase_edit.html", **form_context)

    @login_required
    def delete_purchase(purchase_id: int):
        if delete_purchase_by_id(purchase_id):
            flash("Achat supprime et stock corrige.", "success")
        else:
            flash("Impossible de supprimer cet achat.", "danger")
        return redirect(url_for("purchases"))

    bind_route(app, "/purchases", "purchases", purchases, ["GET", "POST"])
    bind_route(app, "/purchases/new", "new_purchase", new_purchase, ["GET", "POST"])
    bind_route(app, "/purchases/<int:purchase_id>/edit", "edit_purchase", edit_purchase, ["GET", "POST"])
    bind_route(app, "/purchases/document/<int:document_id>/edit", "edit_purchase_document", edit_purchase_document, ["GET", "POST"])
    bind_route(app, "/purchases/<int:purchase_id>/delete", "delete_purchase", delete_purchase, ["POST"])
