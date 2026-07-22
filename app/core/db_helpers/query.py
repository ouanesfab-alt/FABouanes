from __future__ import annotations

import re
from app.core.db_helpers.manager import db_manager


def split_sql_script(script: str) -> list[str]:
    statements = []
    current = []
    in_dollar = False
    in_single_quote = False
    in_double_quote = False

    i = 0
    n = len(script)
    while i < n:
        char = script[i]

        if not in_dollar and not in_single_quote and not in_double_quote:
            if char == '-' and i + 1 < n and script[i+1] == '-':
                i += 2
                while i < n and script[i] != '\n':
                    i += 1
                continue
            if char == '/' and i + 1 < n and script[i+1] == '*':
                i += 2
                while i < n and not (script[i] == '*' and i + 1 < n and script[i+1] == '/'):
                    i += 1
                i += 2
                continue

        if char == '$' and i + 1 < n and script[i+1] == '$':
            in_dollar = not in_dollar
            current.append('$$')
            i += 2
            continue

        if not in_dollar:
            if char == "'" and (i == 0 or script[i-1] != '\\'):
                in_single_quote = not in_single_quote
            elif char == '"' and (i == 0 or script[i-1] != '\\'):
                in_double_quote = not in_double_quote

        if char == ';' and not in_dollar and not in_single_quote and not in_double_quote:
            stmt = "".join(current).strip()
            if stmt:
                statements.append(stmt)
            current = []
        else:
            current.append(char)
        i += 1

    stmt = "".join(current).strip()
    if stmt:
        statements.append(stmt)
    return statements


def validate_identifier(name: str) -> None:
    if not name or not isinstance(name, str):
        raise ValueError("Invalid database identifier")
    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_\.]*$", name):
        raise ValueError(f"Invalid database identifier: {name}")


def query_db(query: str, params: tuple = (), one: bool = False):
    return db_manager.query_db(query, params, one)


async def query_db_async(query: str, params: tuple = (), one: bool = False):
    return await db_manager.query_db_async(query, params, one)


def explain_query_plan(query: str, params: tuple = ()) -> list[dict]:
    return db_manager.explain_query_plan(query, params)


def query_sa(query, one: bool = False):
    from sqlalchemy.dialects import sqlite
    compiled = query.compile(dialect=sqlite.dialect(paramstyle="qmark"), compile_kwargs={"literal_binds": False})
    sql = str(compiled)
    params = tuple(compiled.params[name] for name in (compiled.positiontup or ()))
    return query_db(sql, params, one=one)
