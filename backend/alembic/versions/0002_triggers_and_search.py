"""
Triggers: weighted full-text search vector and append-only decisions.

- the trigger-maintained weighted ``record.search`` tsvector (title A;
  UUID/project/path B, the path also split at ``/`` and ``.`` so file
  name parts match; body C with the ``simple`` configuration so code
  identifiers and UUIDs stay searchable; body D with ``english`` for
  stemmed matches). A trigger is used instead of a generated column
  because the body lives in ``revision``;
- the append-only statement triggers on ``decision_event``: UPDATE,
  DELETE and TRUNCATE (also one cascading from another table) are
  refused. The table owner (and any superuser) can still disable or
  drop the triggers; see docs/operator/backup-restore.rst for running
  the app with a non-owner role.

Revision ID: 0002_triggers_and_search
Revises: 0001_initial
Create Date: 2026-11-27
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002_triggers_and_search"
down_revision: str | Sequence[str] | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SEARCH_FUNCTION = """
CREATE FUNCTION record_search_vector() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    body text;
BEGIN
    SELECT r.content INTO body FROM revision AS r
    WHERE r.digest = NEW.digest;
    NEW.search :=
        setweight(to_tsvector('simple', coalesce(NEW.title, '')), 'A')
        || setweight(to_tsvector('simple', concat_ws(' ',
            NEW.adr_uuid::text, NEW.project, NEW.path,
            translate(NEW.path, '/.', '  '))), 'B')
        || setweight(to_tsvector('simple', coalesce(body, '')), 'C')
        || setweight(to_tsvector('english', coalesce(body, '')), 'D');
    RETURN NEW;
END;
$$
"""

_SEARCH_TRIGGER = """
CREATE TRIGGER record_search_vector
BEFORE INSERT OR UPDATE OF title, adr_uuid, project, path, digest
ON record
FOR EACH ROW EXECUTE FUNCTION record_search_vector()
"""

_APPEND_ONLY_FUNCTION = """
CREATE FUNCTION decision_event_append_only() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'decision_event is append-only: % is not allowed',
        TG_OP
        USING ERRCODE = 'restrict_violation';
END;
$$
"""

# Statement level so that even an UPDATE/DELETE matching no rows fails.
# TRUNCATE bypasses UPDATE/DELETE triggers, hence its own trigger.
_APPEND_ONLY_TRIGGERS = (
    "CREATE TRIGGER decision_event_append_only "
    "BEFORE UPDATE OR DELETE ON decision_event "
    "FOR EACH STATEMENT EXECUTE FUNCTION decision_event_append_only()",
    "CREATE TRIGGER decision_event_no_truncate "
    "BEFORE TRUNCATE ON decision_event "
    "FOR EACH STATEMENT EXECUTE FUNCTION decision_event_append_only()",
)


def upgrade() -> None:
    """Create the search and append-only triggers."""
    op.execute(_SEARCH_FUNCTION)
    op.execute(_SEARCH_TRIGGER)
    op.execute(_APPEND_ONLY_FUNCTION)
    for trigger in _APPEND_ONLY_TRIGGERS:
        op.execute(trigger)
    op.execute(
        "COMMENT ON TRIGGER decision_event_no_truncate ON decision_event "
        "IS 'Refuses TRUNCATE: decision history is append-only.'"
    )


def downgrade() -> None:
    """Drop the triggers and their functions."""
    op.execute("DROP TRIGGER decision_event_no_truncate ON decision_event")
    op.execute("DROP TRIGGER decision_event_append_only ON decision_event")
    op.execute("DROP TRIGGER record_search_vector ON record")
    op.execute("DROP FUNCTION decision_event_append_only()")
    op.execute("DROP FUNCTION record_search_vector()")
