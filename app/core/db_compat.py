from __future__ import annotations

import re
from collections import OrderedDict
from typing import Any, Callable

def adapt_query(query: str) -> str:
    q = query
    q = q.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "BIGSERIAL PRIMARY KEY")
    q = re.sub(r"\bAUTOINCREMENT\b", "", q, flags=re.I)
    q = q.replace("INSERT OR IGNORE INTO", "INSERT INTO")
    q = re.sub(r"INSERT INTO ([^(\s]+)\s*\(([^)]+)\)\s*VALUES\s*\(([^)]+)\)\s*$", r"INSERT INTO \1 (\2) VALUES (\3) ON CONFLICT DO NOTHING", q, flags=re.I | re.DOTALL)
    q = q.replace("?", "%s")
    return q

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
        
        # Check for $$
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
                
        # Split at semicolon ONLY if not inside any quotes or dollar quotes
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

class CompatRow(dict):
    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)

class CompatCursor:
    def __init__(self, cursor, description=None):
        self.cursor = cursor
        self.description = description or getattr(cursor, "description", None)

    def fetchall(self):
        rows = self.cursor.fetchall()
        return _wrap_rows(rows, self.description)

    def fetchone(self):
        row = self.cursor.fetchone()
        if row is None:
            return None
        return _wrap_rows([row], self.description)[0]

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
        dialect: str = "postgres",  # Kept for compatibility with other files just in case
        on_close: Callable[[Any], None] | None = None,
        reconnect: Callable[[], Any] | None = None,
    ):
        self.conn = conn
        self.dialect = "postgres"
        self._on_close = on_close
        self._reconnect = reconnect
        self._closed = False

    def execute(self, query: str, params: tuple = ()):
        q = adapt_query(query)
        retried = False
        while True:
            cur = self.conn.cursor()
            try:
                cur.execute(q, params)
                return CompatCursor(cur)
            except Exception as exc:
                try:
                    cur.close()
                except Exception:
                    pass

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

def _wrap_rows(rows, description):
    if not description:
        return rows
    cols = [c[0] for c in description]
    wrapped = []
    for row in rows:
        wrapped.append(CompatRow(OrderedDict(zip(cols, row))))
    return wrapped
