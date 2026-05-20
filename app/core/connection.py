from __future__ import annotations

# Backward compatibility facade for Database and Connection Utilities.
# This file delegates all core functionalities to the newly decoupled modules:
# - db_pool.py (for ConnectionPoolManager and DBAPI compatibility wrappers)
# - db_helpers.py (for query, transaction wrappers, and performance logs)

from app.core.db_helpers import (
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

# Re-exporting all objects
__all__ = [
    "CompatRow",
    "CompatCursor",
    "CompatConnection",
    "ConnectionPoolManager",
    "pool_manager",
    "DatabaseManager",
    "db_manager",
    "get_db",
    "connect_database",
    "query_db",
    "query_db_async",
    "execute_db",
    "execute_db_async",
    "explain_query_plan",
    "db_transaction",
    "get_setting",
    "set_setting",
    "postgres_pool_status",
    "list_columns",
    "pending_performance_event_count",
    "drain_performance_events_once",
    "db_task",
    "execute_sa",
    "query_sa",
]
