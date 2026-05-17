"""Endpoint de recherche globale - authentifié par session web (cookie)."""
from __future__ import annotations

import re
from datetime import date, datetime

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.core.db_access import query_db
from app.web.deps import get_current_user

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
      - MM/YYYY     →  05/2026
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

    # ── Détection de date ────────────────────────────────────────────────────
    exact_date = _parse_date_query(q)
    partial_date_like = _partial_date_like(q) if not exact_date else None

    if exact_date or partial_date_like:
        date_param = exact_date if exact_date else partial_date_like
        operator  = "=" if exact_date else "LIKE"

        # Ventes pour cette date
        sales = query_db(
            f"""SELECT s.id, s.sale_date, COALESCE(c.name, 'Comptoir') AS client_name,
                       f.name AS item_name, s.total, s.sale_type
                FROM sales s
                LEFT JOIN clients c ON c.id = s.client_id
                JOIN finished_products f ON f.id = s.finished_product_id
                WHERE s.sale_date {operator} ?
                UNION ALL
                SELECT rs.id, rs.sale_date, COALESCE(c.name, 'Comptoir') AS client_name,
                       r.name AS item_name, rs.total, rs.sale_type
                FROM raw_sales rs
                LEFT JOIN clients c ON c.id = rs.client_id
                JOIN raw_materials r ON r.id = rs.raw_material_id
                WHERE rs.sale_date {operator} ?
                ORDER BY sale_date DESC LIMIT 5""",
            (date_param, date_param),
        )
        for s in sales:
            total_fmt = f"{float(s['total'] or 0):,.0f} DA".replace(",", " ")
            results.append({
                "title": f"Vente — {s['client_name']}",
                "sub":   f"{s['item_name']} · {total_fmt} · {s['sale_date']}",
                "icon":  "bi-receipt",
                "type":  "Vente",
                "href":  "/sales",
            })

        # Achats pour cette date
        purchases = query_db(
            f"""SELECT p.id, p.purchase_date, COALESCE(s.name, 'Inconnu') AS supplier_name,
                       COALESCE(NULLIF(p.custom_item_name,''), r.name) AS material_name,
                       p.total
                FROM purchases p
                LEFT JOIN suppliers s ON s.id = p.supplier_id
                LEFT JOIN raw_materials r ON r.id = p.raw_material_id
                WHERE p.purchase_date {operator} ?
                ORDER BY p.purchase_date DESC LIMIT 4""",
            (date_param,),
        )
        for p in purchases:
            total_fmt = f"{float(p['total'] or 0):,.0f} DA".replace(",", " ")
            results.append({
                "title": f"Achat — {p['supplier_name']}",
                "sub":   f"{p['material_name']} · {total_fmt} · {p['purchase_date']}",
                "icon":  "bi-cart",
                "type":  "Achat",
                "href":  "/purchases",
            })

        # Paiements pour cette date
        payments = query_db(
            f"""SELECT p.id, p.payment_date, c.name AS client_name,
                       p.amount, p.payment_type
                FROM payments p
                JOIN clients c ON c.id = p.client_id
                WHERE p.payment_date {operator} ?
                ORDER BY p.payment_date DESC LIMIT 4""",
            (date_param,),
        )
        for p in payments:
            amount_fmt = f"{float(p['amount'] or 0):,.0f} DA".replace(",", " ")
            results.append({
                "title": f"Versement — {p['client_name']}",
                "sub":   f"{amount_fmt} · {p['payment_type']} · {p['payment_date']}",
                "icon":  "bi-cash-stack",
                "type":  "Paiement",
                "href":  "/payments",
            })

    # ── Recherche texte (clients, produits, fournisseurs) ───────────────────
    # Clients
    clients = query_db(
        """SELECT id, name, phone, address
           FROM clients
           WHERE LOWER(name) LIKE ? OR LOWER(COALESCE(phone,'')) LIKE ?
           ORDER BY name LIMIT 5""",
        (needle, needle),
    )
    for c in clients:
        results.append({
            "title": c["name"],
            "sub":   c["phone"] or c["address"] or "",
            "icon":  "bi-person",
            "type":  "Client",
            "href":  f"/contacts/clients/{c['id']}",
        })

    # Matières premières
    raws = query_db(
        """SELECT id, name, unit FROM raw_materials
           WHERE LOWER(name) LIKE ?
           ORDER BY name LIMIT 4""",
        (needle,),
    )
    for r in raws:
        results.append({
            "title": r["name"],
            "sub":   r["unit"] or "",
            "icon":  "bi-box",
            "type":  "Matière",
            "href":  "/catalog",
        })

    # Produits finis
    products = query_db(
        """SELECT id, name, default_unit AS unit FROM finished_products
           WHERE LOWER(name) LIKE ?
           ORDER BY name LIMIT 4""",
        (needle,),
    )
    for p in products:
        results.append({
            "title": p["name"],
            "sub":   p["unit"] or "",
            "icon":  "bi-box-seam",
            "type":  "Produit",
            "href":  "/catalog",
        })

    # Fournisseurs
    suppliers = query_db(
        """SELECT id, name, phone FROM suppliers
           WHERE LOWER(name) LIKE ? OR LOWER(COALESCE(phone,'')) LIKE ?
           ORDER BY name LIMIT 3""",
        (needle, needle),
    )
    for s in suppliers:
        results.append({
            "title": s["name"],
            "sub":   s["phone"] or "",
            "icon":  "bi-truck",
            "type":  "Fournisseur",
            "href":  f"/contacts/suppliers/{s['id']}",
        })

    return JSONResponse({"data": results})
