"""
business_helpers.py — Helpers de raisonnement métier pour Sabrina.

Fournit des utilitaires déterministes pour :
- Parser des dates en français ("aujourd'hui", "hier", "5 juillet"...)
- Normaliser des montants et quantités ("45 000 DA", "1,5 kg", "45k"...)
- Recherche floue de clients/produits dans la base de données
"""
from __future__ import annotations

import re
import logging
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger("fabouanes.assistant.business_helpers")


# ---------------------------------------------------------------------------
# Date parsing — français
# ---------------------------------------------------------------------------

MONTHS_FR = {
    "janvier": 1, "jan": 1,
    "février": 2, "fevrier": 2, "fev": 2,
    "mars": 3,
    "avril": 4, "avr": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7, "juil": 7,
    "août": 8, "aout": 8,
    "septembre": 9, "sep": 9, "sept": 9,
    "octobre": 10, "oct": 10,
    "novembre": 11, "nov": 11,
    "décembre": 12, "decembre": 12, "dec": 12,
}

WEEKDAYS_FR = {
    "lundi": 0, "mardi": 1, "mercredi": 2, "jeudi": 3,
    "vendredi": 4, "samedi": 5, "dimanche": 6,
}


def parse_french_date(text: str, reference: Optional[date] = None) -> Optional[date]:
    """
    Parse une expression de date en français et retourne un objet date.

    Exemples acceptés :
        "aujourd'hui", "hier", "avant-hier",
        "5 juillet", "le 5 juillet 2024",
        "lundi", "mardi prochain",
        "cette semaine", "la semaine dernière",
        "ce mois", "le mois dernier",
        "2024-07-05", "05/07/2024"

    Retourne None si le texte ne peut pas être parsé.
    """
    if not text:
        return None

    today = reference or date.today()
    text = text.strip().lower()

    # --- Relatifs simples ---
    if text in ("aujourd'hui", "aujourd hui", "auj"):
        return today
    if text in ("hier",):
        return today - timedelta(days=1)
    if text in ("avant-hier", "avant hier"):
        return today - timedelta(days=2)
    if text in ("demain",):
        return today + timedelta(days=1)

    # --- ISO format YYYY-MM-DD ---
    iso_match = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", text)
    if iso_match:
        try:
            return date(int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3)))
        except ValueError:
            pass

    # --- DD/MM/YYYY ou DD-MM-YYYY ---
    dmy_match = re.fullmatch(r"(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})", text)
    if dmy_match:
        try:
            return date(int(dmy_match.group(3)), int(dmy_match.group(2)), int(dmy_match.group(1)))
        except ValueError:
            pass

    # --- "le 5 juillet" / "5 juillet" / "5 juillet 2024" ---
    month_pattern = "|".join(MONTHS_FR.keys())
    date_match = re.search(
        rf"(?:le\s+)?(\d{{1,2}})\s+({month_pattern})(?:\s+(\d{{4}}))?(?:\s|$)",
        text,
    )
    if date_match:
        day = int(date_match.group(1))
        month = MONTHS_FR.get(date_match.group(2), 0)
        year = int(date_match.group(3)) if date_match.group(3) else today.year
        if month:
            try:
                result = date(year, month, day)
                # If no explicit year and the date falls before the reference date,
                # keep it in the current year (don't auto-advance to next year).
                # Only advance if the date is strictly in the future relative to
                # the reference and no year was specified — i.e., we default to current year.
                return result
            except ValueError:
                pass

    # --- Jour de la semaine ("lundi", "mardi prochain", "lundi dernier") ---
    for day_name, day_idx in WEEKDAYS_FR.items():
        if day_name in text:
            current_dow = today.weekday()
            diff = (day_idx - current_dow) % 7
            if "dernier" in text or "passé" in text:
                diff = diff - 7 if diff == 0 else -(7 - diff)
            elif "prochain" in text:
                diff = diff if diff > 0 else diff + 7
            else:
                # Par défaut: le plus proche dans le passé
                diff = diff if diff == 0 else diff - 7
            return today + timedelta(days=diff)

    # --- "ce mois" / "mois courant" ---
    if re.search(r"\bce mois\b|\bmois courant\b", text):
        return today.replace(day=1)

    # --- "le mois dernier" / "mois précédent" ---
    if re.search(r"\bmois dernier\b|\bmois précédent\b|\bmois precedent\b", text):
        first_this = today.replace(day=1)
        last_month_last_day = first_this - timedelta(days=1)
        return last_month_last_day.replace(day=1)

    return None


def date_range_for_expression(text: str, reference: Optional[date] = None):
    """
    Retourne (date_debut, date_fin) pour des expressions de période.

    Exemples :
        "cette semaine" → (lundi, dimanche)
        "la semaine dernière" → (lundi_passé, dimanche_passé)
        "ce mois" → (1er du mois, fin du mois)
        "aujourd'hui" → (today, today)
    """
    today = reference or date.today()
    text = text.strip().lower()

    if "cette semaine" in text:
        monday = today - timedelta(days=today.weekday())
        sunday = monday + timedelta(days=6)
        return monday, sunday

    if "semaine dernière" in text or "semaine passée" in text or "semaine precedente" in text:
        monday = today - timedelta(days=today.weekday() + 7)
        sunday = monday + timedelta(days=6)
        return monday, sunday

    if "ce mois" in text or "mois courant" in text:
        first = today.replace(day=1)
        # Dernier jour du mois
        if today.month == 12:
            last = today.replace(month=12, day=31)
        else:
            last = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
        return first, last

    if "mois dernier" in text or "mois précédent" in text or "mois precedent" in text:
        first_this = today.replace(day=1)
        last_prev = first_this - timedelta(days=1)
        first_prev = last_prev.replace(day=1)
        return first_prev, last_prev

    # Fallback: single-day expression
    d = parse_french_date(text, reference)
    if d:
        return d, d
    return None, None


# ---------------------------------------------------------------------------
# Montants & quantités — normalisation
# ---------------------------------------------------------------------------

def parse_amount(text: Any) -> float:
    """
    Convertit un texte de montant/quantité en float propre.

    Accepte :
        "45 000 DA", "1 500,50 DZD", "45k", "1.5 kg",
        "3 500,00", "3500.00", 3500, 3500.0

    Retourne 0.0 si impossible de parser.
    """
    if text is None:
        return 0.0
    if isinstance(text, (int, float)):
        return float(text)

    s = str(text).strip().lower()

    # Supprimer les suffixes connus
    suffixes_to_strip = [
        "da", "dzd", "da.", "dzd.", "dinar", "dinars",
        "kg", "kgs", "g", "litre", "litres", "l",
        "sac", "sacs", "q", "quintal", "quintaux",
        "u", "unité", "unites", "pièce", "pieces",
        "€", "$", "eur", "usd",
    ]
    for suf in suffixes_to_strip:
        if s.endswith(suf):
            s = s[: -len(suf)].strip()

    # Gérer "k" (milliers)
    multiplier = 1.0
    if s.endswith("k"):
        s = s[:-1].strip()
        multiplier = 1000.0
    elif s.endswith("m") and len(s) > 1:
        s = s[:-1].strip()
        multiplier = 1_000_000.0

    # Clean whitespace
    s = re.sub(r"\s", "", s)  # Remove all spaces

    # Determine decimal/thousands separators:
    # Case 1: "3.500,00" → dot before comma → dot = thousands, comma = decimal
    # Case 2: "3,500.00" → comma before dot → comma = thousands, dot = decimal
    # Case 3: "1,5" or "1.5" → simple decimal

    dot_pos = s.rfind(".")
    comma_pos = s.rfind(",")

    if dot_pos != -1 and comma_pos != -1:
        if dot_pos < comma_pos:
            # "3.500,50" — dot is thousands sep, comma is decimal sep
            s = s.replace(".", "").replace(",", ".")
        else:
            # "3,500.50" — comma is thousands sep, dot is decimal sep
            s = s.replace(",", "")
    elif comma_pos != -1 and dot_pos == -1:
        # Only comma: check if it's a decimal or thousands separator
        parts = s.split(",")
        if len(parts) == 2 and len(parts[1]) <= 2:
            # "1500,50" → decimal
            s = s.replace(",", ".")
        else:
            # "1,500,000" → thousands
            s = s.replace(",", "")
    elif s.count(".") > 1:
        # "1.500.000" → multiple dots, all thousands separators
        parts = s.rsplit(".", 1)
        s = parts[0].replace(".", "") + "." + parts[1]

    try:
        return float(s) * multiplier
    except ValueError:
        return 0.0


# ---------------------------------------------------------------------------
# Recherche floue — clients / produits
# ---------------------------------------------------------------------------

def fuzzy_search_clients(name: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Recherche des clients par nom (insensible à la casse, correspondance partielle).

    Retourne une liste de dicts : {id, name, phone, current_debt}
    """
    from app.core.db_helpers import db_manager
    try:
        rows = db_manager.query_db(
            """SELECT id, name, phone,
                      COALESCE((SELECT SUM(balance_due) FROM sales WHERE client_id = c.id), 0) AS current_debt
               FROM clients c
               WHERE lower(name) LIKE %s
               ORDER BY name ASC
               LIMIT %s""",
            (f"%{name.lower()}%", limit),
        )
        results = []
        for r in rows:
            try:
                results.append(dict(r))
            except Exception:
                results.append({
                    "id": r[0], "name": r[1], "phone": r[2], "current_debt": float(r[3] or 0)
                })
        return results
    except Exception as e:
        logger.error("fuzzy_search_clients error: %s", e)
        return []


def fuzzy_search_products(name: str, kind: str = "all", limit: int = 5) -> List[Dict[str, Any]]:
    """
    Recherche des produits par nom.

    Args:
        kind: "all", "finished", ou "raw"
    
    Retourne une liste de dicts : {id, name, kind, unit, stock_qty, sale_price, avg_cost}
    """
    from app.core.db_helpers import db_manager
    results: List[Dict[str, Any]] = []
    pattern = f"%{name.lower()}%"

    try:
        if kind in ("all", "finished"):
            rows = db_manager.query_db(
                """SELECT id, name, 'finished' AS kind, default_unit AS unit,
                          stock_qty, sale_price, avg_cost
                   FROM finished_products
                   WHERE lower(name) LIKE %s
                   ORDER BY name ASC
                   LIMIT %s""",
                (pattern, limit),
            )
            for r in rows:
                try:
                    results.append(dict(r))
                except Exception:
                    results.append({
                        "id": r[0], "name": r[1], "kind": r[2], "unit": r[3],
                        "stock_qty": float(r[4] or 0), "sale_price": float(r[5] or 0),
                        "avg_cost": float(r[6] or 0),
                    })

        if kind in ("all", "raw"):
            rows = db_manager.query_db(
                """SELECT id, name, 'raw' AS kind, unit,
                          stock_qty, sale_price, avg_cost
                   FROM raw_materials
                   WHERE lower(name) LIKE %s
                   ORDER BY name ASC
                   LIMIT %s""",
                (pattern, limit),
            )
            for r in rows:
                try:
                    results.append(dict(r))
                except Exception:
                    results.append({
                        "id": r[0], "name": r[1], "kind": r[2], "unit": r[3],
                        "stock_qty": float(r[4] or 0), "sale_price": float(r[5] or 0),
                        "avg_cost": float(r[6] or 0),
                    })

        return results[:limit]
    except Exception as e:
        logger.error("fuzzy_search_products error: %s", e)
        return []


# ---------------------------------------------------------------------------
# Enum / valeurs autorisées
# ---------------------------------------------------------------------------

ENUM_VALUES: Dict[str, Dict[str, List[str]]] = {
    "expenses": {
        "category": [
            "general", "transport", "fournitures", "loyer", "salaires",
            "maintenance", "telecom", "energie", "impots", "autre",
        ],
        "payment_method": ["cash", "cheque", "virement", "autre"],
    },
    "payments": {
        "payment_type": ["versement", "avance"],
    },
    "supplier_payments": {
        "payment_type": ["versement", "avance"],
    },
    "sales": {
        "sale_type": ["cash", "credit"],
    },
    "raw_sales": {
        "sale_type": ["cash", "credit"],
    },
    "stock_movements": {
        "direction": ["in", "out"],
        "item_kind": ["raw", "finished"],
        "reference_type": ["purchase", "sale", "raw_sale", "production"],
    },
}


def get_enum_values(table: str, column: str) -> Dict[str, Any]:
    """
    Retourne les valeurs acceptées pour un champ restrictif (enum).

    Retourne {"values": [...]} ou {"error": "..."} si inconnu.
    """
    table = table.lower().strip()
    column = column.lower().strip()
    table_enums = ENUM_VALUES.get(table)
    if table_enums is None:
        return {"error": f"Table '{table}' inconnue ou sans contrainte d'énumération."}
    values = table_enums.get(column)
    if values is None:
        return {"error": f"Colonne '{column}' de la table '{table}' sans contrainte d'énumération connue."}
    return {
        "table": table,
        "column": column,
        "values": values,
        "message": f"Valeurs acceptées pour {table}.{column} : {', '.join(values)}",
    }
