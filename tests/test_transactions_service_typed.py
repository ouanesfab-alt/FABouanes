import pytest
from app.modules.accounting.service import transactions_context


@pytest.mark.asyncio
async def test_transactions_context_all():
    ctx = await transactions_context(filter_type="all")
    assert "transactions" in ctx
    assert "pagination" in ctx
    assert ctx["filter_type"] == "all"
    assert isinstance(ctx["transactions"], list)


@pytest.mark.asyncio
async def test_transactions_context_filters():
    # Filter purchase
    p_ctx = await transactions_context(filter_type="purchase", filter_name="test", filter_date="2026-05-01")
    assert p_ctx["filter_type"] == "purchase"
    assert p_ctx["filter_name"] == "test"
    assert p_ctx["filter_date"] == "2026-05-01"

    # Filter sale
    s_ctx = await transactions_context(filter_type="sale", filter_operation="vente")
    assert s_ctx["filter_type"] == "sale"

    # Filter payment
    pay_ctx = await transactions_context(filter_type="payment", filter_name="client")
    assert pay_ctx["filter_type"] == "payment"


@pytest.mark.asyncio
async def test_transactions_context_empty_type():
    ctx = await transactions_context(filter_type="unknown")
    assert ctx["transactions"] == []
    assert ctx["pagination"]["total"] == 0
