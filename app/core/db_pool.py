from __future__ import annotations

import os
import logging
import threading
from collections import OrderedDict
from typing import Any, Callable
from urllib.parse import urlparse

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.core.config import settings

logger = logging.getLogger("fabouanes")

class CompatRow(dict):
    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)

def _wrap_rows(rows, description):
    if not description:
        return rows
    cols = [c[0] for c in description]
    wrapped = []
    for row in rows:
        wrapped.append(CompatRow(OrderedDict(zip(cols, row))))
    return wrapped

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
        dialect: str = "postgres",
        on_close: Callable[[Any], None] | None = None,
        reconnect: Callable[[], Any] | None = None,
    ):
        self.conn = conn
        self.dialect = "postgres"
        self._on_close = on_close
        self._reconnect = reconnect
        self._closed = False

    def execute(self, query: str, params: tuple = ()):
        retried = False
        while True:
            cur = self.conn.cursor()
            try:
                cur.execute(query, params)
                return CompatCursor(cur)
            except Exception as exc:
                try:
                    self.conn.rollback()
                except Exception:
                    pass
                
                exc_msg = str(exc).lower()
                if ("25p02" in exc_msg or "transaction is aborted" in exc_msg) and not retried:
                    retried = True
                    continue

                if not retried:
                    from sqlalchemy.exc import DBAPIError, OperationalError
                    if isinstance(exc, (OperationalError, DBAPIError)) or "connection" in exc_msg:
                        self._reset_postgres_connection()
                        retried = True
                        continue
                raise

    def executescript(self, script: str):
        from app.core.sql_compat import split_sql_script
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


class ConnectionPoolManager:
    def __init__(self):
        self._engines: dict[str, Engine] = {}
        self._engine_lock = threading.Lock()

    def _env_int(self, name: str, default: int, minimum: int = 0, maximum: int | None = None) -> int:
        try:
            value = int(os.environ.get(name, str(default)) or default)
        except Exception:
            value = default
        value = max(minimum, value)
        if maximum is not None:
            value = min(maximum, value)
        return value

    def sqlalchemy_database_url(self, database_url: str) -> str:
        url = str(database_url or "").strip()
        if url.startswith("postgresql://"):
            return "postgresql+pg8000://" + url[len("postgresql://") :]
        if url.startswith("postgres://"):
            return "postgresql+pg8000://" + url[len("postgres://") :]
        return url

    def create_database_engine(self, database_url: str) -> Engine:
        engine_url = self.sqlalchemy_database_url(database_url)
        return create_engine(
            engine_url,
            future=True,
            pool_pre_ping=True,
            pool_size=self._env_int("FAB_PG_POOL_SIZE", 10, 1, 200),
            max_overflow=self._env_int("FAB_PG_POOL_MAX_OVERFLOW", 10, 0, 500),
            pool_timeout=self._env_int("FAB_PG_POOL_TIMEOUT", 30, 1, 300),
            pool_recycle=self._env_int("FAB_PG_POOL_RECYCLE_SECONDS", 1800, 60, 86400),
        )

    def get_database_engine(self, database_url: str) -> Engine:
        raw_url = str(database_url or "").strip()
        with self._engine_lock:
            engine = self._engines.get(raw_url)
            if engine is None:
                engine = self.create_database_engine(raw_url)
                self._engines[raw_url] = engine
            return engine

    def connect_database(self, database_url: str) -> CompatConnection:
        raw_url = str(database_url or "").strip()
        try:
            engine = self.get_database_engine(raw_url)
            conn = engine.raw_connection()
        except Exception as e:
            err_msg = str(e).lower()
            if "does not exist" in err_msg or "3d000" in err_msg:
                parsed = urlparse(raw_url)
                database = parsed.path.lstrip("/")
                port_part = f":{parsed.port}" if parsed.port else ""
                pass_part = f":{parsed.password}" if parsed.password else ""
                user_part = f"{parsed.username}{pass_part}@" if parsed.username else ""
                postgres_url = f"{parsed.scheme}://{user_part}{parsed.hostname}{port_part}/postgres"
                
                pg_engine = create_engine(
                    self.sqlalchemy_database_url(postgres_url),
                    isolation_level="AUTOCOMMIT",
                    future=True,
                )
                with pg_engine.connect() as pg_conn:
                    pg_conn.execute(text(f'CREATE DATABASE "{database}"'))
                pg_engine.dispose()
                
                engine = self.get_database_engine(raw_url)
                conn = engine.raw_connection()
            elif "authentification" in err_msg or "password authentication failed" in err_msg or "28p01" in err_msg:
                raise RuntimeError("Erreur critique d'authentification PostgreSQL. Verifie le mot de passe dans .env") from e
            else:
                raise RuntimeError(f"Impossible de se connecter a la base de donnees PostgreSQL: {e}") from e

        def _reconnect():
            return engine.raw_connection()

        return CompatConnection(
            conn,
            dialect="postgres",
            on_close=lambda c: c.close(),
            reconnect=_reconnect,
        )

    def postgres_pool_status(self, database_url: str) -> dict[str, int | str]:
        pool = self.get_database_engine(database_url).pool
        status: dict[str, int | str] = {"engine": "postgres"}
        for key, method_name in (
            ("size", "size"),
            ("checkedin", "checkedin"),
            ("checkedout", "checkedout"),
            ("overflow", "overflow"),
        ):
            method = getattr(pool, method_name, None)
            if callable(method):
                try:
                    status[key] = int(method())
                except Exception:
                    pass
        return status

pool_manager = ConnectionPoolManager()
