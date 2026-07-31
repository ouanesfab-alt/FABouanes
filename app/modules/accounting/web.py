"""
Routes Web pour la Comptabilité SCF (Balance Général, Bilan, TCR).
"""
from __future__ import annotations

import csv
import io
from datetime import date

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.core.rate_limit import limiter
from app.modules.accounting.scf_service import SCFService
from app.web.deps import get_current_user, template_context, templates

router = APIRouter()


@router.get("/accounting/scf", name="accounting_scf_dashboard")
@limiter.limit("20/minute")
async def accounting_dashboard(request: Request):
    user = get_current_user(request)
    if not user:
        from fastapi.responses import RedirectResponse
        return RedirectResponse("/login", status_code=303)

    balance = await SCFService.get_balance_generale()
    tcr = await SCFService.get_tcr()
    bilan = await SCFService.get_bilan()

    return templates.TemplateResponse("accounting_scf.html", template_context(
        request,
        title="Comptabilité SCF Algérie",
        balance=balance,
        tcr=tcr,
        bilan=bilan
    ))


@router.get("/accounting/balance/export", name="accounting_balance_export")
@limiter.limit("10/minute")
async def export_balance(request: Request):
    user = get_current_user(request)
    if not user:
        from fastapi.responses import RedirectResponse
        return RedirectResponse("/login", status_code=303)

    balance = await SCFService.get_balance_generale()

    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow(["Compte SCF", "Intitulé du Compte", "Débit (DA)", "Crédit (DA)", "Solde Débiteurs (DA)", "Solde Créditeur (DA)"])

    total_deb = 0.0
    total_cred = 0.0
    total_solde_deb = 0.0
    total_solde_cred = 0.0

    for acc in balance:
        writer.writerow([
            acc["code"],
            acc["label"],
            f"{acc['debit']:.2f}",
            f"{acc['credit']:.2f}",
            f"{acc['solde_debiteur']:.2f}",
            f"{acc['solde_crediteur']:.2f}"
        ])
        total_deb += acc["debit"]
        total_cred += acc["credit"]
        total_solde_deb += acc["solde_debiteur"]
        total_solde_cred += acc["solde_crediteur"]

    writer.writerow([])
    writer.writerow(["TOTAL", "TOTAL GÉNÉRAL BALANCE", f"{total_deb:.2f}", f"{total_cred:.2f}", f"{total_solde_deb:.2f}", f"{total_solde_cred:.2f}"])

    output.seek(0)
    bom = "\ufeff"
    return StreamingResponse(
        iter([bom + output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=balance_generale_scf_{date.today().isoformat()}.csv"},
    )
