"""
Responsibility: High-level database orchestration (migrations, health checks, request connections).
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path
from threading import RLock

from sqlalchemy import inspect, text

from app.core.config import settings
from app.core.runtime_paths import ensure_runtime_dirs
from app.core.schema_bootstrap import bootstrap_schema
from app.core.db import connect_database, sqlalchemy_database_url


_BOOTSTRAP_LOCK = RLock()
_BOOTSTRAPPED = False

def create_request_connection():
    """Create a new database connection for the current request context."""
    ensure_runtime_dirs()
    return connect_database(settings.database_url)

def _load_alembic():
    if getattr(sys, "frozen", False):
        command = importlib.import_module("alembic.command")
        config_mod = importlib.import_module("alembic.config")
        return command, config_mod.Config

    original_sys_path = list(sys.path)
    base_dir = str(settings.base_dir.resolve())
    try:
        sys.path = [entry for entry in sys.path if str(Path(entry).resolve()) != base_dir]
        command = importlib.import_module("alembic.command")
        config_mod = importlib.import_module("alembic.config")
        return command, config_mod.Config
    finally:
        sys.path = original_sys_path

def _alembic_script_location() -> Path:
    bundled_location = settings.base_dir / "migration_scripts" / "alembic"
    if bundled_location.exists():
        return bundled_location
    return settings.base_dir / "alembic"

def _alembic_config():
    _, Config = _load_alembic()
    cfg = Config(str(settings.base_dir / "alembic.ini"))
    cfg.set_main_option("script_location", str(_alembic_script_location()))
    cfg.set_main_option("sqlalchemy.url", sqlalchemy_database_url(settings.database_url))
    return cfg

def _alembic_version_exists() -> bool:
    from app.core.db import get_database_engine
    engine = get_database_engine(settings.database_url)
    try:
        return inspect(engine).has_table("alembic_version")
    except Exception:
        return False

def run_alembic_upgrade() -> None:
    if not (settings.base_dir / "alembic.ini").exists():
        return
    command, _ = _load_alembic()
    cfg = _alembic_config()
    if not _alembic_version_exists():
        command.stamp(cfg, "base")
    command.upgrade(cfg, "head")

def bootstrap_and_migrate() -> None:
    """Initialize schema and run migrations if necessary."""
    global _BOOTSTRAPPED
    with _BOOTSTRAP_LOCK:
        if _BOOTSTRAPPED:
            return
        ensure_runtime_dirs()
        bootstrap_schema()
        run_alembic_upgrade()
        _BOOTSTRAPPED = True

def healthcheck() -> bool:
    """Perform a basic connectivity check to the database."""
    try:
        from app.core.db import get_database_engine
        engine = get_database_engine(settings.database_url)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        import logging
        logging.getLogger("fabouanes").error("Database healthcheck failed: %s", e)
        return False

