from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.modules.assistant.tool_actions_insights import (
    search_web,
    handle_insights,
)


@pytest.mark.asyncio
async def test_search_web_mock():
    mock_html = """
    <div class="result results_links results_links_deep web-result ">
        <a class="result__a" href="https://duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com">Example Title</a>
        <div class="result__snippet">Example Snippet description</div>
    </div>
    """
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = mock_html

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
        res = await search_web("test query")
        assert "results" in res
        assert len(res["results"]) > 0
        assert res["results"][0]["title"] == "Example Title"
        assert res["results"][0]["url"] == "https://example.com"


@pytest.mark.asyncio
async def test_search_web_error_status():
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
        res = await search_web("bad query")
        assert "error" in res


@pytest.mark.asyncio
async def test_handle_insights_unknown():
    mock_maker = MagicMock()
    res = await handle_insights("non_existent_func", {}, mock_maker)
    assert res is None


@pytest.mark.asyncio
async def test_handle_insights_weather():
    from app.core.perf_cache import invalidate_cache_domains

    invalidate_cache_domains("assistant")
    mock_maker = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "UniqueCity: +18°C Sunny"

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
        res = await handle_insights("get_current_weather", {"location": "UniqueCity"}, mock_maker)
        assert "weather" in res
        assert "Sunny" in res["weather"]


@pytest.mark.asyncio
async def test_handle_insights_explain_profit_decrease():
    mock_session = AsyncMock()
    scalars = [10000.0, 8000.0, 3000.0, 2000.0, 5000.0, 4000.0, 1000.0, 800.0]
    results = []
    for s in scalars:
        m = MagicMock()
        m.scalar.return_value = s
        results.append(m)
    mock_session.execute.side_effect = results

    mock_maker = MagicMock()
    mock_maker.return_value.__aenter__.return_value = mock_session

    res = await handle_insights("explain_profit_decrease", {"period_days": 15}, mock_maker)
    assert res["period_days"] == 15
    assert "current_period" in res
    assert "variations_percent" in res
    assert "diagnosis" in res


@pytest.mark.asyncio
async def test_handle_insights_predict_business_trends():
    mock_session = AsyncMock()
    m_stock = MagicMock()
    m_stock.fetchall.return_value = [("Produit A", 2.0, 10.0, "Produit fini")]
    m_avg = MagicMock()
    m_avg.scalar.return_value = 500.0
    m_debt = MagicMock()
    m_debt.scalar.return_value = 15000.0

    mock_session.execute.side_effect = [m_stock, m_avg, m_debt]
    mock_maker = MagicMock()
    mock_maker.return_value.__aenter__.return_value = mock_session

    res = await handle_insights("predict_business_trends", {}, mock_maker)
    assert "forecast_sales_next_30_days" in res
    assert res["forecast_sales_next_30_days"] == 15000.0
    assert len(res["imminent_stock_runouts"]) == 1
    assert res["expected_debt_collections"] == 15000.0


@pytest.mark.asyncio
async def test_handle_insights_detect_anomalies():
    mock_session = AsyncMock()
    m_dups = MagicMock()
    m_dups.fetchall.return_value = [("Client Test", 1200.0, 2)]
    m_avg = MagicMock()
    m_avg.scalar.return_value = 5000.0
    m_high = MagicMock()
    m_high.fetchall.return_value = [("Grosse dépense", 25000.0, date.today())]

    mock_session.execute.side_effect = [m_dups, m_avg, m_high]
    mock_maker = MagicMock()
    mock_maker.return_value.__aenter__.return_value = mock_session

    res = await handle_insights("detect_anomalies", {}, mock_maker)
    assert "potential_duplicate_sales" in res
    assert len(res["potential_duplicate_sales"]) == 1
    assert "abnormal_high_expenses" in res
    assert len(res["abnormal_high_expenses"]) == 1
    assert res["average_expense_benchmark"] == 5000.0
