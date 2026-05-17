from __future__ import annotations

import os
import sqlite3
import queue
from threading import Lock

def _env_int(name: str, default: int, minimum: int = 0, maximum: int | None = None) -> int:
    try:
        value = int(os.environ.get(name, str(default)) or default)
    except Exception:
        value = default
    value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value

def _sqlite_pragmas() -> tuple[str, ...]:
    busy_timeout = _env_int("FAB_SQLITE_BUSY_TIMEOUT_MS", 15000, 1000, 60000)
    cache_kib = _env_int("FAB_SQLITE_CACHE_KIB", 131072, 8192, 1048576)
    mmap_size = _env_int("FAB_SQLITE_MMAP_BYTES", 536870912, 0, 2147483647)
    wal_autocheckpoint = _env_int("FAB_SQLITE_WAL_AUTOCHECKPOINT", 2000, 100, 10000)
    return (
        "PRAGMA foreign_keys = ON",
        f"PRAGMA busy_timeout = {busy_timeout}",
        "PRAGMA journal_mode = WAL",
        "PRAGMA synchronous = NORMAL",
        "PRAGMA temp_store = MEMORY",
        f"PRAGMA cache_size = -{cache_kib}",
        f"PRAGMA mmap_size = {mmap_size}",
        f"PRAGMA wal_autocheckpoint = {wal_autocheckpoint}",
        "PRAGMA analysis_limit = 1000",
        "PRAGMA optimize",
    )

class SQLiteConnectionPool:
    """Thread-safe SQLite connection pool to avoid open/close overhead per request."""

    def __init__(self, db_path: str, max_size: int = 8):
        self._path = db_path
        self._max_size = max(2, max_size)
        self._pool: queue.Queue[sqlite3.Connection] = queue.Queue(maxsize=self._max_size)
        self._cached_statements = _env_int("FAB_SQLITE_CACHED_STATEMENTS", 512, 64, 4096)

    def get(self) -> sqlite3.Connection:
        import time
        try:
            item = self._pool.get_nowait()
            if isinstance(item, tuple):
                conn, last_used = item
            else:
                conn, last_used = item, 0.0
            
            if time.monotonic() - last_used > 60.0:
                try:
                    conn.execute("SELECT 1").close()
                except Exception:
                    try:
                        conn.close()
                    except Exception:
                        pass
                    return self._new_connection()
            return conn
        except queue.Empty:
            return self._new_connection()

    def put(self, conn: sqlite3.Connection) -> None:
        import time
        try:
            self._pool.put_nowait((conn, time.monotonic()))
        except queue.Full:
            try:
                conn.close()
            except Exception:
                pass

    def _new_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            self._path,
            timeout=30,
            cached_statements=self._cached_statements,
            check_same_thread=False
        )
        conn.row_factory = sqlite3.Row
        for pragma in _sqlite_pragmas():
            try:
                conn.execute(pragma).close()
            except sqlite3.DatabaseError:
                pass
        return conn

_SQLITE_POOLS: dict[str, SQLiteConnectionPool] = {}
_SQLITE_POOL_LOCK = Lock()

def get_sqlite_pool(db_path: str) -> SQLiteConnectionPool:
    with _SQLITE_POOL_LOCK:
        pool = _SQLITE_POOLS.get(db_path)
        if pool is None:
            max_size = _env_int("FAB_SQLITE_POOL_SIZE", 8, 2, 32)
            pool = SQLiteConnectionPool(db_path, max_size)
            _SQLITE_POOLS[db_path] = pool
        return pool
