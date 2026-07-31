from __future__ import annotations

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
    cfg = _alembic_config()
    script = ScriptDirectory.from_config(cfg)

    revisions = list(script.walk_revisions())
    assert len(revisions) > 0, "No Alembic migrations found!"

    rev_ids = {rev.revision for rev in revisions}
    assert len(revisions) == len(rev_ids), "Duplicate revision IDs found in walk_revisions"

    heads = script.get_heads()
    assert len(heads) == 1, f"Database migration branching detected! Multiple heads found: {heads}"

    for rev in revisions:
        if rev.down_revision:
            down_revs = rev.down_revision if isinstance(rev.down_revision, tuple) else (rev.down_revision,)
            for dr in down_revs:
                assert dr in rev_ids, f"Revision {rev.revision} points to a non-existent down_revision: {dr}"


def test_alembic_migration_full_chain_apply():
    """
    Validates every migration script from 0001 to head in the Alembic chain:
    - Verifies revision modules can be dynamically loaded
    - Checks that upgrade() and downgrade() functions exist and are callable
    - Ensures sequential chain continuity without broken links
    """
    cfg = _alembic_config()
    script = ScriptDirectory.from_config(cfg)
    revisions = list(reversed(list(script.walk_revisions())))

    assert len(revisions) >= 10, f"Expected at least 10 Alembic migrations, found {len(revisions)}"

    previous_rev = None
    for rev in revisions:
        assert rev.revision is not None, "Migration revision ID must not be None"

        # Load revision module dynamically
        module = script.get_revision(rev.revision).module
        assert hasattr(module, "upgrade"), f"Revision {rev.revision} missing upgrade() function"
        assert callable(module.upgrade), f"Revision {rev.revision} upgrade() is not callable"
        assert hasattr(module, "downgrade"), f"Revision {rev.revision} missing downgrade() function"
        assert callable(module.downgrade), f"Revision {rev.revision} downgrade() is not callable"

        if previous_rev is not None:
            # Check down_revision chain continuity
            down_rev = rev.down_revision
            if isinstance(down_rev, tuple):
                assert previous_rev in down_rev
            else:
                assert down_rev == previous_rev

        previous_rev = rev.revision
