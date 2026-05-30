from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.modules.catalog.service import CatalogService, resolve_name_from_form, RAW_MATERIAL_PRESETS
from app.modules.catalog.schemas_validation import RawMaterialCreateSchema, FinishedProductCreateSchema, RawMaterialUpdateSchema
from app.core.models import RawMaterial, FinishedProduct

# ---------------------------------------------------------------------------
# resolve_name_from_form  (pure logic, no mocks needed)
# ---------------------------------------------------------------------------

def test_resolve_name_empty_returns_autre() -> None:
    """Empty name should return 'autre'."""
    assert resolve_name_from_form({"name": "", "kind": "raw"}) == "autre"


def test_resolve_name_preset_kept_as_is() -> None:
    """A preset name should be kept verbatim."""
    assert resolve_name_from_form({"name": "Maïs", "kind": "raw"}) == "Maïs"


def test_resolve_name_custom_gets_prefix() -> None:
    """Custom name should be prefixed with 'autre: '."""
    assert resolve_name_from_form({"name": "Mon produit", "kind": "raw"}) == "autre: Mon produit"


def test_resolve_name_already_prefixed() -> None:
    """Name already starting with 'autre:' should keep the prefix."""
    result = resolve_name_from_form({"name": "autre: Mon produit", "kind": "raw"})
    assert result == "autre: Mon produit"


# ---------------------------------------------------------------------------
# _build_catalog_context — velocity & alert status
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_build_catalog_context_velocity_days_left() -> None:
    """Should compute days_left from velocity = consumed_30d / 30."""
    service = CatalogService(session=AsyncMock())
    service.raw_repo = AsyncMock()
    service.finished_repo = AsyncMock()

    service.raw_repo.get_30d_velocities.return_value = {1: 10.0}   # velocity = 10/day
    service.finished_repo.get_30d_velocities.return_value = {2: 5.0}       # velocity = 5/day
    service.raw_repo.get_all_ordered.return_value = [
        RawMaterial(id=1, name="Maïs", unit="kg", stock_qty=50.0, avg_cost=10.0, sale_price=15.0, alert_threshold=5.0, threshold_qty=5.0)
    ]
    service.finished_repo.get_all_ordered.return_value = [
        FinishedProduct(id=2, name="Aliment", default_unit="kg", stock_qty=100.0, avg_cost=20.0, sale_price=30.0)
    ]

    result = await service._build_catalog_context()

    products = result["all_products"]
    raw = next(p for p in products if p["row_kind"] == "raw")
    fin = next(p for p in products if p["row_kind"] == "finished")
    assert raw["days_left"] == 5    # 50 / 10 = 5
    assert fin["days_left"] == 20   # 100 / 5 = 20


@pytest.mark.asyncio
async def test_build_catalog_context_critical_alert() -> None:
    """Items with days_left <= 7 should have CRITICAL autonomy_status."""
    service = CatalogService(session=AsyncMock())
    service.raw_repo = AsyncMock()
    service.finished_repo = AsyncMock()

    service.raw_repo.get_30d_velocities.return_value = {1: 10.0}   # velocity = 10/day
    service.finished_repo.get_30d_velocities.return_value = {}
    service.raw_repo.get_all_ordered.return_value = [
        RawMaterial(id=1, name="Maïs", unit="kg", stock_qty=30.0, avg_cost=10.0, sale_price=15.0, alert_threshold=5.0, threshold_qty=5.0)
    ]
    service.finished_repo.get_all_ordered.return_value = []

    result = await service._build_catalog_context()

    raw = result["all_products"][0]
    assert raw["days_left"] == 3       # 30 / 10 = 3
    assert raw["is_low"] is True
    assert raw["autonomy_status"] == "CRITICAL"


@pytest.mark.asyncio
async def test_build_catalog_context_warning_alert() -> None:
    """Items with 7 < days_left <= 14 should have WARNING status."""
    service = CatalogService(session=AsyncMock())
    service.raw_repo = AsyncMock()
    service.finished_repo = AsyncMock()

    service.raw_repo.get_30d_velocities.return_value = {1: 1.0}   # velocity = 1/day
    service.finished_repo.get_30d_velocities.return_value = {}
    service.raw_repo.get_all_ordered.return_value = [
        RawMaterial(id=1, name="Maïs", unit="kg", stock_qty=12.0, avg_cost=10.0, sale_price=15.0, alert_threshold=2.0, threshold_qty=2.0)
    ]
    service.finished_repo.get_all_ordered.return_value = []

    result = await service._build_catalog_context()

    raw = result["all_products"][0]
    assert raw["days_left"] == 12
    assert raw["autonomy_status"] == "WARNING"


@pytest.mark.asyncio
async def test_build_catalog_context_ok_status() -> None:
    """Items with days_left > 14 should have OK status."""
    service = CatalogService(session=AsyncMock())
    service.raw_repo = AsyncMock()
    service.finished_repo = AsyncMock()

    service.raw_repo.get_30d_velocities.return_value = {1: 1.0}   # velocity = 1/day
    service.finished_repo.get_30d_velocities.return_value = {}
    service.raw_repo.get_all_ordered.return_value = [
        RawMaterial(id=1, name="Maïs", unit="kg", stock_qty=100.0, avg_cost=10.0, sale_price=15.0, alert_threshold=2.0, threshold_qty=2.0)
    ]
    service.finished_repo.get_all_ordered.return_value = []

    result = await service._build_catalog_context()

    raw = result["all_products"][0]
    assert raw["days_left"] == 100
    assert raw["is_low"] is False
    assert raw["autonomy_status"] == "OK"


@pytest.mark.asyncio
async def test_build_catalog_context_below_threshold_is_low() -> None:
    """Raw material below threshold_qty should be marked is_low even without velocity."""
    service = CatalogService(session=AsyncMock())
    service.raw_repo = AsyncMock()
    service.finished_repo = AsyncMock()

    service.raw_repo.get_30d_velocities.return_value = {}  # no velocity data
    service.finished_repo.get_30d_velocities.return_value = {}
    service.raw_repo.get_all_ordered.return_value = [
        RawMaterial(id=1, name="Sel", unit="kg", stock_qty=3.0, avg_cost=5.0, sale_price=8.0, alert_threshold=10.0, threshold_qty=10.0)
    ]
    service.finished_repo.get_all_ordered.return_value = []

    result = await service._build_catalog_context()

    raw = result["all_products"][0]
    assert raw["is_low"] is True
    assert raw["autonomy_status"] == "CRITICAL"


# ---------------------------------------------------------------------------
# create_catalog_item
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_raw_material() -> None:
    """Creating a raw material should INSERT and emit a DomainEvent."""
    service = CatalogService(session=AsyncMock())
    service.raw_repo = AsyncMock()

    schema = RawMaterialCreateSchema(
        name="Maïs", unit="kg", stock_qty=100.0, avg_cost=10.0, sale_price=15.0, alert_threshold=5.0
    )
    created_mock = RawMaterial(id=42, name="Maïs", unit="kg", stock_qty=100.0, avg_cost=10.0, sale_price=15.0, alert_threshold=5.0, threshold_qty=5.0)
    service.raw_repo.create.return_value = created_mock

    with patch("app.modules.catalog.service.emit") as mock_emit:
        created = await service.create_raw_material(schema)

        assert created.id == 42
        assert created.name == "Maïs"
        service.raw_repo.create.assert_called_once()
        mock_emit.assert_called_once()


@pytest.mark.asyncio
async def test_create_finished_product() -> None:
    """Creating a finished product should INSERT into finished_products."""
    service = CatalogService(session=AsyncMock())
    service.finished_repo = AsyncMock()

    schema = FinishedProductCreateSchema(
        name="Aliment Pondeuse", default_unit="kg", stock_qty=50.0, sale_price=30.0, avg_cost=20.0
    )
    created_mock = FinishedProduct(id=7, name="Aliment Pondeuse", default_unit="kg", stock_qty=50.0, sale_price=30.0, avg_cost=20.0)
    service.finished_repo.create.return_value = created_mock

    with patch("app.modules.catalog.service.emit") as mock_emit:
        created = await service.create_finished_product(schema)

        assert created.id == 7
        assert created.name == "Aliment Pondeuse"
        service.finished_repo.create.assert_called_once()
        mock_emit.assert_called_once()


# ---------------------------------------------------------------------------
# delete_raw_material / delete_finished_product
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_raw_material_linked_returns_false() -> None:
    """If raw material has linked purchases/sales, deletion should be refused."""
    service = CatalogService(session=AsyncMock())
    service.raw_repo = AsyncMock()

    service.raw_repo.get_by_id.return_value = RawMaterial(id=1, name="Maïs")
    service.raw_repo.is_linked.return_value = True

    result = await service.delete_raw_material(1)
    assert result is False
    service.raw_repo.delete.assert_not_called()


@pytest.mark.asyncio
async def test_delete_raw_material_success() -> None:
    """Unlinked raw material should be deleted and emit DomainEvent."""
    service = CatalogService(session=AsyncMock())
    service.raw_repo = AsyncMock()

    service.raw_repo.get_by_id.return_value = RawMaterial(id=1, name="Sel")
    service.raw_repo.is_linked.return_value = False
    service.raw_repo.delete.return_value = True

    with patch("app.modules.catalog.service.emit") as mock_emit:
        result = await service.delete_raw_material(1)

        assert result is True
        service.raw_repo.delete.assert_called_once_with(1)
        mock_emit.assert_called_once()


@pytest.mark.asyncio
async def test_delete_product_linked_returns_false() -> None:
    """If finished product has linked sales, deletion should be refused."""
    service = CatalogService(session=AsyncMock())
    service.finished_repo = AsyncMock()

    service.finished_repo.get_by_id.return_value = FinishedProduct(id=1, name="Aliment")
    service.finished_repo.is_linked.return_value = True

    result = await service.delete_finished_product(1)
    assert result is False
    service.finished_repo.delete.assert_not_called()


@pytest.mark.asyncio
async def test_delete_product_success() -> None:
    """Unlinked finished product should be deleted."""
    service = CatalogService(session=AsyncMock())
    service.finished_repo = AsyncMock()

    service.finished_repo.get_by_id.return_value = FinishedProduct(id=2, name="Aliment")
    service.finished_repo.is_linked.return_value = False
    service.finished_repo.delete.return_value = True

    with patch("app.modules.catalog.service.emit") as mock_emit:
        result = await service.delete_finished_product(2)
        assert result is True
        service.finished_repo.delete.assert_called_once_with(2)
        mock_emit.assert_called_once()


# ---------------------------------------------------------------------------
# update_raw_material
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_raw_material() -> None:
    """Should UPDATE the raw material and emit a DomainEvent with before/after."""
    service = CatalogService(session=AsyncMock())
    service.raw_repo = AsyncMock()

    schema = RawMaterialUpdateSchema(
        name="Maïs", unit="kg", stock_qty=200.0, avg_cost=12.0, sale_price=18.0, alert_threshold=10.0
    )
    before = RawMaterial(id=1, name="Maïs", unit="kg", stock_qty=100.0, avg_cost=10.0, sale_price=15.0, alert_threshold=5.0)
    after = RawMaterial(id=1, name="Maïs", unit="kg", stock_qty=200.0, avg_cost=12.0, sale_price=18.0, alert_threshold=10.0)

    service.raw_repo.get_by_id.return_value = before
    service.raw_repo.update.return_value = after

    with patch("app.modules.catalog.service.refresh_sale_profits_for_item") as mock_refresh, \
         patch("app.modules.catalog.service.emit") as mock_emit:
        
        updated = await service.update_raw_material(1, schema)

        assert updated.stock_qty == 200.0
        service.raw_repo.update.assert_called_once()
        mock_refresh.assert_called_once_with("raw", 1, 12.0, 18.0)
        mock_emit.assert_called_once()
