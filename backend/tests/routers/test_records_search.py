"""Tests for ``GET /api/v1/records`` (search, filters, pagination)."""

import uuid

from fastapi.testclient import TestClient

from app.storage.port import RecordState
from app.storage.postgres.store import PostgresStoreProvider
from tests.routers.conftest import adr, seed

POSTGRES_UUID = uuid.UUID("0b0c2f4e-1a2b-4c3d-8e9f-001122334455")
GITLAB_UUID = uuid.UUID("1b0c2f4e-1a2b-4c3d-8e9f-001122334455")


def test_search_by_title_body_and_uuid(
    client: TestClient, provider: PostgresStoreProvider
) -> None:
    """Ensure free text matches the title, the body and the UUID."""
    with provider.lock_registration("central") as store:
        seed(
            store,
            content=adr(
                POSTGRES_UUID,
                title="Use PostgreSQL",
                body="We chose a relational unicornparty database.",
            ),
        )

    by_title = client.get("/api/v1/records", params={"q": "PostgreSQL"})
    by_body = client.get("/api/v1/records", params={"q": "unicornparty"})
    by_uuid = client.get("/api/v1/records", params={"q": str(POSTGRES_UUID)})
    no_match = client.get("/api/v1/records", params={"q": "no-such-term"})

    for response in (by_title, by_body, by_uuid):
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        item = body["items"][0]
        assert item["title"] == "Use PostgreSQL"
        assert item["source_id"] == "central"
        assert item["project"] == "platform"
        assert item["kind"] == "published"
        assert item["approval_state"] == "pending"
        assert item["issue_counts"] == {"error": 0, "warning": 0}
    assert no_match.json()["total"] == 0


def test_filters_by_source_project_and_state(
    client: TestClient, provider: PostgresStoreProvider
) -> None:
    """Ensure source/project/state filters each narrow the results."""
    with provider.lock_registration("central") as store:
        seed(
            store,
            source_id="central",
            project="platform",
            content=adr(POSTGRES_UUID, title="Platform decision"),
        )
    with provider.lock_registration("other") as store:
        seed(
            store,
            source_id="other",
            project="payments",
            path="doc/decisions/2024-01-01-b.md",
            content=adr(GITLAB_UUID, title="Payments decision"),
        )
    with provider.lock_registration("central") as store:
        seed(
            store,
            source_id="central",
            project="platform",
            path="doc/decisions/2024-01-02-c.md",
            ref="feature",
            kind=RecordState.CANDIDATE,
            content=adr(
                uuid.uuid4(), title="Candidate decision", body="Candidate."
            ),
        )

    by_source = client.get("/api/v1/records", params={"source": "other"})
    by_project = client.get("/api/v1/records", params={"project": "payments"})
    by_state = client.get("/api/v1/records", params={"state": "candidate"})
    unfiltered = client.get("/api/v1/records")

    assert [i["title"] for i in by_source.json()["items"]] == [
        "Payments decision"
    ]
    assert [i["title"] for i in by_project.json()["items"]] == [
        "Payments decision"
    ]
    assert [i["title"] for i in by_state.json()["items"]] == [
        "Candidate decision"
    ]
    assert unfiltered.json()["total"] == 3


def test_pagination_is_bounded(
    client: TestClient, provider: PostgresStoreProvider
) -> None:
    """Ensure pagination returns distinct pages and rejects bad bounds."""
    with provider.lock_registration("central") as store:
        for index in range(3):
            seed(
                store,
                path=f"doc/decisions/2024-01-0{index + 1}-x.md",
                content=adr(
                    uuid.uuid4(), title=f"Decision {index}", body="Body."
                ),
            )

    page_1 = client.get("/api/v1/records", params={"page": 1, "page_size": 1})
    page_2 = client.get("/api/v1/records", params={"page": 2, "page_size": 1})
    too_big = client.get("/api/v1/records", params={"page_size": 51})
    zero_page = client.get("/api/v1/records", params={"page": 0})

    assert page_1.status_code == 200
    assert page_1.json()["total"] == 3
    assert len(page_1.json()["items"]) == 1
    assert page_1.json()["items"][0]["id"] != page_2.json()["items"][0]["id"]
    assert too_big.status_code == 422
    assert zero_page.status_code == 422


def test_invalid_state_filter_is_422(client: TestClient) -> None:
    """Ensure an unknown ``state`` value is rejected, not silently ignored."""
    response = client.get("/api/v1/records", params={"state": "bogus"})

    assert response.status_code == 422


def _titles(client: TestClient, **params: str) -> list[str]:
    """
    Search through the API and return the hit titles in order.

    :param client: Test client.
    :param params: Query parameters.
    :returns: The titles.
    """
    response = client.get("/api/v1/records", params=params)
    assert response.status_code == 200
    return [item["title"] for item in response.json()["items"]]


def _seed_in_turn(
    provider: PostgresStoreProvider, documents: list[tuple[str, bytes]]
) -> None:
    """
    Ingest documents one transaction each, oldest first.

    :param provider: Provider.
    :param documents: ``(path, content)`` pairs.
    """
    for path, content in documents:
        with provider.lock_registration("central") as store:
            seed(store, path=path, content=content)


def test_sort_defaults_and_values(
    client: TestClient, provider: PostgresStoreProvider
) -> None:
    """Ensure each sort value orders hits and the defaults apply."""
    _seed_in_turn(
        provider,
        [
            ("doc/decisions/a.md", adr(uuid.uuid4(), title="Alpha", body="x")),
            (
                "doc/decisions/z.md",
                adr(uuid.uuid4(), title="Zulu caching", body="y"),
            ),
            ("doc/decisions/m.md", adr(uuid.uuid4(), title="Mike", body="x")),
        ],
    )
    by_title = ["Alpha", "Mike", "Zulu caching"]
    by_recent = ["Mike", "Zulu caching", "Alpha"]

    assert _titles(client) == by_title
    assert _titles(client, sort="title") == by_title
    assert _titles(client, sort="relevance") == by_title
    assert _titles(client, q=" ", sort="relevance") == by_title
    assert _titles(client, sort="recent") == by_recent
    assert _titles(client, q="x") == ["Alpha", "Mike"]
    assert _titles(client, q="caching OR x") == [
        "Zulu caching",
        "Alpha",
        "Mike",
    ]
    assert _titles(client, q="caching OR x", sort="title") == by_title
    assert _titles(client, q="caching OR x", sort="recent") == by_recent


def test_sort_combines_with_needs_approval_and_record_type(
    client: TestClient, provider: PostgresStoreProvider
) -> None:
    """Ensure ``recent`` composes with ``needs_approval``/``record_type``."""
    target = uuid.uuid4()
    _seed_in_turn(
        provider,
        [
            ("doc/decisions/t.md", adr(target, title="Target")),
            (
                "doc/decisions/errata/e.md",
                (
                    f"---\nuuid: {uuid.uuid4()}\ntitle: Erratum\n"
                    f"erratum-for: {target}\ntype: editorial\n---\n"
                    "## Corrected text\n\nFixed.\n"
                ).encode(),
            ),
            ("doc/decisions/n.md", adr(uuid.uuid4(), title="Newest")),
        ],
    )

    def recent(**params: str) -> list[str]:
        return _titles(client, sort="recent", needs_approval="true", **params)

    assert recent() == ["Newest", "Target"]
    assert recent(record_type="erratum") == ["Erratum"]
    assert recent(record_type="all") == ["Newest", "Erratum", "Target"]


def test_invalid_sort_is_422(client: TestClient) -> None:
    """Ensure an unknown ``sort`` value is rejected, not ignored."""
    response = client.get("/api/v1/records", params={"sort": "newest"})

    assert response.status_code == 422
