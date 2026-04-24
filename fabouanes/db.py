from __future__ import annotations

import re
from collections import OrderedDict
from pathlib import Path

try:
    import pg8000.dbapi as pg_dbapi
except Exception:
    pg_dbapi = None


POSTGRES_RETURNING_ID_TABLES = {
    "users",
    "clients",
    "suppliers",
    "raw_materials",
    "finished_products",
    "purchase_documents",
    "sale_documents",
    "purchases",
    "production_batches",
    "production_batch_items",
    "saved_recipes",
    "saved_recipe_items",
    "sales",
    "raw_sales",
    "payments",
    "activity_logs",
    "error_logs",
    "system_logs",
    "audit_logs",
    "backup_jobs",
    "backup_runs",
    "api_refresh_tokens",
    "imported_client_history",
    "schema_migrations",
}


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
        self._prefetched_rows = []
        self._lastrowid = getattr(cursor, "lastrowid", None)
        self._lastrowid_loaded = self._lastrowid is not None

    def fetchall(self):
        rows = list(self._prefetched_rows)
        self._prefetched_rows.clear()
        rows.extend(self.cursor.fetchall())
        return _wrap_rows(rows, self.description)

    def fetchone(self):
        if self._prefetched_rows:
            row = self._prefetched_rows.pop(0)
        else:
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
        if self._lastrowid_loaded:
            return self._lastrowid
        self._lastrowid_loaded = True
        if self.dialect == "postgres" and self.description:
            columns = [column[0] for column in self.description]
            if columns == ["id"]:
                row = self.cursor.fetchone()
                if row is not None:
                    self._prefetched_rows.append(row)
                    self._lastrowid = row[0]
        return self._lastrowid


class CompatConnection:
    def __init__(self, conn, dialect: str):
        self.conn = conn
        self.dialect = dialect

    def execute(self, query: str, params: tuple = ()):
        q = adapt_query(query, self.dialect)
        if self.dialect == "postgres":
            q = _append_postgres_returning_id(q)
        cur = self.conn.cursor()
        cur.execute(q, params)
        return CompatCursor(cur, self.dialect)

    def executescript(self, script: str):
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


def _wrap_rows(rows, description):
    if not description:
        return rows
    columns = [column[0] for column in description]
    wrapped = []
    for row in rows:
        wrapped.append(CompatRow(OrderedDict(zip(columns, row))))
    return wrapped


def _postgres_connect(database_url: str):
    if pg_dbapi is None:
        raise RuntimeError("pg8000 n'est pas installe. Ajoute-le dans requirements.txt.")
    from urllib.parse import urlparse, unquote

    parsed = urlparse(database_url)
    return pg_dbapi.connect(
        user=unquote(parsed.username or ""),
        password=unquote(parsed.password or ""),
        host=parsed.hostname or "localhost",
        port=int(parsed.port or 5432),
        database=(parsed.path or "/")[1:],
    )


def connect_database(database_url: str, db_path_hint: str | Path):
    normalized = (database_url or "").strip()
    if not normalized:
        raise RuntimeError(
            "DATABASE_URL est obligatoire et doit pointer vers PostgreSQL. "
            "Copie .env.example vers .env puis renseigne une URL PostgreSQL."
        )
    if not normalized.lower().startswith(("postgres://", "postgresql://")):
        raise RuntimeError("Seules les URL PostgreSQL sont prises en charge.")
    return CompatConnection(_postgres_connect(normalized), "postgres")


def adapt_query(query: str, dialect: str) -> str:
    q = query
    if dialect == "postgres":
        q = q.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "BIGSERIAL PRIMARY KEY")
        q = re.sub(r"\bAUTOINCREMENT\b", "", q, flags=re.I)
        q = q.replace("INSERT OR IGNORE INTO", "INSERT INTO")
        q = re.sub(
            r"INSERT INTO ([^(\s]+) \(([^)]+)\) VALUES \(([^)]+)\)$",
            r"INSERT INTO \1 (\2) VALUES (\3) ON CONFLICT DO NOTHING",
            q,
            flags=re.I,
        )
        q = re.sub(r"\bGROUP_CONCAT\s*\(", "STRING_AGG(", q, flags=re.I)
        q = re.sub(
            r"printf\s*\(\s*'%.2f'\s*,\s*([^)]+?)\s*\)",
            r"to_char(CAST(\1 AS numeric), 'FM999999999990.00')",
            q,
            flags=re.I,
        )
        q = q.replace("?", "%s")
    return q


def _append_postgres_returning_id(query: str) -> str:
    if re.search(r"\bRETURNING\b", query, flags=re.I):
        return query
    match = re.match(r"\s*INSERT\s+INTO\s+([a-zA-Z_][\w]*)\b", query, flags=re.I)
    if not match:
        return query
    table = match.group(1).lower()
    if table not in POSTGRES_RETURNING_ID_TABLES:
        return query
    return query.rstrip().rstrip(";") + " RETURNING id"


def split_sql_script(script: str):
    return [statement.strip() for statement in script.split(";") if statement.strip()]


def list_columns(conn: CompatConnection, table: str) -> set[str]:
    cur = conn.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_schema = 'public' AND table_name = %s",
        (table,),
    )
    rows = cur.fetchall()
    cur.close()
    return {row["column_name"] for row in rows}


def server_default_now() -> str:
    return "CURRENT_TIMESTAMP"
