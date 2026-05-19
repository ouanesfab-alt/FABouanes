"""
Responsibility: Consolidated access functions for executing queries and transactions.
Delegates to connection.py.
"""
from __future__ import annotations

from app.core.connection import (
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
    record_request_timing,
    db_task,
    execute_sa,
    query_sa,
)
