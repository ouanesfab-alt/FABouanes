from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.services.alert_service import (
    check_overdue_clients,
    broadcast_overdue_alerts,
    check_stock_alerts
)


@contextmanager
def dummy_transaction():
    yield


@pytest.mark.asyncio
async def test_check_overdue_clients() -> None:
    """Should query overdue clients with correct cutoff date."""
    expected_cutoff = (date.today() - timedelta(days=15)).isoformat()
    mock_rows = [
        {"id": 1, "name": "Client A", "balance": 500.0, "derniere_operation": "2026-04-01", "jours_inactif": 45}
    ]
    
    with patch("app.services.alert_service.query_db_async", new_callable=AsyncMock) as mock_query:
        mock_query.return_value = mock_rows
        
        result = await check_overdue_clients(overdue_days=15)
        
        assert result == mock_rows
        # Verify query received the calculated cutoff
        args, kwargs = mock_query.call_args
        assert expected_cutoff in args[1]


@pytest.mark.asyncio
async def test_broadcast_overdue_alerts_already_locked() -> None:
    """If the advisory lock cannot be acquired, should return 0 and skip broadcast."""
    with patch("app.services.alert_service.db_transaction", dummy_transaction), \
         patch("app.services.alert_service.query_db_async", new_callable=AsyncMock) as mock_query, \
         patch("app.services.alert_service.manager") as mock_manager:
        
        # lock acquired row is False
        mock_query.return_value = {"locked": False}
        
        res = await broadcast_overdue_alerts()
        
        assert res == 0
        mock_manager.broadcast_sync.assert_not_called()


@pytest.mark.asyncio
async def test_broadcast_overdue_alerts_success() -> None:
    """If lock is acquired and overdue clients exist, should broadcast alert payload."""
    mock_overdue = [
        {"id": 10, "name": "Overdue Corp", "balance": 1500.0, "jours_inactif": 35}
    ]
    
    with patch("app.services.alert_service.db_transaction", dummy_transaction), \
         patch("app.services.alert_service.query_db_async", new_callable=AsyncMock) as mock_query, \
         patch("app.services.alert_service.check_overdue_clients", new_callable=AsyncMock) as mock_check, \
         patch("app.services.alert_service.manager") as mock_manager:
        
        mock_query.return_value = {"locked": True}
        mock_check.return_value = mock_overdue
        
        res = await broadcast_overdue_alerts()
        
        assert res == 1
        mock_manager.broadcast_sync.assert_called_once()
        # Verify correct payload
        payload_str = mock_manager.broadcast_sync.call_args[0][0]
        payload = json.loads(payload_str)
        assert payload["type"] == "overdue_alert"
        assert payload["count"] == 1
        assert payload["clients"][0]["id"] == 10
        assert payload["clients"][0]["balance"] == 1500.0
        assert payload["clients"][0]["jours"] == 35


@pytest.mark.asyncio
async def test_check_stock_alerts_no_alerts() -> None:
    """If all items are above threshold, no alerts should be triggered."""
    with patch("app.services.alert_service.query_db_async", new_callable=AsyncMock) as mock_query, \
         patch("app.services.alert_service._trigger_alert", new_callable=AsyncMock) as mock_trigger:
        
        # Return empty list for: active alerts pre-fetch, raw materials, finished products
        mock_query.side_effect = [[], [], []]
        
        await check_stock_alerts()
        
        mock_trigger.assert_not_called()


@pytest.mark.asyncio
async def test_check_stock_alerts_trigger() -> None:
    """Should trigger alerts for raw materials and finished products under threshold."""
    under_raws = [{"id": 1, "name": "Raw X", "stock_qty": 5.0, "alert_threshold": 10.0}]
    under_products = [{"id": 5, "name": "Prod Y", "stock_qty": 2.0, "alert_threshold": 5.0}]
    
    with patch("app.services.alert_service.query_db_async", new_callable=AsyncMock) as mock_query, \
         patch("app.services.alert_service._trigger_alert", new_callable=AsyncMock) as mock_trigger:
        
        # First query returns active alerts (empty), then raws, then products
        mock_query.side_effect = [[], under_raws, under_products]
        
        await check_stock_alerts()
        
        # _trigger_alert now receives the active_alerts set as 6th argument
        assert mock_trigger.call_count == 2
        call_args_list = mock_trigger.call_args_list
        assert call_args_list[0][0][:5] == ("raw_material", 1, "Raw X", 5.0, 10.0)
        assert call_args_list[1][0][:5] == ("finished_product", 5, "Prod Y", 2.0, 5.0)


@pytest.mark.asyncio
async def test_trigger_alert_duplicate() -> None:
    """If alert was already triggered within last 24h, should not insert a new one."""
    with patch("app.services.alert_service.query_db_async", new_callable=AsyncMock) as mock_query, \
         patch("app.services.alert_service.execute_db_async", new_callable=AsyncMock) as mock_execute:
        
        # Duplicate exists
        mock_query.return_value = {"id": 100}
        
        from app.services.alert_service import _trigger_alert
        await _trigger_alert("raw_material", 1, "Raw X", 5.0, 10.0)
        
        mock_execute.assert_not_called()


@pytest.mark.asyncio
async def test_trigger_alert_new() -> None:
    """If no active duplicate alert exists, insert a new stock alert."""
    with patch("app.services.alert_service.query_db_async", new_callable=AsyncMock) as mock_query, \
         patch("app.services.alert_service.execute_db_async", new_callable=AsyncMock) as mock_execute:
        
        # No duplicate exists
        mock_query.return_value = None
        
        from app.services.alert_service import _trigger_alert
        await _trigger_alert("raw_material", 1, "Raw X", 5.0, 10.0)
        
        mock_execute.assert_called_once()
        args = mock_execute.call_args[0][0]
        params = mock_execute.call_args[0][1]
        assert "INSERT INTO stock_alerts" in args
        assert params == ("raw_material", 1, "Raw X", 5.0, 10.0)
