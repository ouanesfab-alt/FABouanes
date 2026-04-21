from __future__ import annotations

from flask import flash, g, redirect, render_template, request, session, url_for

from fabouanes.core.activity import log_activity
from fabouanes.core.audit import audit_event
from fabouanes.core.decorators import login_required
from fabouanes.routes.route_utils import bind_route
from fabouanes.services.auth_service import attempt_login, change_user_password


def register_auth_routes(app):
    def login():
        if g.user is not None:
            return redirect(url_for("index"))
        if request.method == "POST":
            result = attempt_login(request.form.get("username", ""), request.form.get("password", ""))
            if result["ok"]:
                user = result["user"]
                session.clear()
                session["user_id"] = user["id"]
                session.permanent = bool(request.form.get("remember"))
                flash("Connexion reussie.", "success")
                if int(user["must_change_password"] or 0):
                    flash("Change immediatement le mot de passe administrateur par defaut.", "warning")
                    return redirect(url_for("change_password"))
                return redirect(url_for("index"))
            flash(result["message"], "danger")
            if result.get("status") == 429:
                return render_template("login.html"), 429
        return render_template("login.html")

    @login_required
    def change_password():
        if request.method == "POST":
            result = change_user_password(
                g.user["id"],
                request.form.get("current_password", ""),
                request.form.get("new_password", ""),
                request.form.get("confirm_password", ""),
            )
            if not result["ok"]:
                flash(result["message"], "danger")
                return redirect(url_for("change_password"))
            flash(result["message"], "success")
            return redirect(url_for("index"))
        return render_template("change_password.html")

    def logout():
        if g.user is not None:
            log_activity("logout", "user", g.user["id"], f"Deconnexion de {g.user['username']}")
            audit_event("logout", "user", g.user["id"], after={"username": g.user["username"]})
        session.clear()
        flash("Vous etes deconnecte.", "success")
        return redirect(url_for("login"))

    bind_route(app, "/login", "login", login, ["GET", "POST"])
    bind_route(app, "/change-password", "change_password", change_password, ["GET", "POST"])
    bind_route(app, "/logout", "logout", logout, ["GET"])

