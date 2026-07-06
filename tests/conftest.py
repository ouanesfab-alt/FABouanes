import os

# Set test environment variables before any application code is imported
os.environ["FASTAPI_ENV"] = "test"
os.environ.setdefault("SECRET_KEY", "test-secret-key-pytest-unit-only")
os.environ.setdefault("FAB_DESKTOP", "0")
os.environ.setdefault("DATABASE_URL", "postgresql://fake@localhost/fake_test")
os.environ.setdefault("REDIS_URL", "")
os.environ.setdefault("FAB_DISABLE_BACKGROUND_JOBS", "1")
