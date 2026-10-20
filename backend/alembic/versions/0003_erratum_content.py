"""
Store erratum content and index the erratum-to-target link.

Hand-written. Adds:

- ``record.erratum`` (nullable JSONB): the rendered content of an
  erratum record, ``NULL`` for decisions. Only sanitized HTML and the
  small frontmatter fields are stored; the raw Markdown stays in the
  ``revision`` snapshot of the row's digest.
- ``ix_record_links_corrects``: a partial expression index on
  ``(links ->> 'corrects')`` for the reverse lookup "errata of one
  decision" (``app.storage.postgres.errata.list_errata_for``). It is
  partial on ``(links ->> 'corrects') IS NOT NULL`` because only
  errata carry the link: the index stays as small as the errata set,
  and every equality lookup on the expression implies the predicate,
  so the planner uses it without an extra clause in the query.

Rows of ``record_kind = 'erratum'`` stored before this revision have
no ``erratum`` content (and pre-phase-10 rows use the retired
``kind: erratum`` shape). Their ``change_token`` is cleared so the next
poll re-fetches and re-ingests them with the current parser. Pushed
candidates are only refreshed by the next push. The downgrade does not
restore the cleared tokens: losing them only costs one extra fetch.

Revision ID: 0003_erratum_content
Revises: 0002_no_truncate_decisions
Create Date: 2026-10-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "0003_erratum_content"
down_revision: str | Sequence[str] | None = "0002_no_truncate_decisions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_INDEX = "ix_record_links_corrects"

_COMMENT = (
    "Erratum content, NULL for decisions: JSON object {type "
    "(technical|editorial|null), section, reported_by, reported_date "
    "(YYYY-MM-DD), original_html, corrected_html, notes_html}; text "
    "values may be null, HTML is nh3-sanitized at ingest."
)


def upgrade() -> None:
    """Add ``record.erratum`` and the ``corrects`` link index."""
    op.add_column("record", sa.Column("erratum", JSONB, nullable=True))
    op.execute(f"COMMENT ON COLUMN record.erratum IS '{_COMMENT}'")
    op.execute(
        f"CREATE INDEX {_INDEX} ON record ((links ->> 'corrects')) "
        "WHERE (links ->> 'corrects') IS NOT NULL"
    )
    op.execute(
        f"COMMENT ON INDEX {_INDEX} IS "
        "'Reverse lookup of the errata that correct one decision UUID.'"
    )
    op.execute(
        "UPDATE record SET change_token = NULL "
        "WHERE record_kind = 'erratum' AND erratum IS NULL"
    )


def downgrade() -> None:
    """Drop the index and ``record.erratum`` (cleared tokens stay)."""
    op.execute(f"DROP INDEX {_INDEX}")
    op.drop_column("record", "erratum")
