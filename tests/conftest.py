import os
import sys

# Silence known Python 3.11 Windows ProactorEventLoop __del__ access violation during GC
if sys.platform == "win32":
    try:
        from asyncio.proactor_events import _ProactorBasePipeTransport
        _orig_del = getattr(_ProactorBasePipeTransport, "__del__", None)
        def _safe_proactor_del(self, *args, **kwargs):
            try:
                if _orig_del:
                    _orig_del(self, *args, **kwargs)
            except Exception:
                pass
        _ProactorBasePipeTransport.__del__ = _safe_proactor_del
    except Exception:
        pass

# Set test environment variables before any application code is imported
os.environ["FASTAPI_ENV"] = "test"
os.environ.setdefault("SECRET_KEY", "test-secret-key-pytest-unit-only")
os.environ.setdefault("FAB_DESKTOP", "0")
# Base de données de test PostgreSQL — surchargeable via TEST_DATABASE_URL
def _resolve_test_db_url() -> str:
    if "TEST_DATABASE_URL" in os.environ:
        return os.environ["TEST_DATABASE_URL"]
    # Deriver depuis DATABASE_URL si configurée (ex: postgres:postgres)
    db_env = os.environ.get("DATABASE_URL", "")
    if "127.0.0.1" in db_env or "localhost" in db_env:
        from urllib.parse import urlparse, urlunparse
        p = urlparse(db_env)
        return urlunparse((p.scheme, p.netloc, "/fabouanes_test", p.params, p.query, p.fragment))
    return "postgresql://postgres:postgres@localhost:5432/fabouanes_test"

_test_db_url = _resolve_test_db_url()
os.environ["DATABASE_URL"] = _test_db_url
os.environ.setdefault("REDIS_URL", "")
os.environ.setdefault("FAB_DISABLE_BACKGROUND_JOBS", "1")


def _ensure_test_db_exists():
    try:
        from urllib.parse import urlparse
        import pg8000
        parsed = urlparse(_test_db_url)
        db_name = parsed.path.lstrip("/")
        if not db_name or not parsed.hostname:
            return
        user = parsed.username or "postgres"
        password = parsed.password or ""
        host = parsed.hostname or "localhost"
        port = parsed.port or 5432

        conn = pg8000.connect(user=user, password=password, host=host, port=port, database="postgres")
        conn.autocommit = True
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
        if not cursor.fetchone():
            cursor.execute(f'CREATE DATABASE "{db_name}"')
        conn.close()
    except Exception as e:
        import logging
        logging.warning("Could not auto-create test database: %s", e)

_ensure_test_db_exists()

try:
    from app.core.database import bootstrap_and_migrate
    bootstrap_and_migrate()
except Exception as e:
    import logging
    logging.warning("Could not bootstrap test database: %s", e)

import pytest

@pytest.fixture
def db_session():
    """Provides a database session for tests."""
    from app.core.database import SessionLocal
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

@pytest.fixture
def test_client():
    """Provides a FastAPI TestClient instance."""
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as client:
        yield client

