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
