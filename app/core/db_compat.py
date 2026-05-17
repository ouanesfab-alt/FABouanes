from __future__ import annotations

import re
from collections import OrderedDict
from typing import Any, Callable

def adapt_query(query: str, dialect: str) -> str:
    q = query
    if dialect == "sqlite":
        q = q.replace("CURRENT_TIMESTAMP::text", "CURRENT_TIMESTAMP")
    if dialect == "postgres":
        q = q.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "BIGSERIAL PRIMARY KEY")
        q = re.sub(r"\bAUTOINCREMENT\b", "", q, flags=re.I)
        q = q.replace("INSERT OR IGNORE INTO", "INSERT INTO")
        q = re.sub(r"INSERT INTO ([^(\s]+)\s*\(([^)]+)\)\s*VALUES\s*\(([^)]+)\)\s*$", r"INSERT INTO \1 (\2) VALUES (\3) ON CONFLICT DO NOTHING", q, flags=re.I | re.DOTALL)
        q = q.replace("CURRENT_TIMESTAMP", "CURRENT_TIMESTAMP")
        q = q.replace("?", "%s")
    return q

def split_sql_script(script: str):
    return [s.strip() for s in script.split(";") if s.strip()]

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
    def __init__(
        self,
        conn,
        dialect: str,
        on_close: Callable[[Any], None] | None = None,
        reconnect: Callable[[], Any] | None = None,
    ):
        self.conn = conn
        self.dialect = dialect
        self._on_close = on_close
        self._reconnect = reconnect
        self._closed = False

    def execute(self, query: str, params: tuple = ()):
        q = adapt_query(query, self.dialect)
        retried = False
        while True:
            cur = self.conn.cursor()
            try:
                cur.execute(q, params)
                return CompatCursor(cur, self.dialect)
            except Exception as exc:
                try:
                    cur.close()
                except Exception:
                    pass

                if self.dialect == "postgres":
                    # For Postgres, any failure aborts the transaction (25P02).
                    # We MUST rollback to clear the state.
                    try:
                        self.conn.rollback()
                    except Exception:
                        pass
                    
                    exc_msg = str(exc).lower()
                    # Handle aborted transaction (25P02) by retrying once if not already retried
                    if ("25p02" in exc_msg or "transaction is aborted" in exc_msg) and not retried:
                        retried = True
                        continue

                    # Handle connection issues
                    if not retried:
                        from sqlalchemy.exc import DBAPIError, OperationalError
                        if isinstance(exc, (OperationalError, DBAPIError)) or "connection" in exc_msg:
                            self._reset_postgres_connection()
                            retried = True
                            continue
                raise



    def executescript(self, script: str):
        if self.dialect == "sqlite":
            return self.conn.executescript(script)
        for statement in split_sql_script(script):
            if statement.strip():
                self.execute(statement)
        return None


    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()

    def close(self):
        if self._closed:
            return
        self._closed = True
        if self._on_close is not None:
            self._on_close(self.conn)
            return
        self.conn.close()

    def _reset_postgres_connection(self) -> None:
        if self._reconnect is None:
            raise RuntimeError("Connexion PostgreSQL perdue et reconnexion indisponible.")
        try:
            self.conn.close()
        except Exception:
            pass
        self.conn = self._reconnect()

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
