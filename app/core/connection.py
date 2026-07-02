"""
DÉPRÉCIÉ — Ce fichier existe pour la compatibilité descendante.
Tout le code source est dans db_helpers.py. Utilisez db_helpers.py ou db/__init__.py directement.
"""
from __future__ import annotations

from app.core.db_helpers import (  # noqa: F401
    CompatRow,
    CompatCursor,
    CompatConnection,
    ConnectionPoolManager,
    pool_manager,
    DatabaseManager,
    db_manager,
    get_db,
    connect_database,
    query_db,
    query_db_async,
    execute_db,
    execute_db_async,
    explain_query_plan,
    db_transaction,
    get_setting,
    set_setting,
    postgres_pool_status,
    list_columns,
    pending_performance_event_count,
    drain_performance_events_once,
    db_task,
    execute_sa,
    query_sa,
)
