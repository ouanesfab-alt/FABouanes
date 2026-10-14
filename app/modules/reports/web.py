"""Routes web du module Rapports & Statistiques."""

from __future__ import annotations

import asyncio
import csv
import io
import logging
from datetime import date

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.async_db import get_async_session
from app.core.perf_cache import async_cached_result
from app.core.rate_limit import limiter
from app.core.runtime_paths import paths
from app.modules.reports.bon_space_service import find_bon_space_document, list_bon_space_documents
from app.modules.reports.service import ReportsService
from app.utils.tool_pages import (
    create_user_note,
    delete_pdf_reader_file,
    delete_user_note,
    get_pdf_reader_file_path,
    list_pdf_reader_files,
    list_user_notes,
    save_pdf_reader_upload,
    save_user_note,
)
from app.web.deps import csrf_protect, flash, get_current_user, require_permission, template_context, templates

logger = logging.getLogger("fabouanes.web.report_pages")

router = APIRouter()


def get_reports_service(db: AsyncSession = Depends(get_async_session)) -> ReportsService:
    return ReportsService(db)


@router.get("/reports", name="reports_dashboard")
@limiter.limit("20/minute")
async def reports_page(request: Request, reports_service: ReportsService = Depends(get_reports_service)):
    denied = require_permission(request, "reports.read")
    if denied:
        return denied
    date_from = request.query_params.get("date_from", "")
    date_to = request.query_params.get("date_to", "")

    async def _load_context():
        dto = await reports_service.build_reports_context(date_from or None, date_to or None)
        return dto.model_dump()

    ctx = await async_cached_result(
        ("dashboard", "reports", date_from or "", date_to or ""),
        _load_context,
        ttl_seconds=300.0,
    )

    fmt = request.query_params.get("format", "").lower()
    if fmt == "csv":
        output = io.StringIO()
        writer = csv.writer(output, delimiter=";")
        writer.writerow(["=== RÉSUMÉ GLOBAL ==="])
        writer.writerow(["Indicateur", "Valeur"])
        writer.writerow(["Total Ventes", ctx["summary"]["total_sales"]])
        writer.writerow(["Profit Brut", ctx["summary"]["total_profit"]])
        writer.writerow(["Total Dépenses", ctx["expenses_total"]])
        writer.writerow(["Bénéfice Net", ctx["net_profit"]])
        writer.writerow(["Total Achats", ctx["summary"]["total_purchases"]])
        writer.writerow(["Total Versements", ctx["summary"]["total_payments"]])
        writer.writerow([])

        writer.writerow(["=== BALANCES CLIENTS / RETARDS ==="])
        writer.writerow(["Client", "Total Dû", "Dépassement", "Dernier Versement", "Retard (jours)"])
        for c in ctx.get("client_debts", []):
            writer.writerow(
                [c["name"], c["debt"], c["over_threshold"], c["last_payment_date"] or "-", c["overdue_days"]]
            )
        writer.writerow([])

        writer.writerow(["=== TOP PRODUITS ==="])
        writer.writerow(["Produit", "CA", "Profit", "Quantité"])
        for p in ctx["top_products"]:
            writer.writerow([p["name"], p["revenue"], p["profit"], p["qty"]])
        writer.writerow([])

        writer.writerow(["=== TOP CLIENTS ==="])
        writer.writerow(["Client", "CA", "Profit", "Nombre"])
        for c in ctx["top_clients"]:
            writer.writerow([c["name"], c["revenue"], c["profit"], c["count"]])

        output.seek(0)
        filename = f"report_{date.today().isoformat()}.csv"
        return StreamingResponse(
            iter(["\ufeff" + output.getvalue()]),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    elif fmt == "xlsx":
        import openpyxl
        from openpyxl.styles import Font

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Rapport"

        ws.append(["RAPPORT DÉCISIONNEL FABOUANES"])
        ws.append([])

        ws.append(["=== RÉSUMÉ GLOBAL ==="])
        ws.append(["Indicateur", "Valeur"])
        ws.append(["Total Ventes", ctx["summary"]["total_sales"]])
        ws.append(["Profit Brut", ctx["summary"]["total_profit"]])
        ws.append(["Total Dépenses", ctx["expenses_total"]])
        ws.append(["Bénéfice Net", ctx["net_profit"]])
        ws.append(["Total Achats", ctx["summary"]["total_purchases"]])
        ws.append(["Total Versements", ctx["summary"]["total_payments"]])
        ws.append([])

        ws.append(["=== BALANCES CLIENTS / RETARDS ==="])
        ws.append(["Client", "Total Dû", "Dépassement", "Dernier Versement", "Retard (jours)"])
        for c in ctx.get("client_debts", []):
            ws.append([c["name"], c["debt"], c["over_threshold"], c["last_payment_date"] or "-", c["overdue_days"]])
        ws.append([])

        ws.append(["=== TOP PRODUITS ==="])
        ws.append(["Produit", "CA", "Profit", "Quantité"])
        for p in ctx["top_products"]:
            ws.append([p["name"], p["revenue"], p["profit"], p["qty"]])
        ws.append([])

        ws.append(["=== TOP CLIENTS ==="])
        ws.append(["Client", "CA", "Profit", "Nombre"])
        for c in ctx["top_clients"]:
            ws.append([c["name"], c["revenue"], c["profit"], c["count"]])

        ws.freeze_panes = "A4"

        bold_font = Font(bold=True)
        # Bold on major headings/sections
        sections = [
            1,
            3,
            12,
            12 + len(ctx.get("client_debts", [])) + 2,
            12 + len(ctx.get("client_debts", [])) + 2 + len(ctx["top_products"]) + 2,
        ]
        for idx in sections:
            try:
                for cell in ws[idx]:
                    cell.font = bold_font
            except Exception:
                pass

        for col in ws.columns:
            max_len = max(len(str(cell.value or "")) for cell in col)
            col_letter = openpyxl.utils.get_column_letter(col[0].column)
            ws.column_dimensions[col_letter].width = max(max_len + 3, 10)

        filename = f"report_{date.today().isoformat()}.xlsx"
        out_buf = io.BytesIO()
        wb.save(out_buf)
        out_buf.seek(0)
        return StreamingResponse(
            out_buf,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    return templates.TemplateResponse(
        "reports_dashboard.html",
        template_context(
            request,
            title="Rapports & Statistiques",
            **ctx,
        ),
    )


@router.get("/reports/export-csv", name="reports_export_csv")
@limiter.limit("10/minute")
async def export_csv(request: Request, reports_service: ReportsService = Depends(get_reports_service)):
    denied = require_permission(request, "reports.read")
    if denied:
        return denied
    date_from = request.query_params.get("date_from", "")
    date_to = request.query_params.get("date_to", "")

    async def _load_context():
        dto = await reports_service.build_reports_context(date_from or None, date_to or None)
        return dto.model_dump()

    ctx = await async_cached_result(
        ("dashboard", "reports", date_from or "", date_to or ""),
        _load_context,
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
        iter([(bom + output.getvalue()).encode("utf-8")]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=rapport_fabouanes.csv"},
    )


@router.get("/reports/livre-journal/export", name="reports_export_livre_journal")
@limiter.limit("10/minute")
async def export_livre_journal(
    request: Request,
    service: ReportsService = Depends(get_reports_service),
):
    """Export standard Livre Journal (accounting ledger) in CSV/Excel format."""
    denied = require_permission(request, "reports.read")
    if denied:
        return denied

    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow(["Date", "Type / Ref", "Libellé / Partenaire", "Débit (DA)", "Crédit (DA)"])

    entries = await service.get_livre_journal_entries()

    for row in entries:
        tx_date = str(row.get("tx_date", "") or "")
        tx_ref = str(row.get("tx_ref", "") or "")
        label = str(row.get("label", "") or "")
        debit_val = float(row.get("debit") or 0.0)
        credit_val = float(row.get("credit") or 0.0)
        writer.writerow([tx_date, tx_ref, label, f"{debit_val:.2f}", f"{credit_val:.2f}"])

    output.seek(0)
    bom = "\ufeff"
    return StreamingResponse(
        iter([(bom + output.getvalue()).encode("utf-8")]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=livre_journal_{date.today().isoformat()}.csv"},
    )


@router.get("/reports/marge-brute/export", name="reports_export_marge_brute")
@limiter.limit("10/minute")
async def export_marge_brute(
    request: Request,
    service: ReportsService = Depends(get_reports_service),
):
    """Export product margin analysis (Gross Margin & % Margin) in CSV/Excel format."""
    denied = require_permission(request, "reports.read")
    if denied:
        return denied

    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow(
        [
            "Produit Fini",
            "Quantité Vendue",
            "Chiffre d'Affaires (DA)",
            "Coût Moyen (CMP DA)",
            "Coût Total (DA)",
            "Marge Brute (DA)",
            "Taux de Marge (%)",
        ]
    )

    rows = await service.get_marge_brute_data()

    for r in rows:
        qty = float(r["total_qty"])
        rev = float(r["total_revenue"])
        unit_cost = float(r["avg_cost"] or 0)
        cogs = qty * unit_cost
        margin = rev - cogs
        margin_pct = (margin / rev * 100.0) if rev > 0 else 0.0

        writer.writerow(
            [
                r["name"],
                f"{qty:.2f}",
                f"{rev:.2f}",
                f"{unit_cost:.2f}",
                f"{cogs:.2f}",
                f"{margin:.2f}",
                f"{margin_pct:.1f}%",
            ]
        )

    output.seek(0)
    bom = "\ufeff"
    return StreamingResponse(
        iter([(bom + output.getvalue()).encode("utf-8")]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=marge_brute_{date.today().isoformat()}.csv"},
    )


# ── NOTES UTILISATEURS & BONS / DOCUMENTS ─────────────────────────────────────


@router.get("/notes", name="notes_page")
async def notes_page(request: Request):
    if not get_current_user(request):
        return RedirectResponse("/login", status_code=303)

    notes = list_user_notes()
    return templates.TemplateResponse(
        "notes.html",
        template_context(
            request,
            notes=notes,
        ),
    )


@router.post("/notes/api/create", name="notes_api_create")
async def notes_api_create(request: Request):
    if not get_current_user(request):
        return JSONResponse({"success": False, "error": "Non authentifié"}, status_code=401)
    await csrf_protect(request)

    try:
        form = await request.form()
        title = str(form.get("title", "") or "Sans titre").strip()
        content = str(form.get("content", "") or "")
        color = str(form.get("color", "yellow") or "yellow").strip()

        note = create_user_note(title, content, color)
        return JSONResponse({"success": True, "note": note})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@router.post("/notes/api/save", name="notes_api_save")
async def notes_api_save(request: Request):
    if not get_current_user(request):
        return JSONResponse({"success": False, "error": "Non authentifié"}, status_code=401)
    await csrf_protect(request)

    try:
        form = await request.form()
        note_id = str(form.get("id", "") or "").strip()
        if not note_id:
            return JSONResponse({"success": False, "error": "ID de note manquant"}, status_code=400)

        title = str(form.get("title", "") or "").strip()
        content = str(form.get("content", "") or "")
        color = str(form.get("color", "yellow") or "yellow").strip()
        pinned = form.get("pinned") == "true" or form.get("pinned") == "1"

        note = save_user_note(note_id, title, content, color, pinned)
        return JSONResponse({"success": True, "note": note})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@router.post("/notes/api/delete", name="notes_api_delete")
async def notes_api_delete(request: Request):
    if not get_current_user(request):
        return JSONResponse({"success": False, "error": "Non authentifié"}, status_code=401)
    await csrf_protect(request)

    try:
        form = await request.form()
        note_id = str(form.get("id", "") or "").strip()
        if not note_id:
            return JSONResponse({"success": False, "error": "ID de note manquant"}, status_code=400)

        success = delete_user_note(note_id)
        return JSONResponse({"success": success})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@router.get("/sw.js", name="service_worker")
async def service_worker():
    from app.version import APP_VERSION

    sw_path = paths.static_dir / "sw.js"
    headers = {"Cache-Control": "no-cache, no-store, must-revalidate"}
    if sw_path.exists():
        try:

            def _read_sw():
                with open(sw_path, "r", encoding="utf-8") as f:
                    return f.read()

            content = await asyncio.to_thread(_read_sw)
            # Remplace la version statique par la version dynamique de l'application
            content = content.replace(
                'const VERSION = "fabouanes-v47-offline";', f'const VERSION = "fabouanes-{APP_VERSION}-offline";'
            )
            return Response(content, media_type="application/javascript", headers=headers)
        except Exception as e:
            logger.warning("Erreur lors de l'injection de version dans sw.js: %s", e)
    return FileResponse(sw_path, media_type="application/javascript", headers=headers)


@router.get("/pdf-reader", name="pdf_reader")
@router.get("/bons", name="bons_space")
async def pdf_reader(request: Request, db: AsyncSession = Depends(get_async_session)):
    if not get_current_user(request):
        return RedirectResponse("/login", status_code=303)
    q = str(request.query_params.get("q", "") or "").strip()
    kind = str(request.query_params.get("kind", "") or "").strip()
    selected_key = str(request.query_params.get("doc", "") or "").strip()
    legacy_file = str(request.query_params.get("file", "") or "").strip()
    if legacy_file and not selected_key:
        selected_key = f"pdf:{legacy_file}"
    documents = await list_bon_space_documents(q=q, kind=kind, db=db)
    selected = find_bon_space_document(documents, selected_key)
    missing_doc_key = selected_key if selected_key and selected is None else ""
    return templates.TemplateResponse(
        "pdf_reader.html",
        template_context(
            request,
            files=list_pdf_reader_files(),
            documents=documents,
            selected_doc=selected,
            missing_doc_key=missing_doc_key,
            filters={"q": q, "kind": kind},
        ),
    )


@router.post("/pdf-reader", name="pdf_reader")
@router.post("/bons", name="bons_space")
async def pdf_reader_submit(request: Request):
    if not get_current_user(request):
        return RedirectResponse("/login", status_code=303)
    await csrf_protect(request)
    form = await request.form()
    action = str(form.get("action", "upload") or "upload").strip()
    if action == "delete":
        filename = str(form.get("filename", "") or "").strip()
        if filename and delete_pdf_reader_file(filename):
            flash(request, f"PDF supprimé : {filename}", "success")
        else:
            flash(request, "Fichier introuvable.", "warning")
        return RedirectResponse("/bons", status_code=303)
    uploaded = form.get("pdf_file")
    if not uploaded or not getattr(uploaded, "filename", ""):
        flash(request, "Choisissez un fichier PDF.", "warning")
        return RedirectResponse("/bons", status_code=303)
    try:
        filename = save_pdf_reader_upload(uploaded)
    except ValueError as exc:
        flash(request, str(exc), "danger" if "acceptes" in str(exc) else "warning")
        return RedirectResponse("/bons", status_code=303)
    flash(request, f"PDF ajouté : {filename}", "success")
    return RedirectResponse(f"/bons?doc=pdf:{filename}", status_code=303)


@router.get("/pdf-reader/file/{filename:path}", name="pdf_reader_file")
@router.get("/bons/file/{filename:path}", name="bons_pdf_file")
async def pdf_reader_file(request: Request, filename: str):
    if not get_current_user(request):
        return RedirectResponse("/login", status_code=303)
    path = get_pdf_reader_file_path(filename)
    if not path:
        return JSONResponse({"error": "Not found"}, status_code=404)
    return FileResponse(path, media_type="application/pdf")

