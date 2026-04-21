from __future__ import annotations

import os
import re
import sqlite3
from collections import OrderedDict
from contextlib import closing
from pathlib import Path
from typing import Any

try:
    import pg8000.dbapi as pg_dbapi
except Exception:
    pg_dbapi = None


class CompatRow(dict):
    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class CompatCursor:
    def __init__(self, cursor, dialect: str, description=None):
        self.cursor = cursor
        self.dialect = dialect
        self.description = description or getattr(cursor, "description", None)

    def fetchall(self):
        rows = self.cursor.fetchall()
        return _wrap_rows(rows, self.description, self.dialect)

    def fetchone(self):
        row = self.cursor.fetchone()
        if row is None:
            return None
        return _wrap_rows([row], self.description, self.dialect)[0]

    def close(self):
        try:
            self.cursor.close()
        except Exception:
            pass

    @property
    def lastrowid(self):
        return getattr(self.cursor, "lastrowid", None)


class CompatConnection:
    def __init__(self, conn, dialect: str):
        self.conn = conn
        self.dialect = dialect
        if dialect == "sqlite":
            self.conn.row_factory = sqlite3.Row
            self.conn.execute("PRAGMA foreign_keys = ON")

    def execute(self, query: str, params: tuple = ()):
        q = adapt_query(query, self.dialect)
        cur = self.conn.cursor()
        cur.execute(q, params)
        return CompatCursor(cur, self.dialect)

    def executescript(self, script: str):
        if self.dialect == "sqlite":
            return self.conn.executescript(script)
        for statement in split_sql_script(script):
            stmt = adapt_query(statement, self.dialect)
            if stmt.strip():
                cur = self.conn.cursor()
                cur.execute(stmt)
        return None

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()

    def close(self):
        self.conn.close()


def _wrap_rows(rows, description, dialect):
    if dialect == "sqlite":
        return rows
    if not description:
        return rows
    cols = [c[0] for c in description]
    wrapped = []
    for row in rows:
        wrapped.append(CompatRow(OrderedDict(zip(cols, row))))
    return wrapped


def _postgres_connect(database_url: str):
    if pg_dbapi is None:
        raise RuntimeError("pg8000 n'est pas installé. Ajoute-le dans requirements.txt.")
    from urllib.parse import urlparse, unquote
    parsed = urlparse(database_url)
    return pg_dbapi.connect(
        user=unquote(parsed.username or ""),
        password=unquote(parsed.password or ""),
        host=parsed.hostname or "localhost",
        port=int(parsed.port or 5432),
        database=(parsed.path or "/")[1:],
    )


def connect_database(database_url: str, sqlite_path: str | Path):
    if database_url.lower().startswith("postgres"):
        return CompatConnection(_postgres_connect(database_url), "postgres")
    return CompatConnection(sqlite3.connect(str(sqlite_path)), "sqlite")


def adapt_query(query: str, dialect: str) -> str:
    q = query
    if dialect == "postgres":
        q = q.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "BIGSERIAL PRIMARY KEY")
        q = re.sub(r"\bAUTOINCREMENT\b", "", q, flags=re.I)
        q = q.replace("INSERT OR IGNORE INTO", "INSERT INTO")
        q = re.sub(r"INSERT INTO ([^(\s]+) \(([^)]+)\) VALUES \(([^)]+)\)$", r"INSERT INTO \1 (\2) VALUES (\3) ON CONFLICT DO NOTHING", q, flags=re.I)
        q = q.replace("CURRENT_TIMESTAMP", "CURRENT_TIMESTAMP")
        q = q.replace("?", "%s")
    return q


def split_sql_script(script: str):
    return [s.strip() for s in script.split(";") if s.strip()]

def list_columns(conn: CompatConnection, table: str) -> set[str]:
    if conn.dialect == "sqlite":
        cur = conn.execute(f"PRAGMA table_info({table})")
        rows = cur.fetchall()
        cur.close()
        return {row[1] for row in rows}
    cur = conn.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_schema = 'public' AND table_name = %s",
        (table,),
    )
    rows = cur.fetchall()
    cur.close()
    return {row["column_name"] for row in rows}

def server_default_now() -> str:
    return "CURRENT_TIMESTAMP"
