"""
Responsibility: Bootstrap the initial database schema and seed data.
"""

from __future__ import annotations

from app.core.config import settings
from app.core.db_helpers import connect_database

ADVISORY_LOCK_ID = 884712


def _execute(conn, query: str, params: tuple = ()):
    return conn.execute(query, params) if hasattr(conn, "execute") else conn.cursor().execute(query, params)


def _executescript(conn, sql: str) -> None:
    from sqlalchemy import text

    if hasattr(conn, "exec_driver_sql"):
        try:
            conn.exec_driver_sql(sql)
            return
        except Exception:
            pass
    if hasattr(conn, "executescript"):
        try:
            conn.executescript(sql)
            return
        except Exception:
            pass
    from app.core.db_helpers.query import split_sql_script

    for stmt in split_sql_script(sql):
        if stmt.strip():
            if hasattr(conn, "execute"):
                conn.execute(text(stmt))
            elif hasattr(conn, "cursor"):
                conn.cursor().execute(stmt)
    if hasattr(conn, "commit"):
        try:
            conn.commit()
        except Exception as commit_exc:
            import logging

            logging.getLogger("fabouanes.db").warning("Commit failed in script statement execution: %s", commit_exc)


def bootstrap_schema() -> None:
    from app.core.database import run_alembic_upgrade

    conn = connect_database(settings.database_url)
    try:
        try:
            _execute(conn, "SELECT pg_advisory_lock(%s)", (ADVISORY_LOCK_ID,))
        except Exception:
            pass

        # 1. Base Core & domain schema models (SQLModel)
        from sqlmodel import SQLModel

        import app.core.models  # noqa: F401
        from app.core.db import get_database_engine

        engine = get_database_engine(settings.database_url)
        SQLModel.metadata.create_all(engine)

        # 2. Alembic is the canonical and single authority for schema lifecycle and migrations
        run_alembic_upgrade()

        # 3. Discover and register module schemas if any
        try:
            from app.core.registry import discover_modules, get_enabled_modules

            discover_modules(settings.base_dir / "app" / "modules")
            for module in get_enabled_modules():
                for sql in module.schema_sql:
                    _executescript(conn, sql)
        except Exception as e:
            import logging

            logging.getLogger("fabouanes").warning("Failed to bootstrap module schemas: %s", e)

        # 4. Seeds (admin, settings, other operations)
        from app.core.schema import _seed_default_admin, _seed_default_settings, _seed_other_operation

        _seed_default_admin(conn)
        _seed_default_settings(conn)
        _seed_other_operation(conn)
        conn.commit()
    finally:
        try:
            _execute(conn, "SELECT pg_advisory_unlock(%s)", (ADVISORY_LOCK_ID,))
        except Exception:
            pass
        conn.close()
