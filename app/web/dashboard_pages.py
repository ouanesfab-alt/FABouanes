from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse

from app.utils.mobile_connect import build_mobile_connect_context
from app.web.deps import get_current_user, template_context, templates
from app.repositories.dashboard_repository import get_dashboard_snapshot, get_kpis_for_date


router = APIRouter()


def _money(value):
    try:
        amount = float(value or 0)
    except Exception:
        amount = 0.0
    return f"{amount:,.2f} DA".replace(",", " ")


@router.get("/", name="index")
async def index(request: Request):
    if not get_current_user(request):
        return RedirectResponse("/login", status_code=303)
    context = get_dashboard_snapshot()
    context.update(build_mobile_connect_context(request))
    return templates.TemplateResponse("dashboard.html", template_context(request, **context))


@router.get("/dashboard", name="dashboard")
async def dashboard(request: Request):
    if not get_current_user(request):
        return RedirectResponse("/login", status_code=303)
    context = get_dashboard_snapshot()
    context.update(build_mobile_connect_context(request))
    return templates.TemplateResponse("dashboard.html", template_context(request, **context))


@router.get("/mobile-connect", name="mobile_connect")
async def mobile_connect(request: Request):
    if not get_current_user(request):
        return RedirectResponse("/login", status_code=303)
    context = build_mobile_connect_context(request)
    context["server_status"] = "En ligne"
    return templates.TemplateResponse("mobile_connect.html", template_context(request, **context))


@router.get("/api/kpi-date", name="api_kpi_date")
async def api_kpi_date(request: Request):
    if not get_current_user(request):
        return JSONResponse({"error": "Authentification requise."}, status_code=401)
    target_date = request.query_params.get("date", date.today().isoformat())
    try:
        return JSONResponse(get_kpis_for_date(target_date))
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    except Exception:
        return JSONResponse({"error": "Erreur interne."}, status_code=500)


@router.get("/api/kpi-at-date", name="api_kpi_at_date")
async def api_kpi_at_date(request: Request):
    if not get_current_user(request):
        return JSONResponse({"error": "Authentification requise."}, status_code=401)
    target_date = request.query_params.get("date", date.today().isoformat())
    metric = request.query_params.get("metric", "sales")
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
            return JSONResponse({"error": "Indicateur inconnu"}, status_code=400)
        return JSONResponse(
            {
                "date": target_date,
                "metric": metric,
                "label": labels.get(metric, metric),
                "value": float(value or 0),
                "display": _money(value),
            }
        )
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    except Exception:
        return JSONResponse({"error": "Erreur interne."}, status_code=500)
