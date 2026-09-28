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

    return templates.TemplateResponse(
        "accounting_scf.html",
        template_context(request, title="Comptabilité SCF Algérie", balance=balance, tcr=tcr, bilan=bilan),
    )


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
    writer.writerow(
        [
            "Compte SCF",
            "Intitulé du Compte",
            "Débit (DA)",
            "Crédit (DA)",
            "Solde Débiteurs (DA)",
            "Solde Créditeur (DA)",
        ]
    )

    total_deb = 0.0
    total_cred = 0.0
    total_solde_deb = 0.0
    total_solde_cred = 0.0

    for acc in balance:
        writer.writerow(
            [
                acc["code"],
                acc["label"],
                f"{acc['debit']:.2f}",
                f"{acc['credit']:.2f}",
                f"{acc['solde_debiteur']:.2f}",
                f"{acc['solde_crediteur']:.2f}",
            ]
        )
        total_deb += acc["debit"]
        total_cred += acc["credit"]
        total_solde_deb += acc["solde_debiteur"]
        total_solde_cred += acc["solde_crediteur"]

    writer.writerow([])
    writer.writerow(
        [
            "TOTAL",
            "TOTAL GÉNÉRAL BALANCE",
            f"{total_deb:.2f}",
            f"{total_cred:.2f}",
            f"{total_solde_deb:.2f}",
            f"{total_solde_cred:.2f}",
        ]
    )

    output.seek(0)
    bom = "\ufeff"
    return StreamingResponse(
        iter([bom + output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=balance_generale_scf_{date.today().isoformat()}.csv"},
    )


@router.get("/accounting/scf/export-excel", name="accounting_scf_export_excel")
@router.get("/accounting/export-excel", name="accounting_export_excel")
@limiter.limit("10/minute")
async def export_scf_excel(request: Request):
    user = get_current_user(request)
    if not user:
        from fastapi.responses import RedirectResponse

        return RedirectResponse("/login", status_code=303)

    import openpyxl
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

    balance = await SCFService.get_balance_generale()
    tcr = await SCFService.get_tcr(balance=balance)
    bilan = await SCFService.get_bilan(balance=balance)

    wb = openpyxl.Workbook()

    # Style presets
    header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    section_fill = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
    total_font = Font(name="Calibri", size=11, bold=True, color="000000")

    thin_border = Border(
        left=Side(style="thin", color="CBD5E1"),
        right=Side(style="thin", color="CBD5E1"),
        top=Side(style="thin", color="CBD5E1"),
        bottom=Side(style="thin", color="CBD5E1"),
    )
    align_center = Alignment(horizontal="center", vertical="center")
    align_right = Alignment(horizontal="right", vertical="center")

    # 1. Sheet: Balance Générale
    ws_bal = wb.active
    ws_bal.title = "Balance Générale"
    ws_bal.append(
        [
            "Compte SCF",
            "Intitulé du Compte",
            "Débit (DA)",
            "Crédit (DA)",
            "Solde Débiteur (DA)",
            "Solde Créditeur (DA)",
        ]
    )

    for col in range(1, 7):
        cell = ws_bal.cell(row=1, column=col)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = align_center

    tot_deb, tot_cred, tot_sdeb, tot_scred = 0.0, 0.0, 0.0, 0.0
    for row_idx, acc in enumerate(balance, start=2):
        ws_bal.append(
            [
                acc["code"],
                acc["label"],
                acc["debit"],
                acc["credit"],
                acc["solde_debiteur"],
                acc["solde_crediteur"],
            ]
        )
        for col in range(1, 7):
            c = ws_bal.cell(row=row_idx, column=col)
            c.border = thin_border
            if col in (3, 4, 5, 6):
                c.number_format = '#,##0.00 "DA"'
                c.alignment = align_right

        tot_deb += acc["debit"]
        tot_cred += acc["credit"]
        tot_sdeb += acc["solde_debiteur"]
        tot_scred += acc["solde_crediteur"]

    tot_row = len(balance) + 2
    ws_bal.append(["TOTAL", "TOTAL GÉNÉRAL BALANCE", tot_deb, tot_cred, tot_sdeb, tot_scred])
    for col in range(1, 7):
        c = ws_bal.cell(row=tot_row, column=col)
        c.font = total_font
        c.fill = section_fill
        c.border = thin_border
        if col in (3, 4, 5, 6):
            c.number_format = '#,##0.00 "DA"'
            c.alignment = align_right

    # 2. Sheet: Bilan (Actif vs Passif)
    ws_bilan = wb.create_sheet(title="Bilan Comptable")
    ws_bilan.append(["POSTES DE L'ACTIF", "MONTANT (DA)", "", "POSTES DU PASSIF", "MONTANT (DA)"])
    for col in (1, 2, 4, 5):
        cell = ws_bilan.cell(row=1, column=col)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = align_center

    actif_rows = [
        ("Stocks de matières & produits", bilan["actif"]["stocks"]),
        ("Créances Clients", bilan["actif"]["creances_clients"]),
        ("Trésorerie & Caisse", bilan["actif"]["tresorerie_caisse"]),
    ]
    passif_rows = [
        ("Capitaux Propres", bilan["passif"]["capitaux_propres"]),
        ("Résultat Net de l'Exercice", bilan["passif"]["resultat_exercice"]),
        ("Dettes Fournisseurs", bilan["passif"]["dettes_fournisseurs"]),
    ]

    for i in range(max(len(actif_rows), len(passif_rows))):
        a_lbl, a_val = actif_rows[i] if i < len(actif_rows) else ("", "")
        p_lbl, p_val = passif_rows[i] if i < len(passif_rows) else ("", "")
        ws_bilan.append([a_lbl, a_val, "", p_lbl, p_val])
        row_num = i + 2
        for col, val in ((1, a_lbl), (2, a_val), (4, p_lbl), (5, p_val)):
            c = ws_bilan.cell(row=row_num, column=col)
            c.border = thin_border
            if col in (2, 5) and isinstance(val, (int, float)):
                c.number_format = '#,##0.00 "DA"'
                c.alignment = align_right

    ws_bilan.append(["TOTAL ACTIF", bilan["actif"]["total"], "", "TOTAL PASSIF", bilan["passif"]["total"]])
    tot_bilan_row = max(len(actif_rows), len(passif_rows)) + 2
    for col in (1, 2, 4, 5):
        c = ws_bilan.cell(row=tot_bilan_row, column=col)
        c.font = total_font
        c.fill = section_fill
        c.border = thin_border
        if col in (2, 5):
            c.number_format = '#,##0.00 "DA"'
            c.alignment = align_right

    # 3. Sheet: TCR (Compte de Résultat)
    ws_tcr = wb.create_sheet(title="Compte de Résultat (TCR)")
    ws_tcr.append(["RUBRIQUE TCR (SCF)", "MONTANT (DA)"])
    for col in (1, 2):
        cell = ws_tcr.cell(row=1, column=col)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = align_center

    tcr_items = [
        ("Chiffre d'Affaires (Ventes 700 / 707)", tcr["chiffre_affaires"]),
        ("Achats consommés (600 / 607)", tcr["achats_consommes"]),
        ("Marge Brute", tcr["marge_brute"]),
        ("Autres charges externes d'exploitation (625 / 629)", tcr["autres_charges_externes"]),
        ("Valeur Ajoutée d'Exploitation", tcr["valeur_ajoutee"]),
        ("Résultat d'Exploitation", tcr["resultat_exploitation"]),
        ("RÉSULTAT NET DE L'EXERCICE", tcr["resultat_net"]),
    ]

    for idx, (lbl, val) in enumerate(tcr_items, start=2):
        ws_tcr.append([lbl, val])
        c1 = ws_tcr.cell(row=idx, column=1)
        c2 = ws_tcr.cell(row=idx, column=2)
        c1.border = thin_border
        c2.border = thin_border
        c2.number_format = '#,##0.00 "DA"'
        c2.alignment = align_right
        if "RÉSULTAT" in lbl or "Marge Brute" in lbl or "Valeur Ajoutée" in lbl:
            c1.font = total_font
            c2.font = total_font
            c1.fill = section_fill
            c2.fill = section_fill

    # Auto-adjust column widths
    for sheet in (ws_bal, ws_bilan, ws_tcr):
        for col in sheet.columns:
            max_len = max(len(str(cell.value or "")) for cell in col)
            col_letter = openpyxl.utils.get_column_letter(col[0].column)
            sheet.column_dimensions[col_letter].width = max(max_len + 4, 14)

    bio = io.BytesIO()
    wb.save(bio)
    bio.seek(0)

    filename = f"etats_financiers_scf_{date.today().isoformat()}.xlsx"
    return StreamingResponse(
        bio,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )

