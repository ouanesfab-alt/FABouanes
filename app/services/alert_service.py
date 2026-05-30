from __future__ import annotations
from datetime import date, timedelta
from app.core.db_access import query_db_async, execute_db_async, db_transaction
from app.core.websockets import manager
import json, logging

logger = logging.getLogger("fabouanes.alerts")

DEFAULT_OVERDUE_DAYS = 30


async def check_overdue_clients(overdue_days: int = DEFAULT_OVERDUE_DAYS) -> list[dict]:
    """
    Retourne les clients avec balance > 0 et aucune opération
    depuis plus de `overdue_days` jours.
    """
    cutoff = (date.today() - timedelta(days=overdue_days)).isoformat()
    return await query_db_async(
        """
        SELECT
            c.id, c.name, c.current_balance AS balance,
            MAX(ch.operation_date) AS derniere_operation,
            DATE_PART('day', NOW() - MAX(ch.operation_date)) AS jours_inactif
        FROM clients_with_stats c
        LEFT JOIN client_history ch ON ch.client_id = c.id
        WHERE c.current_balance > 0
        GROUP BY c.id, c.name, c.current_balance
        HAVING MAX(ch.operation_date) < %s
            OR MAX(ch.operation_date) IS NULL
        ORDER BY c.current_balance DESC
        LIMIT 50
        """,
        (cutoff,),
    )


async def broadcast_overdue_alerts() -> int:
    """
    Vérifie les clients en retard et diffuse une alerte WebSocket.
    Retourne le nombre de clients en retard détectés.
    Appelé quotidiennement par le scheduler.
    """
    with db_transaction():
        # Essaye d'obtenir un verrou consultatif transactionnel (advisory lock)
        # pour éviter les exécutions multiples concurrentes (par exemple avec plusieurs workers Gunicorn)
        locked_row = await query_db_async("SELECT pg_try_advisory_xact_lock(48216732) AS locked", one=True)
        if not locked_row or not locked_row["locked"]:
            logger.info("Verrou consultatif déjà détenu par un autre worker. Tâche ignorée.")
            return 0

        overdue = await check_overdue_clients()
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


async def check_stock_alerts() -> None:
    """Vérifie le stock de matières premières et de produits finis par rapport au seuil."""

    # Pre-fetch all active (unacknowledged) alerts from the last 24h in one query
    # to avoid N individual SELECT queries inside the loop.
    active_rows = await query_db_async(
        """
        SELECT product_type, product_id FROM stock_alerts
        WHERE acknowledged_at IS NULL
          AND triggered_at > NOW() - INTERVAL '24 hours'
        """
    )
    active_alerts: set[tuple[str, int]] = {
        (row["product_type"], int(row["product_id"])) for row in active_rows
    }

    # Matières premières
    raws = await query_db_async(
        "SELECT id, name, stock_qty, alert_threshold FROM raw_materials WHERE stock_qty <= alert_threshold AND alert_threshold > 0"
    )
    for row in raws:
        await _trigger_alert("raw_material", int(row["id"]), row["name"], row["stock_qty"], row["alert_threshold"], active_alerts)

    # Produits finis
    products = await query_db_async(
        "SELECT id, name, stock_qty, alert_threshold FROM finished_products WHERE stock_qty <= alert_threshold AND alert_threshold > 0"
    )
    for row in products:
        await _trigger_alert("finished_product", int(row["id"]), row["name"], row["stock_qty"], row["alert_threshold"], active_alerts)


async def _trigger_alert(
    product_type: str,
    product_id: int,
    name: str,
    current_qty: float,
    threshold_qty: float,
    active_alerts: set[tuple[str, int]] | None = None,
) -> None:
    # Éviter les doublons dans les dernières 24h
    if active_alerts is not None:
        if (product_type, product_id) in active_alerts:
            return
    else:
        # Fallback: query individually (for standalone calls outside check_stock_alerts)
        duplicate = await query_db_async(
            """
            SELECT id FROM stock_alerts
            WHERE product_type = %s AND product_id = %s
              AND acknowledged_at IS NULL
              AND triggered_at > NOW() - INTERVAL '24 hours'
            LIMIT 1
            """,
            (product_type, product_id),
            one=True
        )
        if duplicate:
            return

    await execute_db_async(
        """
        INSERT INTO stock_alerts (product_type, product_id, product_name, current_qty, threshold_qty, triggered_at)
        VALUES (%s, %s, %s, %s, %s, NOW())
        """,
        (product_type, product_id, name, current_qty, threshold_qty)
    )
    # Update the cache so subsequent calls in the same batch won't re-trigger
    if active_alerts is not None:
        active_alerts.add((product_type, product_id))
