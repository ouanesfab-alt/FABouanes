"""
Point d'entrée unifié pour la couche base de données.
Réexporte les fonctions publiques depuis db_helpers.py (la source unique de vérité).
"""
from app.core.db_helpers import (  # noqa: F401
    # Query & Execute
    query_db,
    query_db_async,
    execute_db,
    execute_db_async,
    get_db,
    get_setting,
    set_setting,
    # Transactions
    db_transaction,
    db_task,
    # SQLAlchemy
    execute_sa,
    query_sa,
    # Connection management
    DatabaseManager,
    db_manager,
    ConnectionPoolManager,
    pool_manager,
    connect_database,
    postgres_pool_status,
    list_columns,
    explain_query_plan,
    # Performance
    pending_performance_event_count,
    drain_performance_events_once,
    # Low-level
    CompatRow,
    CompatCursor,
    CompatConnection,
)

# Alias
update_setting = set_setting


def sqlalchemy_database_url(database_url: str) -> str:
    return pool_manager.sqlalchemy_database_url(database_url)

def create_database_engine(database_url: str):
    return pool_manager.create_database_engine(database_url)

def get_database_engine(database_url: str):
    return pool_manager.get_database_engine(database_url)
