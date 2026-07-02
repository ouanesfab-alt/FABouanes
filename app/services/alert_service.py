from __future__ import annotations

from datetime import date, timedelta, datetime
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.async_db import get_async_sessionmaker
from app.core.helpers import async_compat
from app.core.models import StockAlert, RawMaterial, FinishedProduct
from app.core.websockets import manager
import json
import logging

logger = logging.getLogger("fabouanes.alerts")

DEFAULT_OVERDUE_DAYS = 30


@async_compat
async def check_overdue_clients(
    overdue_days: int = DEFAULT_OVERDUE_DAYS,
    db: AsyncSession | None = None,
) -> list[dict]:
    """
    Retourne les clients avec balance > 0 et aucune opération
    depuis plus de `overdue_days` jours.
    """
    if db is None:
        async with get_async_sessionmaker()() as session:
            return await _check_overdue_clients_impl(overdue_days, session)
    return await _check_overdue_clients_impl(overdue_days, db)


async def _check_overdue_clients_impl(overdue_days: int, db: AsyncSession) -> list[dict]:
    cutoff = (date.today() - timedelta(days=overdue_days)).isoformat()
    res = await db.execute(
        text("""
        SELECT
            c.id, c.name, c.current_balance AS balance,
            MAX(ch.operation_date) AS derniere_operation,
            DATE_PART('day', NOW() - MAX(ch.operation_date)) AS jours_inactif
        FROM clients_with_stats c
        LEFT JOIN client_history ch ON ch.client_id = c.id
        WHERE c.current_balance > 0
        GROUP BY c.id, c.name, c.current_balance
        HAVING MAX(ch.operation_date) < :cutoff
            OR MAX(ch.operation_date) IS NULL
        ORDER BY c.current_balance DESC
        LIMIT 50
        """),
        {"cutoff": cutoff},
    )
    return [dict(row._mapping) for row in res.all()]


@async_compat
async def broadcast_overdue_alerts(db: AsyncSession | None = None) -> int:
    """
    Vérifie les clients en retard et diffuse une alerte WebSocket.
    Retourne le nombre de clients en retard détectés.
    Appelé quotidiennement par le scheduler.
    """
    if db is None:
        async with get_async_sessionmaker()() as session:
            res = await _broadcast_overdue_alerts_impl(session)
            await session.commit()
            return res
    return await _broadcast_overdue_alerts_impl(db)


async def _broadcast_overdue_alerts_impl(db: AsyncSession) -> int:
    # Essaye d'obtenir un verrou consultatif transactionnel (advisory lock)
    # pour éviter les exécutions multiples concurrentes (par exemple avec plusieurs workers Gunicorn)
    locked_res = await db.execute(text("SELECT pg_try_advisory_xact_lock(48216732) AS locked"))
    locked_row = locked_res.first()
    if not locked_row or not locked_row.locked:
        logger.info("Verrou consultatif déjà détenu par un autre worker. Tâche ignorée.")
        return 0

    overdue = await _check_overdue_clients_impl(DEFAULT_OVERDUE_DAYS, db)
    if overdue:
        payload = json.dumps({
            "type": "overdue_alert",
            "count": len(overdue),
            "clients": [
                {"id": r["id"], "name": r["name"],
                 "balance": float(r["balance"]),
                 "jours": int(r["jours_inactif"] or 0)}
                for r in overdue
            ],
        })
        manager.broadcast_sync(payload)
        logger.info("Alerte : clients en retard.", extra={"count": len(overdue)})
    return len(overdue)


@async_compat
async def check_stock_alerts(db: AsyncSession | None = None) -> None:
    """Vérifie le stock de matières premières et de produits finis par rapport au seuil."""
    if db is None:
        async with get_async_sessionmaker()() as session:
            await _check_stock_alerts_impl(session)
            await session.commit()
            return
    await _check_stock_alerts_impl(db)


async def _check_stock_alerts_impl(db: AsyncSession) -> None:
    # Pre-fetch all active (unacknowledged) alerts from the last 24h in one query
    # to avoid N individual SELECT queries inside the loop.
    active_rows_res = await db.execute(
        select(StockAlert.product_type, StockAlert.product_id)
        .where(
            StockAlert.acknowledged_at == None,
            StockAlert.triggered_at > func.now() - text("INTERVAL '24 hours'")
        )
    )
    active_alerts: set[tuple[str, int]] = {
        (row.product_type, int(row.product_id)) for row in active_rows_res.all()
    }

    # Matières premières
    raws_res = await db.execute(
        select(RawMaterial.id, RawMaterial.name, RawMaterial.stock_qty, RawMaterial.alert_threshold)
        .where(RawMaterial.stock_qty <= RawMaterial.alert_threshold, RawMaterial.alert_threshold > 0)
    )
    for row in raws_res.all():
        await _trigger_alert("raw_material", int(row.id), row.name, row.stock_qty, row.alert_threshold, active_alerts, db=db)

    # Produits finis
    products_res = await db.execute(
        select(FinishedProduct.id, FinishedProduct.name, FinishedProduct.stock_qty, FinishedProduct.alert_threshold)
        .where(FinishedProduct.stock_qty <= FinishedProduct.alert_threshold, FinishedProduct.alert_threshold > 0)
    )
    for row in products_res.all():
        await _trigger_alert("finished_product", int(row.id), row.name, row.stock_qty, row.alert_threshold, active_alerts, db=db)


async def _trigger_alert(
    product_type: str,
    product_id: int,
    name: str,
    current_qty: float,
    threshold_qty: float,
    active_alerts: set[tuple[str, int]] | None = None,
    *,
    db: AsyncSession,
) -> None:
    # Éviter les doublons dans les dernières 24h
    if active_alerts is not None:
        if (product_type, product_id) in active_alerts:
            return
    else:
        # Fallback: query individually (for standalone calls outside check_stock_alerts)
        duplicate_res = await db.execute(
            select(StockAlert.id)
            .where(
                StockAlert.product_type == product_type,
                StockAlert.product_id == product_id,
                StockAlert.acknowledged_at == None,
                StockAlert.triggered_at > func.now() - text("INTERVAL '24 hours'")
            )
            .limit(1)
        )
        duplicate = duplicate_res.first()
        if duplicate:
            return

    new_alert = StockAlert(
        product_type=product_type,
        product_id=product_id,
        product_name=name,
        current_qty=current_qty,
        threshold_qty=threshold_qty,
        triggered_at=datetime.now(),
    )
    db.add(new_alert)
    # Update the cache so subsequent calls in the same batch won't re-trigger
    if active_alerts is not None:
        active_alerts.add((product_type, product_id))
