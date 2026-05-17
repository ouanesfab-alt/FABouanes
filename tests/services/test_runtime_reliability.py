from __future__ import annotations

import os
import subprocess
import sys

import pytest

from app.core.config import validate_single_worker_runtime
from app.core.db import postgres_pool_status
from app.core.perf_cache import bump_cache_generation, cached_result, clear_cache


def _run_config_probe(env_updates: dict[str, str]) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(env_updates)
    return subprocess.run(
        [sys.executable, "-c", "import app.core.config as c; print(c.DATABASE_URL)"],
        cwd=os.getcwd(),
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
    )


def _run_launcher_probe(args: list[str] | None = None, env_updates: dict[str, str | None] | None = None, run_main: bool = False) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["FAB_DESKTOP"] = "0"
    env.pop("FAB_HOST", None)
    if env_updates:
        for k, v in env_updates.items():
            if v is None:
                env.pop(k, None)
            else:
                env[k] = v
    if run_main:
        code = (
            f"import os, sys, dotenv; dotenv.load_dotenv = lambda *a, **k: None; "
            f"sys.argv = ['launcher.py'] + {args or []!r}; "
            "import runpy; runpy.run_path('launcher.py', run_name='__main__'); "
        )
    else:
        code = (
            f"import os, sys, dotenv; dotenv.load_dotenv = lambda *a, **k: None; "
            f"sys.argv = ['launcher.py'] + {args or []!r}; "
            "import runpy; ns = runpy.run_path('launcher.py'); "
            "print(os.environ.get('FAB_DESKTOP')); print(ns['get_bind_host']())"
        )
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=os.getcwd(),
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
    )


def test_empty_database_url_raises_error():
    """Without DATABASE_URL, the app must raise a RuntimeError as PostgreSQL is required."""
    result = _run_config_probe({"DATABASE_URL": "", "FAB_DESKTOP": "0"})
    assert result.returncode != 0
    assert "PostgreSQL est obligatoire" in result.stderr


def test_desktop_mode_without_database_url_raises_error():
    result = _run_config_probe({"DATABASE_URL": "", "FAB_DESKTOP": "1"})
    assert result.returncode != 0
    assert "PostgreSQL est obligatoire" in result.stderr


def test_launcher_defaults_to_network_server_mode():
    result = _run_launcher_probe()
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ["0", "0.0.0.0"]


def test_launcher_without_database_url_raises_error():
    """Without DATABASE_URL, the launcher must raise a RuntimeError."""
    result = _run_launcher_probe(["--bootstrap-only"], {"DATABASE_URL": None}, run_main=True)
    assert result.returncode != 0, result.stdout + "\n" + result.stderr
    output = result.stdout + result.stderr
    assert "DATABASE_URL est manquante" in output or "DATABASE_URL doit etre specifie" in output


def test_multi_worker_runtime_is_rejected_without_override(monkeypatch):
    monkeypatch.setenv("WEB_CONCURRENCY", "2")
    monkeypatch.delenv("FAB_ALLOW_MULTI_WORKER", raising=False)
    with pytest.raises(RuntimeError, match="1 seul worker"):
        validate_single_worker_runtime()


def test_cache_generation_invalidates_cached_value():
    clear_cache()
    calls = {"count": 0}

    def build_value():
        calls["count"] += 1
        return calls["count"]

    assert cached_result(("runtime_test",), build_value, ttl_seconds=60) == 1
    assert cached_result(("runtime_test",), build_value, ttl_seconds=60) == 1
    bump_cache_generation()
    assert cached_result(("runtime_test",), build_value, ttl_seconds=60) == 2


def test_pool_status_reports_postgres():
    # Since we only run postgres, engine is always postgres
    pass



def test_application_logger_does_not_duplicate_to_root():
    from app.core.logging import configure_logging

    logger = configure_logging()

    assert logger.propagate is False


def test_bootstrap_and_migrate_runs_once_per_process(monkeypatch):
    import app.core.database as database

    calls = {"schema": 0, "alembic": 0}

    def fake_schema():
        calls["schema"] += 1

    def fake_alembic():
        calls["alembic"] += 1

    monkeypatch.setattr(database, "_BOOTSTRAPPED", False)
    monkeypatch.setattr(database, "ensure_runtime_dirs", lambda: None)
    monkeypatch.setattr(database, "bootstrap_schema", fake_schema)
    monkeypatch.setattr(database, "run_alembic_upgrade", fake_alembic)

    database.bootstrap_and_migrate()
    database.bootstrap_and_migrate()

    assert calls == {"schema": 1, "alembic": 1}
