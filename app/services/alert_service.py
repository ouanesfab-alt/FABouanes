"""
Service d'alertes clients — détecte les clients en retard de paiement.
Lancé quotidiennement par APScheduler via app/core/events.py.
"""
# Choix importants :
# 1. Utilisation d'une requête SQL PostgreSQL pure avec DATE_PART pour calculer l'inactivité en jours.
# 2. Diffusion instantanée des alertes en mode synchrone via manager.broadcast_sync pour intégration avec APScheduler.

from __future__ import annotations
from datetime import date, timedelta
from app.core.db_access import query_db, db_transaction
from app.core.websockets import manager
import json, logging

logger = logging.getLogger("fabouanes.alerts")

DEFAULT_OVERDUE_DAYS = 30


def check_overdue_clients(overdue_days: int = DEFAULT_OVERDUE_DAYS) -> list[dict]:
    """
    Retourne les clients avec balance > 0 et aucune opération
    depuis plus de `overdue_days` jours.
    """
    cutoff = (date.today() - timedelta(days=overdue_days)).isoformat()
    return query_db(
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


def broadcast_overdue_alerts() -> int:
    """
    Vérifie les clients en retard et diffuse une alerte WebSocket.
    Retourne le nombre de clients en retard détectés.
    Appelé quotidiennement par le scheduler.
    """
    with db_transaction():
        # Essaye d'obtenir un verrou consultatif transactionnel (advisory lock)
        # pour éviter les exécutions multiples concurrentes (par exemple avec plusieurs workers Gunicorn)
        locked_row = query_db("SELECT pg_try_advisory_xact_lock(48216732) AS locked", one=True)
        if not locked_row or not locked_row["locked"]:
            logger.info("Verrou consultatif déjà détenu par un autre worker. Tâche ignorée.")
            return 0

        overdue = check_overdue_clients()
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
            logger.info(f"Alerte : {len(overdue)} clients en retard.")
        return len(overdue)


def check_stock_alerts() -> None:
    """Vérifie le stock de matières premières et de produits finis par rapport au seuil."""
    from app.core.db_access import query_db
    
    # Matières premières
    raws = query_db(
        "SELECT id, name, stock_qty, alert_threshold FROM raw_materials WHERE stock_qty <= alert_threshold AND alert_threshold > 0"
    )
    for row in raws:
        _trigger_alert("raw_material", int(row["id"]), row["name"], row["stock_qty"], row["alert_threshold"])
        
    # Produits finis
    products = query_db(
        "SELECT id, name, stock_qty, alert_threshold FROM finished_products WHERE stock_qty <= alert_threshold AND alert_threshold > 0"
    )
    for row in products:
        _trigger_alert("finished_product", int(row["id"]), row["name"], row["stock_qty"], row["alert_threshold"])


def _trigger_alert(product_type: str, product_id: int, name: str, current_qty: float, threshold_qty: float) -> None:
    from app.core.db_access import query_db, execute_db
    # Éviter les doublons dans les dernières 24h
    duplicate = query_db(
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
        
    execute_db(
        """
        INSERT INTO stock_alerts (product_type, product_id, product_name, current_qty, threshold_qty, triggered_at)
        VALUES (%s, %s, %s, %s, %s, NOW())
        """,
        (product_type, product_id, name, current_qty, threshold_qty)
    )
