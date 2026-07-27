import os

# Set test environment variables before any application code is imported
os.environ["FASTAPI_ENV"] = "test"
os.environ.setdefault("SECRET_KEY", "test-secret-key-pytest-unit-only")
os.environ.setdefault("FAB_DESKTOP", "0")
# Base de données de test PostgreSQL — peut être surchargée via TEST_DATABASE_URL
_test_db_url = os.environ.get("TEST_DATABASE_URL", "postgresql://postgres:0000@localhost:5432/fabouanes_test")
os.environ.setdefault("DATABASE_URL", _test_db_url)
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
