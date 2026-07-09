"""Endpoint de recherche globale - authentifié par session web (cookie)."""
from __future__ import annotations

import re
import logging
from datetime import date

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.core.db_helpers import query_db
from app.web.deps import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Helpers ──────────────────────────────────────────────────────────────────

def _parse_date_query(q: str) -> str | None:
    """
    Détecte si la requête ressemble à une date et la convertit en YYYY-MM-DD.
    Formats acceptés :
      - YYYY-MM-DD  →  2026-05-17
      - DD/MM/YYYY  →  17/05/2026
      - DD/MM/YY    →  17/05/26
      - DD/MM       →  17/05  (année courante)
    Retourne None si la chaîne n'est pas une date.
    """
    q = q.strip()
    today = date.today()

    # YYYY-MM-DD
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", q)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
        except ValueError:
            pass

    # DD/MM/YYYY
    m = re.fullmatch(r"(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{4})", q)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat()
        except ValueError:
            pass

    # DD/MM/YY
    m = re.fullmatch(r"(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{2})", q)
    if m:
        try:
            year = 2000 + int(m.group(3))
            return date(year, int(m.group(2)), int(m.group(1))).isoformat()
        except ValueError:
            pass

    # DD/MM  (année courante)
    m = re.fullmatch(r"(\d{1,2})[/\-\.](\d{1,2})", q)
    if m:
        try:
            return date(today.year, int(m.group(2)), int(m.group(1))).isoformat()
        except ValueError:
            pass

    return None


def _partial_date_like(q: str) -> str | None:
    """
    Détecte une date partielle (mois/année) et retourne un LIKE pattern pour SQL.
    Ex: '05/2026' → '2026-05-%'
    """
    m = re.fullmatch(r"(\d{1,2})[/\-\.](\d{4})", q.strip())
    if m:
        return f"{m.group(2)}-{int(m.group(1)):02d}-%"
    # Année seule ex: '2026'
    m = re.fullmatch(r"(\d{4})", q.strip())
    if m:
        return f"{m.group(1)}-%"
    return None


def _safe_query(sql: str, params: tuple) -> list:
    """Wrapper autour de query_db qui retourne [] en cas d'erreur SQL."""
    try:
        result = query_db(sql, params)
        return result or []
    except Exception as exc:
        logger.warning("Search query failed: %s | params=%s | err=%s", sql[:120], params, exc)
        return []


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.get("/api/search", name="global_search")
async def global_search(request: Request):
    """Recherche globale par session web (pas de token Bearer requis)."""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"data": []}, status_code=401)

    q = request.query_params.get("q", "").strip()
    if len(q) < 2:
        return JSONResponse({"data": []})

    needle = f"%{q.lower()}%"
    results = []

    # ── Détection d'un montant / quantité ────────────────────────────────────
    amount_val = None
    try:
        cleaned = q.replace(" ", "").replace(",", ".")
        amount_val = float(cleaned)
    except ValueError:
        pass

    if amount_val is not None:
        lo = amount_val * 0.95
        hi = amount_val * 1.05

        # Ventes par montant (produits finis + matières)
        for row in _safe_query(
            """SELECT client_name, item_name, total, sale_date FROM (
                SELECT COALESCE(c.name, 'Comptoir') AS client_name,
                       f.name AS item_name, s.total, s.sale_date
                FROM sales s
                LEFT JOIN clients c ON c.id = s.client_id
                JOIN finished_products f ON f.id = s.finished_product_id
                WHERE s.total BETWEEN %s AND %s
                UNION ALL
                SELECT COALESCE(c.name, 'Comptoir') AS client_name,
                       r.name AS item_name, rs.total, rs.sale_date
                FROM raw_sales rs
                LEFT JOIN clients c ON c.id = rs.client_id
                JOIN raw_materials r ON r.id = rs.raw_material_id
                WHERE rs.total BETWEEN %s AND %s
            ) t ORDER BY sale_date DESC LIMIT 5""",
            (lo, hi, lo, hi),
        ):
            fmt = f"{float(row['total'] or 0):,.0f} DA".replace(",", " ")
            results.append({"title": f"Vente — {row['client_name']}", "sub": f"{row['item_name']} · {fmt} · {row['sale_date']}", "icon": "bi-receipt", "type": "Vente", "href": "/sales"})

        # Achats par montant
        for row in _safe_query(
            """SELECT COALESCE(s.name,'Inconnu') AS supplier_name,
                      COALESCE(NULLIF(p.custom_item_name,''), r.name) AS material_name,
                      p.total, p.purchase_date
               FROM purchases p
               LEFT JOIN suppliers s ON s.id = p.supplier_id
               LEFT JOIN raw_materials r ON r.id = p.raw_material_id
               WHERE p.total BETWEEN %s AND %s
               ORDER BY p.purchase_date DESC LIMIT 4""",
            (lo, hi),
        ):
            fmt = f"{float(row['total'] or 0):,.0f} DA".replace(",", " ")
            results.append({"title": f"Achat — {row['supplier_name']}", "sub": f"{row['material_name']} · {fmt} · {row['purchase_date']}", "icon": "bi-cart", "type": "Achat", "href": "/purchases"})

        # Paiements par montant
        for row in _safe_query(
            """SELECT c.name AS client_name, p.amount, p.payment_type, p.payment_date
               FROM payments p
               JOIN clients c ON c.id = p.client_id
               WHERE p.amount BETWEEN %s AND %s
               ORDER BY p.payment_date DESC LIMIT 4""",
            (lo, hi),
        ):
            fmt = f"{float(row['amount'] or 0):,.0f} DA".replace(",", " ")
            results.append({"title": f"Versement — {row['client_name']}", "sub": f"{fmt} · {row['payment_type']} · {row['payment_date']}", "icon": "bi-cash-stack", "type": "Paiement", "href": "/payments"})

        # Productions par quantité
        for row in _safe_query(
            """SELECT f.name AS product_name, pb.output_quantity, pb.production_date
               FROM production_batches pb
               JOIN finished_products f ON f.id = pb.finished_product_id
               WHERE pb.output_quantity BETWEEN %s AND %s
               ORDER BY pb.production_date DESC LIMIT 4""",
            (lo, hi),
        ):
            results.append({"title": f"Production — {row['product_name']}", "sub": f"{int(row['output_quantity'] or 0)} unités · {row['production_date']}", "icon": "bi-gear", "type": "Production", "href": "/production"})

    # ── Détection de date ────────────────────────────────────────────────────
    exact_date = _parse_date_query(q)
    partial_date_like = _partial_date_like(q) if not exact_date else None

    if exact_date or partial_date_like:
        date_param = exact_date if exact_date else partial_date_like
        operator = "=" if exact_date else "LIKE"

        # Ventes par date
        for row in _safe_query(
            f"""SELECT client_name, item_name, total, sale_date FROM (
                SELECT COALESCE(c.name, 'Comptoir') AS client_name,
                       f.name AS item_name, s.total, s.sale_date
                FROM sales s
                LEFT JOIN clients c ON c.id = s.client_id
                JOIN finished_products f ON f.id = s.finished_product_id
                WHERE CAST(s.sale_date AS TEXT) {operator} %s
                UNION ALL
                SELECT COALESCE(c.name, 'Comptoir') AS client_name,
                       r.name AS item_name, rs.total, rs.sale_date
                FROM raw_sales rs
                LEFT JOIN clients c ON c.id = rs.client_id
                JOIN raw_materials r ON r.id = rs.raw_material_id
                WHERE CAST(rs.sale_date AS TEXT) {operator} %s
            ) t ORDER BY sale_date DESC LIMIT 5""",
            (date_param, date_param),
        ):
            fmt = f"{float(row['total'] or 0):,.0f} DA".replace(",", " ")
            results.append({"title": f"Vente — {row['client_name']}", "sub": f"{row['item_name']} · {fmt} · {row['sale_date']}", "icon": "bi-receipt", "type": "Vente", "href": "/sales"})

        # Achats par date
        for row in _safe_query(
            f"""SELECT COALESCE(s.name, 'Inconnu') AS supplier_name,
                      COALESCE(NULLIF(p.custom_item_name,''), r.name) AS material_name,
                      p.total, p.purchase_date
               FROM purchases p
               LEFT JOIN suppliers s ON s.id = p.supplier_id
               LEFT JOIN raw_materials r ON r.id = p.raw_material_id
               WHERE CAST(p.purchase_date AS TEXT) {operator} %s
               ORDER BY p.purchase_date DESC LIMIT 4""",
            (date_param,),
        ):
            fmt = f"{float(row['total'] or 0):,.0f} DA".replace(",", " ")
            results.append({"title": f"Achat — {row['supplier_name']}", "sub": f"{row['material_name']} · {fmt} · {row['purchase_date']}", "icon": "bi-cart", "type": "Achat", "href": "/purchases"})

        # Paiements par date
        for row in _safe_query(
            f"""SELECT c.name AS client_name, p.amount, p.payment_type, p.payment_date
               FROM payments p
               JOIN clients c ON c.id = p.client_id
               WHERE CAST(p.payment_date AS TEXT) {operator} %s
               ORDER BY p.payment_date DESC LIMIT 4""",
            (date_param,),
        ):
            fmt = f"{float(row['amount'] or 0):,.0f} DA".replace(",", " ")
            results.append({"title": f"Versement — {row['client_name']}", "sub": f"{fmt} · {row['payment_type']} · {row['payment_date']}", "icon": "bi-cash-stack", "type": "Paiement", "href": "/payments"})

    # ── Recherche texte ───────────────────────────────────────────────────────

    # Clients
    for row in _safe_query(
        """SELECT id, name, phone, address FROM clients
           WHERE LOWER(name) LIKE %s OR LOWER(COALESCE(phone,'')) LIKE %s
           ORDER BY name LIMIT 5""",
        (needle, needle),
    ):
        results.append({"title": row["name"], "sub": row["phone"] or row["address"] or "", "icon": "bi-person", "type": "Client", "href": f"/contacts/clients/{row['id']}"})

    # Fournisseurs
    for row in _safe_query(
        """SELECT id, name, phone FROM suppliers
           WHERE LOWER(name) LIKE %s OR LOWER(COALESCE(phone,'')) LIKE %s
           ORDER BY name LIMIT 3""",
        (needle, needle),
    ):
        results.append({"title": row["name"], "sub": row["phone"] or "", "icon": "bi-truck", "type": "Fournisseur", "href": f"/contacts/suppliers/{row['id']}"})

    # Matières premières
    for row in _safe_query(
        """SELECT id, name, unit FROM raw_materials
           WHERE LOWER(name) LIKE %s ORDER BY name LIMIT 4""",
        (needle,),
    ):
        results.append({"title": row["name"], "sub": row["unit"] or "", "icon": "bi-box", "type": "Matière", "href": "/catalog"})

    # Produits finis
    for row in _safe_query(
        """SELECT id, name, default_unit AS unit FROM finished_products
           WHERE LOWER(name) LIKE %s ORDER BY name LIMIT 4""",
        (needle,),
    ):
        results.append({"title": row["name"], "sub": row["unit"] or "", "icon": "bi-box-seam", "type": "Produit", "href": "/catalog"})

    # Ventes par nom client ou produit
    for row in _safe_query(
        """SELECT client_name, item_name, total, sale_date FROM (
            SELECT COALESCE(c.name, 'Comptoir') AS client_name,
                   f.name AS item_name, s.total, s.sale_date
            FROM sales s
            LEFT JOIN clients c ON c.id = s.client_id
            JOIN finished_products f ON f.id = s.finished_product_id
            WHERE LOWER(COALESCE(c.name, '')) LIKE %s OR LOWER(f.name) LIKE %s
            UNION ALL
            SELECT COALESCE(c.name, 'Comptoir') AS client_name,
                   r.name AS item_name, rs.total, rs.sale_date
            FROM raw_sales rs
            LEFT JOIN clients c ON c.id = rs.client_id
            JOIN raw_materials r ON r.id = rs.raw_material_id
            WHERE LOWER(COALESCE(c.name, '')) LIKE %s OR LOWER(r.name) LIKE %s
        ) t ORDER BY sale_date DESC LIMIT 5""",
        (needle, needle, needle, needle),
    ):
        fmt = f"{float(row['total'] or 0):,.0f} DA".replace(",", " ")
        results.append({"title": f"Vente — {row['client_name']}", "sub": f"{row['item_name']} · {fmt} · {row['sale_date']}", "icon": "bi-receipt", "type": "Vente", "href": "/sales"})

    # Achats par nom fournisseur ou matière
    for row in _safe_query(
        """SELECT COALESCE(s.name,'Inconnu') AS supplier_name,
                  COALESCE(NULLIF(p.custom_item_name,''), r.name) AS material_name,
                  p.total, p.purchase_date
           FROM purchases p
           LEFT JOIN suppliers s ON s.id = p.supplier_id
           LEFT JOIN raw_materials r ON r.id = p.raw_material_id
           WHERE LOWER(COALESCE(s.name,'')) LIKE %s
              OR LOWER(COALESCE(r.name,'')) LIKE %s
              OR LOWER(COALESCE(p.custom_item_name,'')) LIKE %s
           ORDER BY p.purchase_date DESC LIMIT 4""",
        (needle, needle, needle),
    ):
        fmt = f"{float(row['total'] or 0):,.0f} DA".replace(",", " ")
        results.append({"title": f"Achat — {row['supplier_name']}", "sub": f"{row['material_name']} · {fmt} · {row['purchase_date']}", "icon": "bi-cart", "type": "Achat", "href": "/purchases"})

    # Productions par nom de produit (table correcte : production_batches)
    for row in _safe_query(
        """SELECT f.name AS product_name, pb.output_quantity, pb.production_date
           FROM production_batches pb
           JOIN finished_products f ON f.id = pb.finished_product_id
           WHERE LOWER(f.name) LIKE %s
           ORDER BY pb.production_date DESC LIMIT 4""",
        (needle,),
    ):
        results.append({"title": f"Production — {row['product_name']}", "sub": f"{int(row['output_quantity'] or 0)} unités · {row['production_date']}", "icon": "bi-gear", "type": "Production", "href": "/production"})

    # Paiements par nom de client
    for row in _safe_query(
        """SELECT c.name AS client_name, p.amount, p.payment_type, p.payment_date
           FROM payments p
           JOIN clients c ON c.id = p.client_id
           WHERE LOWER(c.name) LIKE %s
           ORDER BY p.payment_date DESC LIMIT 4""",
        (needle,),
    ):
        fmt = f"{float(row['amount'] or 0):,.0f} DA".replace(",", " ")
        results.append({"title": f"Versement — {row['client_name']}", "sub": f"{fmt} · {row['payment_type']} · {row['payment_date']}", "icon": "bi-cash-stack", "type": "Paiement", "href": "/payments"})

    return JSONResponse({"data": results})
