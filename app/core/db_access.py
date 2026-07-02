"""
DÉPRÉCIÉ — Ce fichier existe pour la compatibilité descendante.
Utilisez app.core.db_helpers directement ou app.core.db (le package).
"""
from __future__ import annotations

from app.core.db_helpers import (  # noqa: F401
    get_db,
    query_db,
    query_db_async,
    execute_db,
    execute_db_async,
    explain_query_plan,
    db_transaction,
    get_setting,
    set_setting,
    pending_performance_event_count,
    drain_performance_events_once,
    db_task,
    execute_sa,
    query_sa,
)
