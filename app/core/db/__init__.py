"""
Point d'entrée unifié pour la couche base de données.
Réexporte les fonctions publiques depuis db_helpers.py (la source unique de vérité).
"""
from app.core.db_helpers import (  # noqa: F401
    CompatConnection,
    CompatCursor,
    # Low-level
    CompatRow,
    ConnectionPoolManager,
    # Connection management
    DatabaseManager,
    connect_database,
    db_manager,
    db_task,
    # Transactions
    db_transaction,
    drain_performance_events_once,
    execute_db,
    execute_db_async,
    # SQLAlchemy
    execute_sa,
    explain_query_plan,
    get_db,
    get_setting,
    list_columns,
    # Performance
    pending_performance_event_count,
    pool_manager,
    postgres_pool_status,
    # Query & Execute
    query_db,
    query_db_async,
    query_sa,
    set_setting,
)

# Alias
update_setting = set_setting


def sqlalchemy_database_url(database_url: str) -> str:
    return pool_manager.sqlalchemy_database_url(database_url)

def create_database_engine(database_url: str):
    return pool_manager.create_database_engine(database_url)

def get_database_engine(database_url: str):
    return pool_manager.get_database_engine(database_url)
