from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path
from typing import Any
import pandas as pd
from decimal import Decimal, InvalidOperation


def parse_client_history_excel(file_path: str) -> dict:
    """
    Parse un grand livre client au format Excel FABOuanes.

    Structure attendue du fichier :
      - iloc[0, 1] : nom du client
      - iloc[1]    : ligne vide
      - iloc[2]    : en-têtes (Date | Designation | Montant a Payer | Versement | Reste a Payer)
      - iloc[3+]   : lignes de données

    Retourne un dict avec :
      {
        "client_name": str,
        "rows": [
          {
            "ordre_import": int,
            "date": str,                # format ISO "YYYY-MM-DD"
            "designation": str,
            "montant_achat": float,
            "montant_verse": float,
            "solde_cumule": float,
            "type_operation": str,      # "achat"|"versement"|"mixte"|"immediat"|"ouverture"
          },
          ...
        ],
        "solde_final": float,
        "total_achats": float,
        "total_verses": float,
        "nb_lignes": int,
        "nb_dates_hors_ordre": int,
      }
    """
    # === Lecture du nom client ===
    try:
        raw = pd.read_excel(file_path, header=None)
    except Exception as e:
        raise ValueError(f"Impossible de lire le fichier Excel : {e}")

    if raw.shape[0] < 3 or raw.shape[1] < 2:
        raise ValueError("Le fichier Excel ne respecte pas le format attendu (trop petit).")

    client_name = str(raw.iloc[0, 1]).strip()
    if client_name.lower() in ("nan", "none", ""):
        client_name = "Client inconnu"

    # === Lecture des données ===
    try:
        df = pd.read_excel(
            file_path,
            skiprows=2,  # saute ligne nom + ligne vide
            header=0,    # la ligne 3 (index 2) est l'en-tête
            usecols=[0, 1, 2, 3, 4],
            names=["date_raw", "designation", "montant_achat_raw",
                   "montant_verse_raw", "solde_cumule_raw"],
            dtype=str,
        )
    except Exception as e:
        raise ValueError(f"Erreur lors de la lecture des lignes de données : {e}")

    rows = []
    ordre = 0

    for _, row in df.iterrows():
        date_str = str(row.get("date_raw", "")).strip()

        # Ignorer les lignes sans date valide ou lignes d'en-tête répétées
        if not date_str or date_str.lower() in ("nan", "none", "date", ""):
            continue

        # Parser la date (format JJ/MM/AAAA)
        try:
            date_parsed = pd.to_datetime(
                date_str, dayfirst=True, errors="raise"
            ).date().isoformat()
        except Exception:
            continue  # ignorer les lignes avec date illisible

        montant_achat = _to_float(row.get("montant_achat_raw"))
        montant_verse = _to_float(row.get("montant_verse_raw"))
        solde_cumule  = _to_float(row.get("solde_cumule_raw"))
        
        designation   = str(row.get("designation", "")).strip()
        if designation.lower() in ("nan", "none"):
            designation = ""

        # Déterminer le type d'opération
        type_op = _classify_operation(
            designation, montant_achat, montant_verse, ordre
        )

        rows.append({
            "ordre_import":  ordre,
            "date":          date_parsed,
            "designation":   designation,
            "montant_achat": montant_achat,
            "montant_verse": montant_verse,
            "solde_cumule":  solde_cumule,
            "type_operation": type_op,
        })
        ordre += 1

    if not rows:
        raise ValueError("Aucune ligne de données valide trouvée dans le fichier Excel.")

    # Compter les dates hors ordre
    nb_hors_ordre = 0
    for i in range(1, len(rows)):
        if rows[i]["date"] < rows[i-1]["date"]:
            nb_hors_ordre += 1

    return {
        "client_name":        client_name,
        "rows":               rows,
        "solde_final":        rows[-1]["solde_cumule"],
        "total_achats":       sum(r["montant_achat"] for r in rows),
        "total_verses":       sum(r["montant_verse"] for r in rows),
        "nb_lignes":          len(rows),
        "nb_dates_hors_ordre": nb_hors_ordre,
    }


def _to_float(val) -> float:
    """Convertit une valeur brute Excel en float, 0.0 si vide/invalide."""
    try:
        s = str(val or "").strip().replace(" ", "").replace("\xa0", "").replace(",", ".")
        if s.lower() in ("nan", "none", ""):
            return 0.0
        return float(Decimal(s))
    except (InvalidOperation, ValueError):
        return 0.0


def _classify_operation(
    designation: str,
    montant_achat: float,
    montant_verse: float,
    ordre: int
) -> str:
    """
    Classifie le type d'opération pour l'affichage.

    Règles :
    - ordre == 0 ET designation contient "ancien" → "ouverture"
    - purchase > 0 ET verse == 0  → "achat"
    - purchase == 0 ET verse > 0  → "versement"
    - purchase > 0 ET verse > 0 ET purchase == verse → "immediat" (payé cash)
    - purchase > 0 ET verse > 0 ET purchase != verse → "mixte"
    """
    if ordre == 0 and "ancien" in designation.lower():
        return "ouverture"
    if montant_achat > 0 and montant_verse == 0:
        return "achat"
    if montant_achat == 0 and montant_verse > 0:
        return "versement"
    if montant_achat > 0 and montant_verse > 0:
        if abs(montant_achat - montant_verse) < 0.01:
            return "immediat"
        return "mixte"
    return "achat"  # fallback


# === FONCTIONS ORIGINALES RESTAURÉES ===

def parse_flexible_date(value) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip() if value is not None else ""
    if not text or text.lower() in {"none", "nan"}:
        return date.today().isoformat()
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%m/%d/%Y", "%d/%m/%y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except Exception:
            pass
    try:
        return datetime.fromisoformat(text).date().isoformat()
    except Exception:
        return date.today().isoformat()


def parse_flexible_amount(value) -> float:
    if value in (None, ""):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace("\xa0", "").replace(" ", "").replace("DA", "").replace("da", "")
    text = text.replace(",", ".") if text.count(",") == 1 and text.count(".") == 0 else text.replace(",", "")
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    return float(match.group(0)) if match else 0.0


def parse_excel_client_history(file_path) -> dict:
    try:
        import openpyxl
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("Le module openpyxl est requis.") from exc

    workbook = openpyxl.load_workbook(file_path, data_only=True)
    sheet = workbook[workbook.sheetnames[0]]

    def cell_str(value):
        return str(value).strip() if value is not None else ""

    header_row = None
    for row_index, row in enumerate(sheet.iter_rows(values_only=True), start=1):
        values = [cell_str(value).lower() for value in row]
        joined = " | ".join(values)
        if "designation" in joined and ("montant" in joined or "reste" in joined or "versement" in joined):
            header_row = row_index
            break
    if not header_row:
        return {"last_date": None, "last_balance": 0.0}

    last_date = None
    last_balance = 0.0
    for row in sheet.iter_rows(min_row=header_row + 1, values_only=True):
        cells = (list(row) + [None] * 6)[:6]
        raw_date, designation, amount, payment, balance = cells[:5]
        if not any(
            value is not None and str(value).strip() and str(value).strip().lower() not in {"none", "nan"}
            for value in (raw_date, designation, amount, payment, balance)
        ):
            continue
        if raw_date is not None and str(raw_date).strip() and str(raw_date).strip().lower() not in {"none", "nan"}:
            last_date = parse_flexible_date(raw_date)
        balance_value = parse_flexible_amount(balance)
        if balance_value > 0:
            last_balance = round(balance_value, 2)
    return {"last_date": last_date, "last_balance": last_balance}


def parse_excel_client_file(file_path) -> dict:
    try:
        import openpyxl
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("Le module openpyxl est requis pour l'import Excel.") from exc

    workbook = openpyxl.load_workbook(file_path, data_only=True)
    sheet = workbook[workbook.sheetnames[0]]

    def cell_str(value: Any) -> str:
        return str(value).strip() if value is not None else ""

    top_rows = [[cell_str(value) for value in row] for row in sheet.iter_rows(min_row=1, max_row=min(6, sheet.max_row), values_only=True)]
    client_name = ""
    phone = ""
    for row in top_rows:
        cleaned = [value for value in row if value]
        if len(cleaned) >= 2 and not client_name:
            for value in cleaned:
                upper = value.upper()
                if value and "TEL" not in upper and "DATE" not in upper and "DESIGNATION" not in upper:
                    client_name = value
                    break
        for index, value in enumerate(row):
            upper = value.upper()
            if "TEL" not in upper:
                continue
            inline = value.split(":", 1)[1].strip() if ":" in value else ""
            if inline:
                phone = inline
            elif index + 1 < len(row):
                phone = row[index + 1].strip()

    header_row = None
    for row_index, row in enumerate(sheet.iter_rows(values_only=True), start=1):
        values = [cell_str(value).lower() for value in row]
        joined = " | ".join(values)
        if "designation" in joined and ("montant a payer" in joined or "reste a payer" in joined):
            header_row = row_index
            break

    history_count = 0
    opening_credit = 0.0
    final_balance = 0.0
    if header_row:
        for row in sheet.iter_rows(min_row=header_row + 1, values_only=True):
            raw_date, designation, amount, payment, balance = (list(row) + [None] * 5)[:5]
            designation_text = cell_str(designation)
            if not any(value is not None and str(value).strip() for value in (raw_date, designation, amount, payment, balance)):
                continue
            history_count += 1
            balance_num = parse_flexible_amount(balance)
            amount_num = parse_flexible_amount(amount)
            final_balance = balance_num or final_balance
            if designation_text and "ancien solde" in designation_text.lower():
                opening_credit = balance_num or amount_num or opening_credit

    if opening_credit <= 0 and final_balance > 0:
        opening_credit = final_balance
    if not client_name:
        client_name = Path(file_path).stem.replace("_", " ").strip()

    return {
        "name": client_name.strip(),
        "phone": phone.strip(),
        "address": "",
        "notes": f"Importe depuis Excel ({Path(file_path).name}). Lignes detectees: {history_count}.",
        "opening_credit": round(float(opening_credit or 0.0), 2),
        "history_count": history_count,
        "source_file": Path(file_path).name,
    }
