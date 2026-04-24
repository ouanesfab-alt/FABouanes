from __future__ import annotations

from fabouanes.fastapi_compat import flash, redirect, render_template, request, url_for

from fabouanes.core.activity import log_activity
from fabouanes.core.db_access import execute_db
from fabouanes.core.decorators import login_required
from fabouanes.core.helpers import wants_print_after_submit
from fabouanes.core.pagination import request_pagination
from fabouanes.core.storage import backup_database
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
        page, page_size = request_pagination()
        return render_template("production.html", **productions_context(page=page, page_size=page_size))

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

    @login_required
    def edit_production_notes():
        batch_id = int(request.form.get("batch_id", 0))
        production_date = request.form.get("production_date", "").strip()
        notes = request.form.get("notes", "").strip()
        if not batch_id:
            flash("Identifiant manquant.", "danger")
            return redirect(url_for("production"))
        updates = {}
        if production_date:
            updates["production_date"] = production_date
        updates["notes"] = notes
        sets = ", ".join(f"{key}=?" for key in updates)
        values = list(updates.values()) + [batch_id]
        execute_db(f"UPDATE production_batches SET {sets} WHERE id=?", tuple(values))
        log_activity("edit_production_notes", "production", batch_id, f"date={production_date}")
        backup_database("edit_production_notes")
        flash("Production mise à jour.", "success")
        return redirect(url_for("production"))

    bind_route(app, "/production", "production", production, ["GET", "POST"])
    bind_route(app, "/production/new", "new_production", new_production, ["GET", "POST"])
    bind_route(app, "/production/edit-notes", "edit_production_notes", edit_production_notes, ["POST"])
    bind_route(app, "/production/<int:batch_id>/delete", "delete_production", delete_production, ["POST"])
