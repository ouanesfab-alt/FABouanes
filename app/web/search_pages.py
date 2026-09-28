"""Endpoint de recherche globale - authentifié par session web (cookie)."""

from __future__ import annotations

import logging
import re
from datetime import date

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import String, cast, func, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.async_db import get_async_session
from app.core.models import (
    Client,
    FinishedProduct,
    Payment,
    ProductionBatch,
    Purchase,
    RawMaterial,
    RawSale,
    Sale,
    Supplier,
)
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


# ── Recherche par Catégorie ──────────────────────────────────────────────────


async def _search_numeric_matches(db: AsyncSession, q: str, results: list) -> None:
    try:
        cleaned = q.replace(" ", "").replace(",", ".")
        amount_val = float(cleaned)
    except ValueError:
        return

    lo = amount_val * 0.95
    hi = amount_val * 1.05

    # 1. Ventes (finies et matières brutes)
    subq_sales = (
        select(
            func.coalesce(Client.name, "Comptoir").label("client_name"),
            FinishedProduct.name.label("item_name"),
            Sale.total,
            Sale.sale_date,
        )
        .select_from(Sale)
        .outerjoin(Client, Client.id == Sale.client_id)
        .join(FinishedProduct, FinishedProduct.id == Sale.finished_product_id)
        .where(Sale.total.between(lo, hi))
    )

    subq_raw_sales = (
        select(
            func.coalesce(Client.name, "Comptoir").label("client_name"),
            RawMaterial.name.label("item_name"),
            RawSale.total,
            RawSale.sale_date,
        )
        .select_from(RawSale)
        .outerjoin(Client, Client.id == RawSale.client_id)
        .join(RawMaterial, RawMaterial.id == RawSale.raw_material_id)
        .where(RawSale.total.between(lo, hi))
    )

    u = union_all(subq_sales, subq_raw_sales).subquery()
    stmt_sales = (
        select(u.c.client_name, u.c.item_name, u.c.total, u.c.sale_date).order_by(u.c.sale_date.desc()).limit(5)
    )
    try:
        res = await db.execute(stmt_sales)
        for row in res.mappings().all():
            fmt = f"{float(row['total'] or 0):,.0f} DA".replace(",", " ")
            results.append(
                {
                    "title": f"Vente — {row['client_name']}",
                    "sub": f"{row['item_name']} · {fmt} · {row['sale_date']}",
                    "icon": "bi-receipt",
                    "type": "Vente",
                    "href": "/sales",
                }
            )
    except Exception as exc:
        logger.warning("Numeric sales search failed: %s", exc)

    # 2. Achats
    stmt_purchases = (
        select(
            func.coalesce(Supplier.name, "Inconnu").label("supplier_name"),
            func.coalesce(func.nullif(Purchase.custom_item_name, ""), RawMaterial.name).label("material_name"),
            Purchase.total,
            Purchase.purchase_date,
        )
        .select_from(Purchase)
        .outerjoin(Supplier, Supplier.id == Purchase.supplier_id)
        .outerjoin(RawMaterial, RawMaterial.id == Purchase.raw_material_id)
        .where(Purchase.total.between(lo, hi))
        .order_by(Purchase.purchase_date.desc())
        .limit(4)
    )
    try:
        res = await db.execute(stmt_purchases)
        for row in res.mappings().all():
            fmt = f"{float(row['total'] or 0):,.0f} DA".replace(",", " ")
            results.append(
                {
                    "title": f"Achat — {row['supplier_name']}",
                    "sub": f"{row['material_name']} · {fmt} · {row['purchase_date']}",
                    "icon": "bi-cart",
                    "type": "Achat",
                    "href": "/purchases",
                }
            )
    except Exception as exc:
        logger.warning("Numeric purchases search failed: %s", exc)

    # 3. Versements
    stmt_payments = (
        select(Client.name.label("client_name"), Payment.amount, Payment.payment_type, Payment.payment_date)
        .select_from(Payment)
        .join(Client, Client.id == Payment.client_id)
        .where(Payment.amount.between(lo, hi))
        .order_by(Payment.payment_date.desc())
        .limit(4)
    )
    try:
        res = await db.execute(stmt_payments)
        for row in res.mappings().all():
            fmt = f"{float(row['amount'] or 0):,.0f} DA".replace(",", " ")
            results.append(
                {
                    "title": f"Versement — {row['client_name']}",
                    "sub": f"{fmt} · {row['payment_type']} · {row['payment_date']}",
                    "icon": "bi-cash-stack",
                    "type": "Paiement",
                    "href": "/payments",
                }
            )
    except Exception as exc:
        logger.warning("Numeric payments search failed: %s", exc)

    # 4. Production
    stmt_prod = (
        select(
            FinishedProduct.name.label("product_name"), ProductionBatch.output_quantity, ProductionBatch.production_date
        )
        .select_from(ProductionBatch)
        .join(FinishedProduct, FinishedProduct.id == ProductionBatch.finished_product_id)
        .where(ProductionBatch.output_quantity.between(lo, hi))
        .order_by(ProductionBatch.production_date.desc())
        .limit(4)
    )
    try:
        res = await db.execute(stmt_prod)
        for row in res.mappings().all():
            results.append(
                {
                    "title": f"Production — {row['product_name']}",
                    "sub": f"{int(row['output_quantity'] or 0)} unités · {row['production_date']}",
                    "icon": "bi-gear",
                    "type": "Production",
                    "href": "/production",
                }
            )
    except Exception as exc:
        logger.warning("Numeric production search failed: %s", exc)


async def _search_date_matches(db: AsyncSession, q: str, results: list) -> None:
    exact_date = _parse_date_query(q)
    partial_date_like = _partial_date_like(q) if not exact_date else None

    if not (exact_date or partial_date_like):
        return

    # Ventes
    if exact_date:
        cond_sale = cast(Sale.sale_date, String) == exact_date
        cond_raw = cast(RawSale.sale_date, String) == exact_date
        cond_pur = cast(Purchase.purchase_date, String) == exact_date
        cond_pay = cast(Payment.payment_date, String) == exact_date
    else:
        cond_sale = cast(Sale.sale_date, String).like(partial_date_like)
        cond_raw = cast(RawSale.sale_date, String).like(partial_date_like)
        cond_pur = cast(Purchase.purchase_date, String).like(partial_date_like)
        cond_pay = cast(Payment.payment_date, String).like(partial_date_like)

    s1 = (
        select(
            func.coalesce(Client.name, "Comptoir").label("client_name"),
            FinishedProduct.name.label("item_name"),
            Sale.total,
            Sale.sale_date,
        )
        .select_from(Sale)
        .outerjoin(Client, Client.id == Sale.client_id)
        .join(FinishedProduct, FinishedProduct.id == Sale.finished_product_id)
        .where(cond_sale)
    )

    s2 = (
        select(
            func.coalesce(Client.name, "Comptoir").label("client_name"),
            RawMaterial.name.label("item_name"),
            RawSale.total,
            RawSale.sale_date,
        )
        .select_from(RawSale)
        .outerjoin(Client, Client.id == RawSale.client_id)
        .join(RawMaterial, RawMaterial.id == RawSale.raw_material_id)
        .where(cond_raw)
    )

    u = union_all(s1, s2).subquery()
    stmt_sales = (
        select(u.c.client_name, u.c.item_name, u.c.total, u.c.sale_date).order_by(u.c.sale_date.desc()).limit(5)
    )
    try:
        res = await db.execute(stmt_sales)
        for row in res.mappings().all():
            fmt = f"{float(row['total'] or 0):,.0f} DA".replace(",", " ")
            results.append(
                {
                    "title": f"Vente — {row['client_name']}",
                    "sub": f"{row['item_name']} · {fmt} · {row['sale_date']}",
                    "icon": "bi-receipt",
                    "type": "Vente",
                    "href": "/sales",
                }
            )
    except Exception as exc:
        logger.warning("Date sales search failed: %s", exc)

    stmt_pur = (
        select(
            func.coalesce(Supplier.name, "Inconnu").label("supplier_name"),
            func.coalesce(func.nullif(Purchase.custom_item_name, ""), RawMaterial.name).label("material_name"),
            Purchase.total,
            Purchase.purchase_date,
        )
        .select_from(Purchase)
        .outerjoin(Supplier, Supplier.id == Purchase.supplier_id)
        .outerjoin(RawMaterial, RawMaterial.id == Purchase.raw_material_id)
        .where(cond_pur)
        .order_by(Purchase.purchase_date.desc())
        .limit(4)
    )
    try:
        res = await db.execute(stmt_pur)
        for row in res.mappings().all():
            fmt = f"{float(row['total'] or 0):,.0f} DA".replace(",", " ")
            results.append(
                {
                    "title": f"Achat — {row['supplier_name']}",
                    "sub": f"{row['material_name']} · {fmt} · {row['purchase_date']}",
                    "icon": "bi-cart",
                    "type": "Achat",
                    "href": "/purchases",
                }
            )
    except Exception as exc:
        logger.warning("Date purchases search failed: %s", exc)

    stmt_pay = (
        select(Client.name.label("client_name"), Payment.amount, Payment.payment_type, Payment.payment_date)
        .select_from(Payment)
        .join(Client, Client.id == Payment.client_id)
        .where(cond_pay)
        .order_by(Payment.payment_date.desc())
        .limit(4)
    )
    try:
        res = await db.execute(stmt_pay)
        for row in res.mappings().all():
            fmt = f"{float(row['amount'] or 0):,.0f} DA".replace(",", " ")
            results.append(
                {
                    "title": f"Versement — {row['client_name']}",
                    "sub": f"{fmt} · {row['payment_type']} · {row['payment_date']}",
                    "icon": "bi-cash-stack",
                    "type": "Paiement",
                    "href": "/payments",
                }
            )
    except Exception as exc:
        logger.warning("Date payments search failed: %s", exc)


async def _search_text_matches(db: AsyncSession, needle: str, results: list) -> None:
    try:
        res_clients = await db.execute(
            select(Client.id, Client.name, Client.phone, Client.address)
            .where(func.lower(Client.name).like(needle) | func.lower(func.coalesce(Client.phone, "")).like(needle))
            .order_by(Client.name)
            .limit(5)
        )
        for row in res_clients.mappings().all():
            results.append(
                {
                    "title": row["name"],
                    "sub": row["phone"] or row["address"] or "",
                    "icon": "bi-person",
                    "type": "Client",
                    "href": f"/contacts/clients/{row['id']}",
                }
            )
    except Exception as exc:
        logger.warning("Text clients search failed: %s", exc)

    try:
        res_suppliers = await db.execute(
            select(Supplier.id, Supplier.name, Supplier.phone)
            .where(func.lower(Supplier.name).like(needle) | func.lower(func.coalesce(Supplier.phone, "")).like(needle))
            .order_by(Supplier.name)
            .limit(3)
        )
        for row in res_suppliers.mappings().all():
            results.append(
                {
                    "title": row["name"],
                    "sub": row["phone"] or "",
                    "icon": "bi-truck",
                    "type": "Fournisseur",
                    "href": f"/contacts/suppliers/{row['id']}",
                }
            )
    except Exception as exc:
        logger.warning("Text suppliers search failed: %s", exc)

    try:
        res_raw = await db.execute(
            select(RawMaterial.id, RawMaterial.name, RawMaterial.unit)
            .where(func.lower(RawMaterial.name).like(needle))
            .order_by(RawMaterial.name)
            .limit(4)
        )
        for row in res_raw.mappings().all():
            results.append(
                {
                    "title": row["name"],
                    "sub": row["unit"] or "",
                    "icon": "bi-box",
                    "type": "Matière",
                    "href": "/catalog",
                }
            )
    except Exception as exc:
        logger.warning("Text raw materials search failed: %s", exc)

    try:
        res_finished = await db.execute(
            select(FinishedProduct.id, FinishedProduct.name, FinishedProduct.default_unit.label("unit"))
            .where(func.lower(FinishedProduct.name).like(needle))
            .order_by(FinishedProduct.name)
            .limit(4)
        )
        for row in res_finished.mappings().all():
            results.append(
                {
                    "title": row["name"],
                    "sub": row["unit"] or "",
                    "icon": "bi-box-seam",
                    "type": "Produit",
                    "href": "/catalog",
                }
            )
    except Exception as exc:
        logger.warning("Text finished products search failed: %s", exc)

    try:
        s1 = (
            select(
                func.coalesce(Client.name, "Comptoir").label("client_name"),
                FinishedProduct.name.label("item_name"),
                Sale.total,
                Sale.sale_date,
            )
            .select_from(Sale)
            .outerjoin(Client, Client.id == Sale.client_id)
            .join(FinishedProduct, FinishedProduct.id == Sale.finished_product_id)
            .where(
                func.lower(func.coalesce(Client.name, "")).like(needle) | func.lower(FinishedProduct.name).like(needle)
            )
        )
        s2 = (
            select(
                func.coalesce(Client.name, "Comptoir").label("client_name"),
                RawMaterial.name.label("item_name"),
                RawSale.total,
                RawSale.sale_date,
            )
            .select_from(RawSale)
            .outerjoin(Client, Client.id == RawSale.client_id)
            .join(RawMaterial, RawMaterial.id == RawSale.raw_material_id)
            .where(func.lower(func.coalesce(Client.name, "")).like(needle) | func.lower(RawMaterial.name).like(needle))
        )
        u = union_all(s1, s2).subquery()
        res_sales = await db.execute(
            select(u.c.client_name, u.c.item_name, u.c.total, u.c.sale_date).order_by(u.c.sale_date.desc()).limit(5)
        )
        for row in res_sales.mappings().all():
            fmt = f"{float(row['total'] or 0):,.0f} DA".replace(",", " ")
            results.append(
                {
                    "title": f"Vente — {row['client_name']}",
                    "sub": f"{row['item_name']} · {fmt} · {row['sale_date']}",
                    "icon": "bi-receipt",
                    "type": "Vente",
                    "href": "/sales",
                }
            )
    except Exception as exc:
        logger.warning("Text sales search failed: %s", exc)

    try:
        res_purchases = await db.execute(
            select(
                func.coalesce(Supplier.name, "Inconnu").label("supplier_name"),
                func.coalesce(func.nullif(Purchase.custom_item_name, ""), RawMaterial.name).label("material_name"),
                Purchase.total,
                Purchase.purchase_date,
            )
            .select_from(Purchase)
            .outerjoin(Supplier, Supplier.id == Purchase.supplier_id)
            .outerjoin(RawMaterial, RawMaterial.id == Purchase.raw_material_id)
            .where(
                func.lower(func.coalesce(Supplier.name, "")).like(needle)
                | func.lower(func.coalesce(RawMaterial.name, "")).like(needle)
                | func.lower(func.coalesce(Purchase.custom_item_name, "")).like(needle)
            )
            .order_by(Purchase.purchase_date.desc())
            .limit(4)
        )
        for row in res_purchases.mappings().all():
            fmt = f"{float(row['total'] or 0):,.0f} DA".replace(",", " ")
            results.append(
                {
                    "title": f"Achat — {row['supplier_name']}",
                    "sub": f"{row['material_name']} · {fmt} · {row['purchase_date']}",
                    "icon": "bi-cart",
                    "type": "Achat",
                    "href": "/purchases",
                }
            )
    except Exception as exc:
        logger.warning("Text purchases search failed: %s", exc)

    try:
        res_prod = await db.execute(
            select(
                FinishedProduct.name.label("product_name"),
                ProductionBatch.output_quantity,
                ProductionBatch.production_date,
            )
            .select_from(ProductionBatch)
            .join(FinishedProduct, FinishedProduct.id == ProductionBatch.finished_product_id)
            .where(func.lower(FinishedProduct.name).like(needle))
            .order_by(ProductionBatch.production_date.desc())
            .limit(4)
        )
        for row in res_prod.mappings().all():
            results.append(
                {
                    "title": f"Production — {row['product_name']}",
                    "sub": f"{int(row['output_quantity'] or 0)} unités · {row['production_date']}",
                    "icon": "bi-gear",
                    "type": "Production",
                    "href": "/production",
                }
            )
    except Exception as exc:
        logger.warning("Text production search failed: %s", exc)

    try:
        res_payments = await db.execute(
            select(Client.name.label("client_name"), Payment.amount, Payment.payment_type, Payment.payment_date)
            .select_from(Payment)
            .join(Client, Client.id == Payment.client_id)
            .where(func.lower(Client.name).like(needle))
            .order_by(Payment.payment_date.desc())
            .limit(4)
        )
        for row in res_payments.mappings().all():
            fmt = f"{float(row['amount'] or 0):,.0f} DA".replace(",", " ")
            results.append(
                {
                    "title": f"Versement — {row['client_name']}",
                    "sub": f"{fmt} · {row['payment_type']} · {row['payment_date']}",
                    "icon": "bi-cash-stack",
                    "type": "Paiement",
                    "href": "/payments",
                }
            )
    except Exception as exc:
        logger.warning("Text payments search failed: %s", exc)


# ── Endpoint ──────────────────────────────────────────────────────────────────


@router.get("/api/search", name="global_search")
async def global_search(
    request: Request,
    db: AsyncSession = Depends(get_async_session),
):
    """Recherche globale par session web (pas de token Bearer requis)."""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"data": []}, status_code=401)

    q = request.query_params.get("q", "").strip()
    if len(q) < 2:
        return JSONResponse({"data": []})

    results = []
    needle = f"%{q.lower()}%"

    await _search_numeric_matches(db, q, results)
    await _search_date_matches(db, q, results)
    await _search_text_matches(db, needle, results)

    return JSONResponse({"data": results})
