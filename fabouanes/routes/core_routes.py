from __future__ import annotations

from datetime import date

from fabouanes.fastapi_compat import current_app, g, jsonify, redirect, render_template, request, session, url_for

from fabouanes.core.db_access import query_db
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
    def dashboard_summary():
        target_date = request.args.get("date")
        return jsonify(dict(get_dashboard_snapshot(target_date)))

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

    def api_item_info():
        if not session.get("user_id"):
            return {"ok": False}, 401
        kind = (request.args.get("kind") or "").strip()
        item_id = request.args.get("id", type=int)
        if not item_id or kind not in {"raw", "finished"}:
            return {"ok": False}, 400
        if kind == "raw":
            row = query_db(
                "SELECT id, name, unit, stock_qty, sale_price, avg_cost FROM raw_materials WHERE id = ?",
                (item_id,),
                one=True,
            )
            if not row:
                return {"ok": False}, 404
            return {
                "ok": True,
                "item": {
                    "unit": row["unit"],
                    "stock_qty": float(row["stock_qty"]),
                    "sale_price": float(row["sale_price"]),
                    "avg_cost": float(row["avg_cost"]),
                },
            }
        row = query_db(
            "SELECT id, name, default_unit AS unit, stock_qty, sale_price, avg_cost FROM finished_products WHERE id = ?",
            (item_id,),
            one=True,
        )
        if not row:
            return {"ok": False}, 404
        return {
            "ok": True,
            "item": {
                "unit": row["unit"],
                "stock_qty": float(row["stock_qty"]),
                "sale_price": float(row["sale_price"]),
                "avg_cost": float(row["avg_cost"]),
            },
        }

    @login_required
    def api_recipe(recipe_id: int):
        recipe = query_db(
            """
            SELECT sr.id, sr.finished_product_id, sr.name, COALESCE(sr.notes,'') AS notes, fp.name AS finished_name
            FROM saved_recipes sr
            JOIN finished_products fp ON fp.id = sr.finished_product_id
            WHERE sr.id = ?
            """,
            (recipe_id,),
            one=True,
        )
        if not recipe:
            return {"ok": False}, 404
        items = [dict(row) for row in query_db(
            """
            SELECT sri.raw_material_id, sri.quantity, sri.position,
                   rm.name AS material_name, rm.stock_qty, rm.unit
            FROM saved_recipe_items sri
            JOIN raw_materials rm ON rm.id = sri.raw_material_id
            WHERE sri.recipe_id = ?
            ORDER BY sri.position, sri.id
            """,
            (recipe_id,),
        )]
        return {
            "ok": True,
            "recipe": {
                "id": int(recipe["id"]),
                "finished_product_id": int(recipe["finished_product_id"]),
                "name": recipe["name"],
                "notes": recipe["notes"],
                "finished_name": recipe["finished_name"],
                "items": [
                    {
                        "raw_material_id": int(row["raw_material_id"]),
                        "quantity": float(row["quantity"]),
                        "material_name": row["material_name"],
                        "stock_qty": float(row["stock_qty"]),
                        "unit": row["unit"],
                    }
                    for row in items
                ],
            },
        }

    def health():
        return jsonify({"ok": True, "service": "FABOuanes", "version": "v10.12"})

    bind_route(app, "/", "index", index, ["GET"])
    bind_route(app, "/dashboard", "dashboard", dashboard, ["GET"])
    bind_route(app, "/dashboard/summary", "dashboard_summary", dashboard_summary, ["GET"])
    bind_route(app, "/api/kpi-date", "api_kpi_date", api_kpi_date, ["GET"])
    bind_route(app, "/api/kpi-at-date", "api_kpi_at_date", api_kpi_at_date, ["GET"])
    bind_route(app, "/api/item-info", "api_item_info", api_item_info, ["GET"])
    bind_route(app, "/api/recipe/<int:recipe_id>", "api_recipe", api_recipe, ["GET"])
    bind_route(app, "/reports", "reports", reports, ["GET"])
    bind_route(app, "/health", "health", health, ["GET"])
