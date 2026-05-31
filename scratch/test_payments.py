import os
import sys
from unittest.mock import MagicMock

sys.modules["redis"] = MagicMock()
sys.modules["redis.asyncio"] = MagicMock()

os.environ["DATABASE_URL"] = "postgresql://fake@localhost/fake_test"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["FASTAPI_ENV"] = "test"
os.environ["FAB_DESKTOP"] = "0"

import tests.test_services_coverage as tc

def run():
    for route in ["/", "/login", "/dashboard", "/clients", "/contacts", "/operations", "/production", "/admin", "/reports", "/search", "/change-password"]:
        try:
            response = tc.client.get(route)
            print(f"ROUTE {route}: STATUS {response.status_code}")
        except Exception as e:
            print(f"ROUTE {route}: ERROR {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()

run()
