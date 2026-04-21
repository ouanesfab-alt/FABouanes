from __future__ import annotations

from datetime import date

from flask import current_app, g, jsonify, redirect, render_template, request, url_for

from fabouanes.core.decorators import login_required
from fabouanes.core.mobile_connect import build_mobile_connect_context
from fabouanes.repositories.dashboard_repository import get_dashboard_snapshot, get_kpis_for_date
from fabouanes.routes.route_utils import bind_route


def _money(value):
    try:
        amount = float(value or 0)
    except Exception:
        amount = 0.0
    return f"{amount:,.2f} DA".replace(",", " ")


def register_core_routes(app):
    def index():
        if getattr(g, "user", None) is None:
            return redirect(url_for("login"))
        context = get_dashboard_snapshot()
        context.update(build_mobile_connect_context(request))
        return render_template("dashboard.html", **context)

    @login_required
    def dashboard():
        context = get_dashboard_snapshot()
        context.update(build_mobile_connect_context(request))
        return render_template("dashboard.html", **context)

    @login_required
    def api_kpi_date():
        target_date = request.args.get("date", date.today().isoformat())
        try:
            return jsonify(get_kpis_for_date(target_date))
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception:
            current_app.logger.exception("Failed to load KPI data for %s", target_date)
            return jsonify({"error": "Erreur interne."}), 500

    @login_required
    def api_kpi_at_date():
        target_date = request.args.get("date", date.today().isoformat())
        metric = request.args.get("metric", "sales")
        labels = {
            "sales": "Ventes",
            "cash": "Encaisse",
            "profit": "Profit",
            "receivables": "Creances",
        }
        try:
            values = get_kpis_for_date(target_date)
            value = values.get(metric)
            if value is None:
                return jsonify({"error": "Indicateur inconnu"}), 400
            return jsonify(
                {
                    "date": target_date,
                    "metric": metric,
                    "label": labels.get(metric, metric),
                    "value": float(value or 0),
                    "display": _money(value),
                }
            )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception:
            current_app.logger.exception("Failed to load KPI metric %s for %s", metric, target_date)
            return jsonify({"error": "Erreur interne."}), 500

    @login_required
    def reports():
        return redirect(url_for("index"))

    def health():
        return jsonify({"ok": True, "service": "FABOuanes", "version": "v10.12"})

    bind_route(app, "/", "index", index, ["GET"])
    bind_route(app, "/dashboard", "dashboard", dashboard, ["GET"])
    bind_route(app, "/api/kpi-date", "api_kpi_date", api_kpi_date, ["GET"])
    bind_route(app, "/api/kpi-at-date", "api_kpi_at_date", api_kpi_at_date, ["GET"])
    bind_route(app, "/reports", "reports", reports, ["GET"])
    bind_route(app, "/health", "health", health, ["GET"])
