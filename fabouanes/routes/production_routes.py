from __future__ import annotations

from flask import flash, redirect, render_template, request, url_for

from fabouanes.core.decorators import login_required
from fabouanes.core.helpers import wants_print_after_submit
from fabouanes.routes.route_utils import bind_route, flash_route_exception
from fabouanes.services.production_service import (
    create_production_from_form,
    delete_production_by_id,
    new_production_context,
    productions_context,
)


def register_production_routes(app):
    @login_required
    def production():
        if request.method == "POST":
            try:
                create_production_from_form(request.form)
                flash("Production multi-matières enregistrée avec coût de revient.", "success")
                return redirect(url_for("production"))
            except Exception as exc:
                flash_route_exception(exc)
                return redirect(url_for("production"))
        return render_template("production.html", **productions_context())

    @login_required
    def new_production():
        if request.method == "POST":
            try:
                result = create_production_from_form(request.form)
                if result["recipe_id"]:
                    flash(
                        f"Production enregistrée. Recette sauvegardée ({result['recipe_label']}). "
                        f"Reste théorique: {result['remainder']:.2f} kg.",
                        "success",
                    )
                else:
                    flash(
                        f"Production enregistrée avec recette et coût de revient. "
                        f"Reste théorique: {result['remainder']:.2f} kg.",
                        "success",
                    )
                if wants_print_after_submit():
                    return redirect(url_for("print_document", doc_type="production", item_id=result["batch_id"]))
                return redirect(url_for("production"))
            except Exception as exc:
                flash_route_exception(exc)
                return redirect(url_for("new_production"))
        return render_template("production_new.html", **new_production_context())

    @login_required
    def delete_production(batch_id: int):
        if delete_production_by_id(batch_id):
            flash("Production supprimée et stock corrigé.", "success")
        else:
            flash("Impossible de supprimer cette production.", "danger")
        return redirect(url_for("production"))

    bind_route(app, "/production", "production", production, ["GET", "POST"])
    bind_route(app, "/production/new", "new_production", new_production, ["GET", "POST"])
    bind_route(app, "/production/<int:batch_id>/delete", "delete_production", delete_production, ["POST"])
