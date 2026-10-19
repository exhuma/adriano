"""Integration tests for full-text search, filters and pagination."""

import uuid

import pytest

from app.domain.approval import Policy
from app.storage.port import MAX_PAGE_SIZE, RecordState, SearchFilters
from app.storage.postgres.store import PostgresStoreProvider
from tests.storage.conftest import put_record

U1 = uuid.UUID("0b0c2f4e-1234-4abc-8def-0123456789ab")
U2 = uuid.UUID("2b0c2f4e-1234-4abc-8def-0123456789ab")
POLICY = Policy(id="global", version=1)
ALL = SearchFilters()


@pytest.fixture
def seeded(provider: PostgresStoreProvider) -> PostgresStoreProvider:
    """
    Store three records with distinct titles, bodies and locations.

    :param provider: Clean provider.
    :returns: The provider.
    """
    with provider.unit_of_work() as store:
        store.upsert_published(
            put_record(
                store,
                adr_uuid=U1,
                path="doc/decisions/2024-01-01-use-postgres.md",
                title="Use PostgreSQL",
                body="We store records in a relational database.",
            )
        )
        store.upsert_published(
            put_record(
                store,
                source_id="other",
                project="payments",
                adr_uuid=U2,
                path="doc/decisions/2024-02-01-queue.md",
                title="Adopt a message queue",
                body="Payments are processed asynchronously via kafka_topic.",
            )
        )
        store.upsert_candidate(
            put_record(
                store,
                adr_uuid=U1,
                ref="feature",
                title="Use PostgreSQL",
                body="Draft wording about deciding things.",
            )
        )
    return provider


def titles(provider: PostgresStoreProvider, query: str | None) -> list[str]:
    """
    Search and return the hit titles with their kinds.

    :param provider: Provider.
    :param query: Text query.
    :returns: ``"<title>/<kind>"`` per hit.
    """
    with provider.unit_of_work() as store:
        page = store.search(query, ALL, 1, MAX_PAGE_SIZE, policy=POLICY)
    return [f"{item.title}/{item.kind}" for item in page.items]


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        (
            "postgresql",
            ["Use PostgreSQL/candidate", "Use PostgreSQL/published"],
        ),
        ("relational", ["Use PostgreSQL/published"]),
        ("kafka_topic", ["Adopt a message queue/published"]),
        (str(U2), ["Adopt a message queue/published"]),
        ("payments", ["Adopt a message queue/published"]),
        ("2024-02-01-queue", ["Adopt a message queue/published"]),
        ("decide", ["Use PostgreSQL/candidate"]),
        ("nothing-like-this", []),
        ("!!!", []),
    ],
)
def test_full_text_search(
    seeded: PostgresStoreProvider, query: str, expected: list[str]
) -> None:
    """Ensure titles, bodies, identifiers, UUIDs and paths are found."""
    assert sorted(titles(seeded, query)) == sorted(expected)


def test_blank_query_lists_everything_by_title(
    seeded: PostgresStoreProvider,
) -> None:
    """Ensure a blank query returns all rows ordered by title."""
    result = titles(seeded, "  ")
    assert result[0] == "Adopt a message queue/published"
    assert len(result) == 3
    assert titles(seeded, None) == result


def test_title_match_ranks_first(provider: PostgresStoreProvider) -> None:
    """Ensure a title hit outranks a body-only hit."""
    with provider.unit_of_work() as store:
        store.upsert_published(
            put_record(store, path="a.md", title="Other", body="caching")
        )
        store.upsert_published(
            put_record(store, path="b.md", title="Caching", body="other")
        )
    assert titles(provider, "caching") == [
        "Caching/published",
        "Other/published",
    ]


@pytest.mark.parametrize(
    ("filters", "count"),
    [
        (SearchFilters(source_id="central"), 2),
        (SearchFilters(source_id="other"), 1),
        (SearchFilters(project="payments"), 1),
        (SearchFilters(kind=RecordState.CANDIDATE), 1),
        (SearchFilters(kind=RecordState.PUBLISHED), 2),
        (
            SearchFilters(
                source_id="central",
                project="platform",
                kind=RecordState.PUBLISHED,
            ),
            1,
        ),
        (SearchFilters(source_id="missing"), 0),
    ],
)
def test_filters(
    seeded: PostgresStoreProvider, filters: SearchFilters, count: int
) -> None:
    """Ensure source, project and kind filters combine with AND."""
    with seeded.unit_of_work() as store:
        page = store.search(None, filters, 1, 10, policy=POLICY)
    assert page.total == count
    assert len(page.items) == count


def test_pagination(provider: PostgresStoreProvider) -> None:
    """Ensure pages are disjoint, ordered and report the total."""
    with provider.unit_of_work() as store:
        for index in range(7):
            store.upsert_published(
                put_record(store, path=f"{index}.md", title=f"T{index}")
            )
    seen: list[str] = []
    with provider.unit_of_work() as store:
        for number in (1, 2, 3, 4):
            page = store.search(None, ALL, number, 3, policy=POLICY)
            assert page.total == 7
            assert page.page == number and page.page_size == 3
            seen += [item.title for item in page.items]
    assert seen == [f"T{index}" for index in range(7)]


@pytest.mark.parametrize(
    ("page", "page_size"),
    [(0, 10), (-1, 10), (1, 0), (1, MAX_PAGE_SIZE + 1)],
)
def test_pagination_bounds(
    provider: PostgresStoreProvider, page: int, page_size: int
) -> None:
    """Ensure out-of-range page arguments are refused."""
    with provider.unit_of_work() as store, pytest.raises(ValueError):
        store.search(None, ALL, page, page_size, policy=POLICY)


def test_search_item_fields(seeded: PostgresStoreProvider) -> None:
    """Ensure items carry identity, digest and the approval state."""
    with seeded.unit_of_work() as store:
        page = store.search("queue", ALL, 1, MAX_PAGE_SIZE, policy=POLICY)
    (item,) = page.items
    assert item.adr_uuid == U2
    assert item.record_key == str(U2)
    assert item.digest.startswith("sha256-v1:")
    assert item.approval_state == "pending"
