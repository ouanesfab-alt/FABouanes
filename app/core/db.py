"""
Responsibility: Entry point for database connections, engine management, and high-level status.
Delegates to connection.py for consolidated database management.
"""
from __future__ import annotations

from app.core.connection import (
    db_manager,
    connect_database,
    postgres_pool_status,
    list_columns,
)

def sqlalchemy_database_url(database_url: str) -> str:
    return db_manager.sqlalchemy_database_url(database_url)

def create_database_engine(database_url: str):
    return db_manager.create_database_engine(database_url)

def get_database_engine(database_url: str):
    return db_manager.get_database_engine(database_url)
