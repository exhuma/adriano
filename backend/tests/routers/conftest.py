"""
Fixtures for the read-API router tests (real HTTP against real Postgres).

Each test gets a truncated, re-migrated database and a ``client`` whose
app lifespan has synced two ``filesystem`` registrations
(``central``, ``other``) plus a configured approval policy from a
generated ``catalog.yaml``. Tests seed records directly through the
storage port (:func:`app.services.ingest.ingest_document`), exactly
like the phase 04 ingest/polling tests, then exercise the HTTP routes.

The ``client`` holds a dev session for an ``admin`` (read + operate) by
default; tests sign in again (:func:`tests.auth_helpers.sign_in`) or
drop the cookie to check authentication and permissions.
"""

import datetime
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from app.config import Settings, get_settings
from app.main import create_app
from app.services.ingest import (
    IncomingDocument,
    ingest_document,
    prepare_document,
)
from app.storage.port import CatalogStore, RecordState
from app.storage.postgres.store import PostgresStoreProvider
from tests.auth_helpers import https_client, sign_in
from tests.storage.conftest import (  # noqa: F401
    migrated_engine,
    truncate_all,
)

#: Two filesystem registrations and a configured, enforced policy with
#: no eligible reviewers (decisions are out of scope for phase 05).
CATALOG_YAML = """
sources:
  - id: central
    type: filesystem
    root: ./does-not-need-to-exist
    published_ref: local
  - id: other
    type: filesystem
    root: ./does-not-need-to-exist
    published_ref: local
approval_policy:
  id: global
  version: 1
  required: true
  reviewers:
    roles: [adr-reviewer]
rbac:
  roles:
    admin: [read, operate]
    adr-reader: [read]
    poller: [operate]
"""


@pytest.fixture
def clean_engine(migrated_engine: Engine) -> Engine:  # noqa: F811
    """
    Provide the migrated engine with every table truncated.

    :param migrated_engine: Session-wide migrated engine.
    :returns: The same engine, with empty tables.
    """
    with migrated_engine.begin() as connection:
        truncate_all(connection)
    return migrated_engine


@pytest.fixture
def catalog_file(tmp_path: Path) -> Path:
    """
    Write the two-registration ``catalog.yaml`` used by these tests.

    :param tmp_path: Pytest temporary directory.
    :returns: The file path.
    """
    path = tmp_path / "catalog.yaml"
    path.write_text(CATALOG_YAML, encoding="utf-8")
    return path


@pytest.fixture
def router_settings(test_settings: Settings, catalog_file: Path) -> Settings:
    """
    Build the settings of the router test client.

    :param test_settings: Settings pointed at the test database.
    :param catalog_file: The generated ``catalog.yaml``.
    :returns: Settings reading that file.
    """
    return test_settings.model_copy(update={"config_file": str(catalog_file)})


@pytest.fixture
def client(
    router_settings: Settings, clean_engine: Engine
) -> Iterator[TestClient]:
    """
    Build a test client whose lifespan synced the two registrations.

    :param router_settings: Settings reading the generated
        ``catalog.yaml``.
    :param clean_engine: Truncated, migrated engine (ensures the sync
        in this fixture's lifespan runs against empty tables).
    :returns: The client, authenticated as an ``admin``.
    """
    app = create_app(router_settings)
    app.dependency_overrides[get_settings] = lambda: router_settings
    with https_client(app) as test_client:
        sign_in(test_client, roles=["admin"])
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def provider(clean_engine: Engine) -> PostgresStoreProvider:
    """
    Build a store provider bound to the same truncated database.

    :param clean_engine: Truncated, migrated engine.
    :returns: The provider.
    """
    return PostgresStoreProvider(clean_engine)


def seed(
    store: CatalogStore,
    *,
    source_id: str = "central",
    project: str = "platform",
    path: str = "doc/decisions/2024-01-01-a.md",
    ref: str = "local",
    content: bytes,
    kind: RecordState = RecordState.PUBLISHED,
) -> uuid.UUID:
    """
    Ingest one document straight through the shared ingest path.

    :param store: Store in the caller's (locked) unit of work.
    :param source_id: Owning registration id.
    :param project: Owning project path.
    :param path: File path inside the project.
    :param ref: Branch/ref.
    :param content: Raw file bytes.
    :param kind: Published or candidate.
    :returns: The stored record id.
    """
    document = IncomingDocument(
        source_id=source_id,
        project=project,
        path=path,
        ref=ref,
        content=content,
        change_token="1:1",
    )
    prepared = prepare_document(document)
    result = ingest_document(store, prepared, kind)
    return result.record_id


def adr(
    adr_uuid: uuid.UUID | str | None,
    *,
    title: str = "A decision",
    body: str = "Body text.",
    extra: str = "",
) -> bytes:
    """
    Render a small ADR document.

    :param adr_uuid: UUID written to the frontmatter, or ``None`` to
        omit it (an invalid record).
    :param title: Title.
    :param body: Markdown body.
    :param extra: Extra raw frontmatter lines (e.g. ``updates: [...]``).
    :returns: The document bytes.
    """
    uuid_line = "" if adr_uuid is None else f"uuid: {adr_uuid}\n"
    return (
        f"---\n{uuid_line}title: {title}\ndecision-date: 2024-01-01\n"
        f"{extra}---\n{body}\n"
    ).encode()


def mark_poll_ok(
    provider: PostgresStoreProvider,
    source_id: str,
    *,
    when: datetime.datetime | None = None,
) -> None:
    """
    Record a successful poll for a registration.

    :param provider: Storage provider.
    :param source_id: Registration id.
    :param when: Attempt time; defaults to now.
    """
    from app.storage.port import PollStatus

    with provider.unit_of_work() as store:
        store.update_poll_status(
            source_id,
            PollStatus.OK,
            when or datetime.datetime.now(datetime.UTC),
        )
