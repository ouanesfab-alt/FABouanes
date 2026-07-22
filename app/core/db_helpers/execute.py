from __future__ import annotations

from app.core.db_helpers.manager import db_manager


def execute_db(query: str, params: tuple = ()) -> int:
    return db_manager.execute_db(query, params)


async def execute_db_async(query: str, params: tuple = ()) -> int:
    return await db_manager.execute_db_async(query, params)


def execute_sa(query) -> int:
    from sqlalchemy.dialects import sqlite
    compiled = query.compile(dialect=sqlite.dialect(paramstyle="qmark"), compile_kwargs={"literal_binds": False})
    sql = str(compiled)
    params = tuple(compiled.params[name] for name in (compiled.positiontup or ()))
    return execute_db(sql, params)
