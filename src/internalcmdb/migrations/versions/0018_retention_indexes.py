"""Indexes required by the data-retention job on discovery tables.

Revision ID: 0018
Revises: 0017
Created: 2026-07-03

Changes:
  - Index on snapshot_diff.previous_snapshot_id — without it every DELETE on
    collector_snapshot triggers a sequential scan of snapshot_diff for the
    FK integrity check (snapshot_diff_previous_snapshot_id_fkey).
  - Index on collector_snapshot.collected_at — used by the retention job's
    range delete (collected_at < NOW() - interval).

Both use IF NOT EXISTS so environments where the indexes were pre-created
CONCURRENTLY (to avoid write locks on large tables) upgrade cleanly.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_snapshot_diff_previous_snapshot "
        "ON discovery.snapshot_diff (previous_snapshot_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_collector_snapshot_collected_at "
        "ON discovery.collector_snapshot (collected_at)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS discovery.ix_snapshot_diff_previous_snapshot")
    op.execute("DROP INDEX IF EXISTS discovery.ix_collector_snapshot_collected_at")
