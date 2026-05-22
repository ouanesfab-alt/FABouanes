"""
Point d'entrée unique pour la couche base de données.
Réexporte les fonctions publiques depuis les sous-modules.
Tous les imports existants du type :
    from app.core.db_access import query_db, execute_db
continuent de fonctionner (db_access.py reste en place comme alias).
"""
# Choix importants :
# 1. Exposition simplifiée de l'interface DB via un module db unifié.
# 2. Conservation de la compatibilité descendante totale sans déplacer les fichiers physiques existants.

from app.core.db_access import (
    query_db,
    query_db_async,
    execute_db,
    get_db,
    get_setting,
    set_setting,
)
from app.core.db_helpers import (
    DatabaseManager,
    db_transaction,
    db_manager,
)
from app.core.connection import (
    connect_database,
    postgres_pool_status,
    list_columns,
    pool_manager,
)

# Alias pour correspondre aux variations d'interface possibles
update_setting = set_setting

def sqlalchemy_database_url(database_url: str) -> str:
    return pool_manager.sqlalchemy_database_url(database_url)

def create_database_engine(database_url: str):
    return pool_manager.create_database_engine(database_url)

def get_database_engine(database_url: str):
    return pool_manager.get_database_engine(database_url)

__all__ = [
    "query_db", "query_db_async", "execute_db",
    "get_db", "get_setting", "set_setting", "update_setting",
    "DatabaseManager", "db_transaction", "db_manager",
    "connect_database", "postgres_pool_status", "list_columns", "pool_manager",
    "sqlalchemy_database_url", "create_database_engine", "get_database_engine",
]
