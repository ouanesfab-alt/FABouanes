import os
import sys
from datetime import datetime, date
from decimal import Decimal
from unittest.mock import MagicMock, patch

os.environ["SECRET_KEY"] = "test-secret-key-pytest-unit-only"
os.environ["FASTAPI_ENV"] = "test"
os.environ["FAB_DESKTOP"] = "0"
os.environ["DATABASE_URL"] = "postgresql://fake@localhost/fake_test"
os.environ["REDIS_URL"] = ""
os.environ["FAB_DISABLE_BACKGROUND_JOBS"] = "1"

# Mock DB connection
class MockDBCursor:
    def __init__(self):
        self.description = [("id",), ("name",), ("value",)]
        self.rowcount = 1
        self.lastrowid = 1
        self._rows = [(1, "test", "1")]
        self._index = 0

    def execute(self, sql, params=()):
        print(f"Mock execute SQL: {sql} with {params}")
        self._index = 0
        return self

    def fetchall(self):
        return self._rows

    def fetchone(self):
        if self._index < len(self._rows):
            r = self._rows[self._index]
            self._index += 1
            return r
        return None

    def close(self):
        pass

class MockDBConnection:
    def cursor(self):
        return MockDBCursor()
    def commit(self):
        pass
    def rollback(self):
        pass
    def close(self):
        pass
    def executescript(self, script):
        print(f"Mock executescript: {script[:50]}...")
        pass
    def execute(self, sql, params=()):
        print(f"Mock connection execute SQL: {sql}")
        return MockDBCursor().execute(sql, params)

mock_conn = MockDBConnection()

# Now patch the database connection in app.core.db_helpers before import
import app.core.db_helpers
app.core.db_helpers.db_manager.connect_database = MagicMock(return_value=mock_conn)
app.core.db_helpers.pool_manager.connect_database = MagicMock(return_value=mock_conn)

# Let's test if query_db runs our mock
from app.core.db_access import query_db, execute_db

res = query_db("SELECT value FROM app_settings WHERE key = %s", ("test_key",))
print(f"Result: {res}")
