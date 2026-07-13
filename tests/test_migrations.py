from __future__ import annotations

import pytest
from alembic.script import ScriptDirectory
from app.core.database import _alembic_config


def test_alembic_migration_lineage():
    """
    Test statically that the database migration lineage is coherent:
    - At least one migration exists
    - No duplicate revision IDs
    - No multiple heads (exactly one head)
    - All down_revisions point to existing migrations
    """
    # 1. Load Alembic Config
    cfg = _alembic_config()
    script = ScriptDirectory.from_config(cfg)
    
    # 2. Get all migration scripts
    revisions = list(script.walk_revisions())
    
    # 3. Check that revisions exist
    assert len(revisions) > 0, "No Alembic migrations found!"

    # 4. Check for duplicate revisions
    rev_ids = {rev.revision for rev in revisions}
    assert len(revisions) == len(rev_ids), f"Duplicate revision IDs found in walk_revisions"
    
    # 5. Check for branching (must have exactly one head)
    heads = script.get_heads()
    assert len(heads) == 1, f"Database migration branching detected! Multiple heads found: {heads}"
    
    # 6. Check that every down_revision is either None/base or points to an existing revision ID
    for rev in revisions:
        if rev.down_revision:
            down_revs = rev.down_revision if isinstance(rev.down_revision, tuple) else (rev.down_revision,)
            for dr in down_revs:
                assert dr in rev_ids, f"Revision {rev.revision} points to a non-existent down_revision: {dr}"
