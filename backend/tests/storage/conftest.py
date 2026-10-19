"""
Fixtures for the PostgreSQL storage integration tests.

The schema is built once per test session on the test database
(``ADRIANO_TEST_DATABASE_URL``) by running the real Alembic migrations
(``downgrade base`` then ``upgrade head``, which also exercises the
downgrade path). Every test starts from truncated tables.
"""

import datetime
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text

from alembic import command
from app.config import Settings
from app.database import _make_engine_url
from app.domain.hashing import content_digest
from app.domain.issues import Issue
from app.domain.values import Links, RecordKind, TitleSource, record_key
from app.storage.port import (
    CatalogStore,
    RecordWrite,
    RegistrationConfig,
)
from app.storage.postgres.store import PostgresStoreProvider

BACKEND_DIR = Path(__file__).resolve().parents[2]
TABLES = "intake_run, decision_event, record, revision, source_registration"
SOURCES = ("central", "other")


def database_url_for_tests() -> str:
    """
    Read the plain test DSN from the settings.

    :returns: ``ADRIANO_TEST_DATABASE_URL``.
    """
    return str(Settings().test_database_url)


def make_engine() -> Engine:
    """
    Create a fresh engine for the test database.

    :returns: The engine.
    """
    return create_engine(_make_engine_url(database_url_for_tests()))


@pytest.fixture(scope="session")
def migrated_engine() -> Iterator[Engine]:
    """
    Migrate the test database from scratch once per session.

    :returns: An engine bound to the migrated test database.
    """
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.attributes["database_url"] = database_url_for_tests()
    config.attributes["configure_logger"] = False
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    engine = make_engine()
    yield engine
    engine.dispose()


@pytest.fixture
def engine(migrated_engine: Engine) -> Engine:
    """
    Provide the engine with empty tables and seeded registrations.

    :param migrated_engine: Session-wide migrated engine.
    :returns: The same engine.
    """
    with migrated_engine.begin() as connection:
        connection.execute(text(f"TRUNCATE {TABLES}"))
    provider = PostgresStoreProvider(migrated_engine)
    with provider.unit_of_work() as store:
        store.sync_registrations(
            [
                RegistrationConfig(id=source, type="filesystem", config={})
                for source in SOURCES
            ]
        )
    return migrated_engine


@pytest.fixture
def provider(engine: Engine) -> PostgresStoreProvider:
    """
    Build a store provider over the clean test database.

    :param engine: Clean engine.
    :returns: The provider.
    """
    return PostgresStoreProvider(engine)


def document(adr_uuid: uuid.UUID | None, title: str, body: str) -> str:
    """
    Render a small ADR document.

    :param adr_uuid: UUID written to the frontmatter, if any.
    :param title: Title written to the frontmatter.
    :param body: Markdown body.
    :returns: The document text.
    """
    uuid_line = "" if adr_uuid is None else f"uuid: {adr_uuid}\n"
    return f"---\n{uuid_line}title: {title}\n---\n{body}\n"


def put_record(
    store: CatalogStore,
    *,
    source_id: str = "central",
    project: str = "platform",
    path: str = "doc/decisions/2024-01-01-a.md",
    ref: str = "main",
    adr_uuid: uuid.UUID | None = None,
    title: str = "A decision",
    body: str = "Some body text.",
    change_token: str | None = "1:1",
    issues: tuple[Issue, ...] = (),
) -> RecordWrite:
    """
    Store the revision of a test document and build its record write.

    :param store: Store in the current unit of work.
    :param source_id: Registration id.
    :param project: Project path.
    :param path: File path.
    :param ref: Ref.
    :param adr_uuid: Authored UUID (``None`` for a fallback key).
    :param title: Title.
    :param body: Body text.
    :param change_token: Change token.
    :param issues: Validation issues.
    :returns: The record write (not yet upserted).
    """
    content = document(adr_uuid, title, body)
    digest = str(content_digest(content.encode()))
    store.put_revision(digest, content)
    return RecordWrite(
        source_id=source_id,
        project=project,
        path=path,
        ref=ref,
        adr_uuid=adr_uuid,
        record_key=record_key(adr_uuid, source_id, project, path),
        digest=digest,
        change_token=change_token,
        metadata={"title": title},
        title=title,
        title_source=TitleSource.FRONTMATTER,
        decision_date=datetime.date(2024, 1, 1),
        decision_date_inferred=False,
        record_kind=RecordKind.DECISION,
        links=Links(),
        rendered_html=f"<p>{body}</p>",
        issues=issues,
    )
