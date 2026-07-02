"""
DÉPRÉCIÉ — Ce fichier (app/core/db.py) existe pour la compatibilité descendante.
Le vrai code est dans db_helpers.py. Utilisez app.core.db (le package) pour les nouveaux imports.
"""
from __future__ import annotations

from app.core.db_helpers import pool_manager  # noqa: F401


def sqlalchemy_database_url(database_url: str) -> str:
    return pool_manager.sqlalchemy_database_url(database_url)

def create_database_engine(database_url: str):
    return pool_manager.create_database_engine(database_url)

def get_database_engine(database_url: str):
    return pool_manager.get_database_engine(database_url)

def connect_database(database_url: str):
    return pool_manager.connect_database(database_url)

def postgres_pool_status(database_url: str):
    return pool_manager.postgres_pool_status(database_url)

def list_columns(conn, table: str):
    from app.core.db_helpers import list_columns as _lc
    return _lc(conn, table)
