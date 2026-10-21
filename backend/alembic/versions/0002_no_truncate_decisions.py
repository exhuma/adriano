"""
Refuse TRUNCATE on ``decision_event``.

Hand-written. Migration 0001 made ``decision_event`` append-only for
UPDATE and DELETE only; ``TRUNCATE`` bypasses row and statement
UPDATE/DELETE triggers, so it could still wipe the decision history.
This adds a ``BEFORE TRUNCATE`` statement trigger that reuses the
existing ``decision_event_append_only()`` function (it raises with
``TG_OP``, so the message reads "TRUNCATE is not allowed"). A
``TRUNCATE`` of another table that cascades to ``decision_event`` is
refused as well.

The table owner (and any superuser) can still disable or drop the
trigger; see docs/operator/backup-restore.rst for running the app
with a non-owner role.

Revision ID: 0002_no_truncate_decisions
Revises: 0001_initial
Create Date: 2026-10-19
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002_no_truncate_decisions"
down_revision: str | Sequence[str] | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TRIGGER = "decision_event_no_truncate"


def upgrade() -> None:
    """Add the BEFORE TRUNCATE guard trigger."""
    op.execute(
        f"CREATE TRIGGER {_TRIGGER} "
        "BEFORE TRUNCATE ON decision_event "
        "FOR EACH STATEMENT EXECUTE FUNCTION decision_event_append_only()"
    )
    op.execute(
        f"COMMENT ON TRIGGER {_TRIGGER} ON decision_event IS "
        "'Refuses TRUNCATE: decision history is append-only.'"
    )


def downgrade() -> None:
    """Drop the BEFORE TRUNCATE guard trigger (function stays: 0001)."""
    op.execute(f"DROP TRIGGER {_TRIGGER} ON decision_event")
