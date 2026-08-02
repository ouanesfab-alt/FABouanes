"""
test_ultra_coverage_98.py — Comprehensive branch coverage test suite.
"""
from datetime import date, datetime
from decimal import Decimal

from app.core.db_helpers.manager import CompatRow
from app.modules.assistant.rag import search_manual, normalize_text, SYNONYM_MAP
from app.modules.assistant.sql_tools import serialize_for_json
from app.modules.assistant.sql_guard import validate_readonly_sql, get_allowed_write_tables
from app.core.permissions import has_permission, PERMISSION_DASHBOARD_READ
from app.core.helpers import async_compat

def test_compat_row_edge_cases():
    row_dict = {"id": 10, "name": "Test", "val": None}
    r = CompatRow(row_dict)
    assert r["id"] == 10
    assert r.get("missing", "default") == "default"
    assert len(r) == 3
    assert "name" in r
    assert list(iter(r)) == ["id", "name", "val"]

def test_rag_manual_search_branches():
    results = search_manual("vente client facture", limit=5)
    assert isinstance(results, list)
    
    empty_res = search_manual("", limit=3)
    assert empty_res == []
    
    norm = normalize_text("Éléphant & Maïs 50.40!")
    assert isinstance(norm, str)
    assert "facture" in SYNONYM_MAP

def test_sql_guard_validations():
    tables = get_allowed_write_tables()
    assert "sales" in tables
    
    res = validate_readonly_sql("SELECT * FROM sales WHERE id = 1")
    assert res.ok is True

def test_sql_tools_serialization():
    data = {
        "price": Decimal("50.40"),
        "qty": Decimal("100"),
        "created": date(2026, 7, 31),
        "updated": datetime(2026, 7, 31, 21, 55, 0),
        "items": [Decimal("12.50"), "test"]
    }
    serialized = serialize_for_json(data)
    assert serialized["price"] == 50.4
    assert serialized["qty"] == 100
    assert "2026-07-31" in serialized["created"]

def test_helpers_formatters():
    @async_compat
    async def sample_async_func():
        return 42

    res = sample_async_func()
    assert res == 42

def test_permissions_edge_cases():
    user = {"role": "admin", "custom_permissions": [PERMISSION_DASHBOARD_READ]}
    assert has_permission(user, PERMISSION_DASHBOARD_READ) is True
    assert has_permission(None, PERMISSION_DASHBOARD_READ) is False
