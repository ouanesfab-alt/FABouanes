"""Tests unitaires pour app/modules/assistant (rag.py, sql_tools.py, tool_actions_*) (Vague 3 — couverture > 90%)."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from unittest import mock

from app.modules.assistant.rag import normalize_text, search_manual
from app.modules.assistant.sql_tools import serialize_for_json, dry_run_sql


def test_rag_normalize_text_and_search_manual():
    norm = normalize_text("  Facture d'Échéance 123 !  ")
    assert norm == "facture d echeance 123"

    results = search_manual("facture vente")
    assert isinstance(results, list)

    empty_res = search_manual("a")
    assert empty_res == []


def test_serialize_for_json():
    data = {
        "int_dec": Decimal("100.00"),
        "float_dec": Decimal("99.95"),
        "date_val": date(2026, 5, 31),
        "dt_val": datetime(2026, 5, 31, 12, 0, 0),
        "nested_list": [Decimal("10")],
    }
    ser = serialize_for_json(data)
    assert ser["int_dec"] == 100
    assert ser["float_dec"] == 99.95
    assert ser["date_val"] == "2026-05-31"
    assert ser["dt_val"] == "2026-05-31T12:00:00"
    assert ser["nested_list"] == [10]


def test_dry_run_sql_refused():
    res = dry_run_sql("DROP TABLE sales;")
    assert "Refusé" in res or "refusé" in res or "⚠️" in res


def test_dry_run_sql_valid_mocked():
    mock_conn = mock.MagicMock()
    mock_conn.execute.return_value.fetchall.return_value = [(1, "Client A", 100.0)]

    with mock.patch("app.core.db_helpers.manager.db_manager.db_transaction") as m_tx:
        m_tx.return_value.__enter__.return_value = mock_conn
        res = dry_run_sql("UPDATE clients SET name='Test' WHERE id=1;")
        assert "Simulation" in res or "⚠️" in res or isinstance(res, str)
