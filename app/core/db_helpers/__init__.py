"""
Backward-compatibility facade for db_helpers.
Canonical implementation and single source of truth is `app.core.database`.
"""

from __future__ import annotations

import sys

from app.core import database as _db

# Low-level DB wrappers and types
CompatRow = _db.CompatRow
CompatCursor = _db.CompatCursor
CompatConnection = _db.CompatConnection
_clean_params = _db._clean_params
_wrap_rows = _db._wrap_rows

# Managers
DatabaseManager = _db.DatabaseManager
ConnectionPoolManager = _db.ConnectionPoolManager
db_manager = _db.db_manager
pool_manager = _db.pool_manager

# Connection management
get_db = _db.get_db
get_write_db = _db.get_write_db
get_read_db = _db.get_read_db
connect_database = _db.connect_database
postgres_pool_status = _db.postgres_pool_status
list_columns = _db.list_columns

# Performance & Logging
pending_performance_event_count = _db.pending_performance_event_count
drain_performance_events_once = _db.drain_performance_events_once

# Transactions & Tasks
db_task = _db.db_task
db_transaction = _db.db_transaction

# Settings
get_setting = _db.get_setting
set_setting = _db.set_setting
update_setting = _db.update_setting

# SQL Script & Queries
split_sql_script = _db.split_sql_script
validate_identifier = _db.validate_identifier
query_db = _db.query_db
query_db_async = _db.query_db_async
explain_query_plan = _db.explain_query_plan
query_sa = _db.query_sa
execute_db = _db.execute_db
execute_db_async = _db.execute_db_async
execute_sa = _db.execute_sa

# Direct aliases for legacy submodules
sys.modules["app.core.db_helpers.manager"] = _db
sys.modules["app.core.db_helpers.execute"] = _db
sys.modules["app.core.db_helpers.query"] = _db

__all__ = [
    "CompatRow",
    "CompatCursor",
    "CompatConnection",
    "DatabaseManager",
    "ConnectionPoolManager",
    "db_manager",
    "pool_manager",
    "get_db",
    "get_write_db",
    "get_read_db",
    "connect_database",
    "postgres_pool_status",
    "list_columns",
    "pending_performance_event_count",
    "drain_performance_events_once",
    "db_task",
    "db_transaction",
    "get_setting",
    "set_setting",
    "update_setting",
    "split_sql_script",
    "validate_identifier",
    "query_db",
    "query_db_async",
    "explain_query_plan",
    "query_sa",
    "execute_db",
    "execute_db_async",
    "execute_sa",
]
