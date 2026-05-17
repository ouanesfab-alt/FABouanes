"""Routes web du module Rapports & Statistiques."""
from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, StreamingResponse

from app.modules.reports.service import build_reports_context
from app.web.deps import require_permission, template_context, templates
from app.core.perf_cache import cached_result

router = APIRouter()


@router.get("/reports", name="reports_dashboard")
async def reports_page(request: Request):
    denied = require_permission(request, "reports.read")
    if denied:
        return denied
    date_from = request.query_params.get("date_from", "")
    date_to = request.query_params.get("date_to", "")
    
    ctx = cached_result(
        ("dashboard", "reports", date_from or "", date_to or ""),
        lambda: build_reports_context(date_from or None, date_to or None),
        ttl_seconds=300.0,
    )
    
    return templates.TemplateResponse("reports_dashboard.html", template_context(
        request, title="Rapports & Statistiques", **ctx,
    ))


@router.get("/reports/export-csv", name="reports_export_csv")
async def export_csv(request: Request):
    denied = require_permission(request, "reports.read")
    if denied:
        return denied
    date_from = request.query_params.get("date_from", "")
    date_to = request.query_params.get("date_to", "")
    
    ctx = cached_result(
        ("dashboard", "reports", date_from or "", date_to or ""),
        lambda: build_reports_context(date_from or None, date_to or None),
        ttl_seconds=300.0,
    )

    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")

    # Résumé
    writer.writerow(["=== RÉSUMÉ GLOBAL ==="])
    writer.writerow(["Indicateur", "Valeur"])
    writer.writerow(["Total Ventes", ctx["summary"]["total_sales"]])
    writer.writerow(["Profit Brut", ctx["summary"]["total_profit"]])
    writer.writerow(["Total Dépenses", ctx["expenses_total"]])
    writer.writerow(["Bénéfice Net", ctx["net_profit"]])
    writer.writerow(["Total Achats", ctx["summary"]["total_purchases"]])
    writer.writerow(["Total Versements", ctx["summary"]["total_payments"]])
    writer.writerow([])

    # Top produits
    writer.writerow(["=== TOP PRODUITS ==="])
    writer.writerow(["Produit", "CA", "Profit", "Quantité"])
    for p in ctx["top_products"]:
        writer.writerow([p["name"], p["revenue"], p["profit"], p["qty"]])
    writer.writerow([])

    # Top clients
    writer.writerow(["=== TOP CLIENTS ==="])
    writer.writerow(["Client", "CA", "Profit", "Nombre"])
    for c in ctx["top_clients"]:
        writer.writerow([c["name"], c["revenue"], c["profit"], c["count"]])

    output.seek(0)
    bom = "\ufeff"
    return StreamingResponse(
        iter([bom + output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=rapport_fabouanes.csv"},
    )
