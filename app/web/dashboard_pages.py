from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse

from app.utils.mobile_connect import build_mobile_connect_context
from app.web.deps import get_current_user, template_context, templates
from app.modules.reports.repository import get_dashboard_snapshot, get_kpis_for_date
from app.modules.assistant.schema_context import get_gemini_api_key
from app.core.db_helpers import db_manager


router = APIRouter()


def _money(value):
    try:
        amount = int(round(float(value or 0)))
    except Exception:
        amount = 0
    return f"{amount:,} DA".replace(",", " ")


def _assistant_context():
    """Build context variables for the inline Sabrina assistant widget."""
    api_key = get_gemini_api_key()
    selected_model = db_manager.get_setting("gemini_model", "gemini-3.1-flash-lite").strip()
    if not selected_model:
        selected_model = "gemini-3.1-flash-lite"
    is_local = selected_model.lower() in ("local", "ollama")
    has_key = bool(api_key) or is_local
    return {"has_key": has_key, "selected_model": selected_model}


@router.get("/", name="index")
async def index(request: Request):
    if not get_current_user(request):
        return RedirectResponse("/login", status_code=303)
    context = await get_dashboard_snapshot()
    context.update(build_mobile_connect_context(request))
    context.update(_assistant_context())
    return templates.TemplateResponse("dashboard.html", template_context(request, **context))


@router.get("/dashboard", name="dashboard")
async def dashboard(request: Request):
    if not get_current_user(request):
        return RedirectResponse("/login", status_code=303)
    context = await get_dashboard_snapshot()
    context.update(build_mobile_connect_context(request))
    context.update(_assistant_context())
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
        return JSONResponse(await get_kpis_for_date(target_date))
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
        "receivables": "Créances",
    }
    try:
        values = await get_kpis_for_date(target_date)
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
