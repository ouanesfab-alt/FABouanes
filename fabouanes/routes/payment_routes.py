from __future__ import annotations

from fabouanes.fastapi_compat import flash, redirect, render_template, request, url_for

from fabouanes.core.decorators import login_required
from fabouanes.core.helpers import wants_print_after_submit
from fabouanes.core.pagination import request_pagination
from fabouanes.routes.route_utils import bind_route, flash_route_exception
from fabouanes.services.payment_service import (
    create_payment_from_form,
    delete_payment_by_id,
    edit_payment_from_form,
    get_edit_payment_context,
    new_payment_context,
    payments_context,
)


def register_payment_routes(app):
    @login_required
    def payments():
        if request.method == "POST":
            try:
                create_payment_from_form(request.form)
                flash("Paiement enregistre.", "success")
                return redirect(url_for("payments"))
            except Exception as exc:
                flash_route_exception(exc)
                return redirect(url_for("payments"))
        page, page_size = request_pagination()
        return render_template("payments.html", **payments_context(page=page, page_size=page_size))

    @login_required
    def new_payment():
        mode = request.args.get("mode") or request.form.get("payment_type") or "versement"
        heading = "Enregistrer une avance" if mode == "avance" else "Enregistrer un versement"
        button_label = "Enregistrer l'avance" if mode == "avance" else "Enregistrer le versement"
        if request.method == "POST":
            try:
                payment_id, payment_type = create_payment_from_form(request.form)
                flash("Avance enregistree." if payment_type == "avance" else "Versement enregistre.", "success")
                if wants_print_after_submit():
                    return redirect(url_for("print_document", doc_type="payment", item_id=payment_id))
                return redirect(url_for("transactions", type="payment"))
            except Exception as exc:
                flash_route_exception(exc)
                return redirect(url_for("new_payment", mode=mode))
        context = new_payment_context()
        context.update(
            {
                "heading": heading,
                "button_label": button_label,
                "payment_type": mode,
                "show_sale_link": mode != "avance",
            }
        )
        return render_template("payment_new.html", **context)

    @login_required
    def edit_payment(payment_id: int):
        context = get_edit_payment_context(payment_id)
        if not context:
            flash("Versement introuvable.", "danger")
            return redirect(url_for("transactions", type="payment"))
        if request.method == "POST":
            try:
                edit_payment_from_form(payment_id, request.form)
                flash("Transaction client modifiee.", "success")
                return redirect(url_for("transactions", type="payment"))
            except Exception as exc:
                flash_route_exception(exc)
                return redirect(request.url)
        return render_template("payment_edit.html", **context)

    @login_required
    def delete_payment(payment_id: int):
        if delete_payment_by_id(payment_id):
            flash("Transaction client supprimee.", "success")
        else:
            flash("Transaction introuvable.", "danger")
        return redirect(url_for("transactions", type="payment"))

    bind_route(app, "/payments", "payments", payments, ["GET", "POST"])
    bind_route(app, "/payments/new", "new_payment", new_payment, ["GET", "POST"])
    bind_route(app, "/payments/<int:payment_id>/edit", "edit_payment", edit_payment, ["GET", "POST"])
    bind_route(app, "/payments/<int:payment_id>/delete", "delete_payment", delete_payment, ["POST"])
