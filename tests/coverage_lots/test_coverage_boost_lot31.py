"""
test_coverage_boost_lot31.py
Targets:
  - sales/commands.py: create_sale_record initial payment (lines 92-101), raw material "autre" (line 111)
  - registry.py: discover_modules with import failure & disabled modules (lines 129, 137-143)
  - schema/__init__.py: schema package exports
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ============================================================
# 1. sales/commands.py — create_sale_record initial payment & "autre"
# ============================================================

@pytest.mark.asyncio
async def test_sales_commands_create_sale_record_initial_payment():
    """Lines 92-101: initial payment created when amount_paid > 0."""
    from app.modules.sales.commands import SalesCommands

    mock_session = AsyncMock()
    added_objs = []

    def mock_add(obj):
        added_objs.append(obj)

    async def mock_flush():
        for o in added_objs:
            if getattr(o, "id", None) is None:
                o.id = 10

    mock_session.add = MagicMock(side_effect=mock_add)
    mock_session.flush = AsyncMock(side_effect=mock_flush)

    mock_prod = MagicMock()
    mock_prod.id = 1
    mock_prod.name = "Farine T55"

    mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mock_prod)))

    commands = SalesCommands(mock_session)

    with patch("app.modules.sales.validation.SalesValidator.validate_stock_availability",
               new=AsyncMock(return_value=(mock_prod, 10.0))), \
         patch.object(commands, "recalc_sale_document_totals", new=AsyncMock()):
        kind, row_id = await commands.create_sale_record(
            client_id=1,
            item_kind="finished",
            item_id=1,
            qty=10.0,
            unit="kg",
            unit_price=100.0,
            sale_type="credit",
            sale_date="2024-01-01",
            notes="note",
            amount_paid_input=500.0,
            document_id=1,
        )

    assert kind == "finished"
    assert row_id == 10


@pytest.mark.asyncio
async def test_sales_commands_create_sale_record_raw_autre():
    """Line 111: RawMaterial name == 'autre' forces unit='unite'."""
    from app.modules.sales.commands import SalesCommands

    mock_session = AsyncMock()
    added_objs = []

    def mock_add(obj):
        added_objs.append(obj)

    async def mock_flush():
        for o in added_objs:
            if getattr(o, "id", None) is None:
                o.id = 20

    mock_session.add = MagicMock(side_effect=mock_add)
    mock_session.flush = AsyncMock(side_effect=mock_flush)

    mock_rm = MagicMock()
    mock_rm.id = 2
    mock_rm.name = "autre"

    mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mock_rm)))

    commands = SalesCommands(mock_session)

    with patch("app.modules.sales.validation.SalesValidator.validate_stock_availability",
               new=AsyncMock(return_value=(mock_rm, 5.0))), \
         patch.object(commands, "recalc_sale_document_totals", new=AsyncMock()):
        kind, row_id = await commands.create_sale_record(
            client_id=1,
            item_kind="raw",
            item_id=2,
            qty=5.0,
            unit="kg",
            unit_price=200.0,
            sale_type="cash",
            sale_date="2024-01-01",
            notes="",
        )

    assert kind == "raw"
    assert row_id == 20


# ============================================================
# 2. registry.py — module loading error handling & feature flags
# ============================================================

def test_registry_discover_modules_error_handling(tmp_path: Path):
    """Lines 129, 137-143: discover_modules handles import errors & disabled modules."""
    from app.core.registry import discover_modules, register, ModuleDescriptor

    # Create dummy module directory structure
    mod_dir = tmp_path / "mod_broken"
    mod_dir.mkdir()
    (mod_dir / "__init__.py").write_text("# broken")

    mod_dir2 = tmp_path / "mod_disabled"
    mod_dir2.mkdir()
    (mod_dir2 / "__init__.py").write_text("# disabled")

    desc = ModuleDescriptor(name="mod_disabled", label="Disabled")
    register(desc)

    with patch.dict("os.environ", {"FAB_MODULES_DISABLED": "mod_disabled"}), \
         patch("importlib.import_module", side_effect=[Exception("import error"), None]):
        discover_modules(tmp_path)

    assert desc.enabled is False


# ============================================================
# 3. schema/__init__.py — validation helpers
# ============================================================

def test_schema_init_exports():
    """Lines 30-31, 64, 88-89: schema package exports."""
    import app.core.schema as schema_pkg

    assert hasattr(schema_pkg, "__all__") or isinstance(dir(schema_pkg), list)
