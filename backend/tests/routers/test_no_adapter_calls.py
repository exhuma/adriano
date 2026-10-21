"""
Ensure normal browse/search requests never construct a source adapter.

``docs/developer/decisions/0004-reads-from-local-index.rst``
requires that read routes use only the storage port. Every source
adapter is built inside a registration's
``SourceBinding.open_adapter`` context, which constructs a
:class:`~app.sources.filesystem.FilesystemAdapter` or a
:class:`~app.sources.gitlab.GitLabAdapter` (plus its HTTP client).
Patching those constructors to raise and record the call catches any
read path that opens an adapter -- including one that goes through
the bindings built at startup, which patching the registry factory
after startup could not.
"""

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.domain.approval import DecisionAction
from app.domain.values import Identity
from app.sources import filesystem, gitlab, gitlab_api
from app.storage.port import NewDecision, RecordState
from app.storage.postgres.store import PostgresStoreProvider
from tests.routers.conftest import adr, seed

U1 = uuid.UUID("0b0c2f4e-1234-4abc-8def-0123456789ab")
U2 = uuid.UUID("1b0c2f4e-1234-4abc-8def-0123456789ab")
PATH = "doc/decisions/2024-01-01-a.md"


@pytest.fixture
def adapter_calls(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[str]]:
    """
    Make every adapter constructor raise and record the attempt.

    The list is asserted empty at the end, so a read path that catches
    the exception and still answers 200 is caught too.

    :param monkeypatch: Pytest monkeypatch.
    :returns: Names of the constructors that were called.
    """
    calls: list[str] = []

    def _refusing(name: str) -> object:
        def _refuse(*_args: object, **_kwargs: object) -> None:
            calls.append(name)
            raise AssertionError(f"a read route constructed {name}")

        return _refuse

    targets = [
        (filesystem.FilesystemAdapter, "__init__"),
        (gitlab.GitLabAdapter, "__init__"),
        (gitlab_api.GitLabApi, "__init__"),
    ]
    for owner, attribute in targets:
        monkeypatch.setattr(
            owner, attribute, _refusing(f"{owner.__name__}.{attribute}")
        )
    monkeypatch.setattr(gitlab, "open_client", _refusing("open_client"))
    yield calls


def _seed_catalog(provider: PostgresStoreProvider) -> uuid.UUID:
    """
    Seed two revisions, a candidate and an accepted decision.

    :param provider: Store provider of the test database.
    :returns: The published record id (with a previous revision).
    """
    with provider.lock_registration("central") as store:
        seed(store, content=adr(U1, title="First"))
        record_id = seed(store, content=adr(U1, title="Readable"))
        seed(
            store,
            ref="feature",
            content=adr(U2, title="Candidate"),
            path="doc/decisions/2024-01-02-b.md",
            kind=RecordState.CANDIDATE,
        )
        stored = store.get_record(record_id)
        assert stored is not None
        store.append_decision(
            NewDecision(
                identity=Identity("central", "platform", str(U1)),
                adr_uuid=U1,
                digest=stored.digest,
                action=DecisionAction.ACCEPTED,
                actor_issuer="https://idp.example.com",
                actor_subject="subject-123",
                actor_display="Rev Iewer",
                actor_email="rev@example.com",
                comment=None,
                policy_id="global",
                policy_version=1,
            )
        )
    return record_id


READ_QUERIES = [
    {},
    {"q": "Readable"},
    {"source": "central", "project": "platform"},
    {"state": "published"},
    {"state": "candidate"},
    {"needs_approval": "true"},
    {"needs_approval": "true", "state": "candidate", "q": "Candidate"},
    {"page": "2", "page_size": "1"},
]


def test_every_read_route_never_constructs_an_adapter(
    client: TestClient,
    provider: PostgresStoreProvider,
    adapter_calls: list[str],
) -> None:
    """Ensure all read routes answer without constructing any adapter."""
    record_id = _seed_catalog(provider)

    searches = [
        client.get("/api/v1/records", params=params) for params in READ_QUERIES
    ]
    detail = client.get(f"/api/v1/records/{record_id}")
    diff = client.get(f"/api/v1/records/{record_id}/diff")
    missing = client.get(f"/api/v1/records/{uuid.uuid4()}")
    others = [
        client.get(path)
        for path in ("/api/v1/sources", "/api/v1/facets", "/api/v1/me")
    ]

    assert [r.status_code for r in searches] == [200] * len(READ_QUERIES)
    assert searches[0].json()["total"] == 2
    assert searches[5].json()["total"] == 1  # the candidate only
    assert detail.status_code == 200
    assert detail.json()["metadata"]["title"] == "Readable"
    assert diff.status_code == 200
    assert missing.status_code == 404
    assert [r.status_code for r in others] == [200, 200, 200]
    assert adapter_calls == []
