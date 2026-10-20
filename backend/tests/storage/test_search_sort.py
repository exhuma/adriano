"""Integration tests for the search sort orders (``SearchSort``)."""

import dataclasses
import uuid

import pytest
from sqlalchemy import Engine, text

from app.domain.approval import DecisionAction, Policy
from app.domain.values import RecordKind
from app.storage.port import (
    MAX_PAGE_SIZE,
    NewDecision,
    RecordWrite,
    SearchFilters,
    SearchSort,
)
from app.storage.postgres.store import PostgresStoreProvider
from tests.storage.conftest import put_record

POLICY = Policy(id="global", version=1)
ALL = SearchFilters()
NEEDS_APPROVAL = SearchFilters(needs_approval=True)


def titles(
    provider: PostgresStoreProvider,
    query: str | None,
    sort: SearchSort,
    filters: SearchFilters = ALL,
) -> list[str]:
    """
    Search one full page and return the hit titles in order.

    :param provider: Provider.
    :param query: Text query.
    :param sort: Requested order.
    :param filters: Filters.
    :returns: The titles.
    """
    with provider.unit_of_work() as store:
        page = store.search(
            query, filters, 1, MAX_PAGE_SIZE, policy=POLICY, sort=sort
        )
    return [item.title for item in page.items]


def store_one(
    provider: PostgresStoreProvider,
    *,
    path: str,
    title: str,
    body: str = "Some body text.",
    adr_uuid: uuid.UUID | None = None,
) -> RecordWrite:
    """
    Store one published record in its own unit of work.

    Each unit of work is one transaction, so every call gets a later
    ``now()`` and therefore a later ``updated_at`` for new content.

    :param provider: Provider.
    :param path: File path.
    :param title: Title.
    :param body: Body text.
    :param adr_uuid: Authored UUID, if any.
    :returns: The stored write.
    """
    with provider.unit_of_work() as store:
        write = put_record(
            store, path=path, title=title, body=body, adr_uuid=adr_uuid
        )
        store.upsert_published(write)
    return write


@pytest.fixture
def timeline(provider: PostgresStoreProvider) -> PostgresStoreProvider:
    """
    Store Alpha, Bravo, Charlie in turn, then touch Alpha and edit Bravo.

    Alpha is re-stored unchanged (only ``last_seen_at`` moves) and
    Bravo's body changes (``updated_at`` moves), so the "recent" order
    is Bravo, Charlie, Alpha.

    :param provider: Clean provider.
    :returns: The provider.
    """
    store_one(provider, path="a.md", title="Alpha", body="First.")
    store_one(provider, path="b.md", title="Bravo", body="First.")
    store_one(provider, path="c.md", title="Charlie", body="First.")
    store_one(provider, path="a.md", title="Alpha", body="First.")
    store_one(provider, path="b.md", title="Bravo", body="Edited.")
    return provider


def test_recent_follows_content_changes_only(
    timeline: PostgresStoreProvider,
) -> None:
    """Ensure ``recent`` orders by content change, not by last poll."""
    assert titles(timeline, None, SearchSort.RECENT) == [
        "Bravo",
        "Charlie",
        "Alpha",
    ]


def test_title_and_relevance_without_query(
    timeline: PostgresStoreProvider,
) -> None:
    """Ensure ``title`` is A-Z and ``relevance`` without a query too."""
    expected = ["Alpha", "Bravo", "Charlie"]
    assert titles(timeline, None, SearchSort.TITLE) == expected
    assert titles(timeline, "  ", SearchSort.RELEVANCE) == expected


@pytest.fixture
def ranked(provider: PostgresStoreProvider) -> PostgresStoreProvider:
    """
    Store body hits Alpha and Mike around the title hit Zulu.

    Stored oldest to newest: Alpha, Zulu Caching, Mike.

    :param provider: Clean provider.
    :returns: The provider.
    """
    store_one(provider, path="a.md", title="Alpha", body="caching")
    store_one(provider, path="z.md", title="Zulu Caching", body="other")
    store_one(provider, path="m.md", title="Mike", body="caching")
    store_one(provider, path="n.md", title="Nothing", body="unrelated")
    return provider


@pytest.mark.parametrize(
    ("sort", "expected"),
    [
        (SearchSort.RELEVANCE, ["Zulu Caching", "Alpha", "Mike"]),
        (SearchSort.TITLE, ["Alpha", "Mike", "Zulu Caching"]),
        (SearchSort.RECENT, ["Mike", "Zulu Caching", "Alpha"]),
    ],
)
@pytest.mark.parametrize("filters", [ALL, NEEDS_APPROVAL])
def test_each_sort_with_a_query(
    ranked: PostgresStoreProvider,
    sort: SearchSort,
    expected: list[str],
    filters: SearchFilters,
) -> None:
    """Ensure each sort orders the text hits, with or without approval."""
    assert titles(ranked, "caching", sort, filters) == expected


def test_default_sort_is_relevance(ranked: PostgresStoreProvider) -> None:
    """Ensure the store defaults to relevance (title without a query)."""
    with ranked.unit_of_work() as store:
        hit = store.search("caching", ALL, 1, 10, policy=POLICY)
        browse = store.search(None, ALL, 1, 10, policy=POLICY)
    assert [item.title for item in hit.items] == [
        "Zulu Caching",
        "Alpha",
        "Mike",
    ]
    assert [item.title for item in browse.items] == [
        "Alpha",
        "Mike",
        "Nothing",
        "Zulu Caching",
    ]


@pytest.fixture
def same_instant(provider: PostgresStoreProvider) -> PostgresStoreProvider:
    """
    Store eight records in one transaction (one ``updated_at``).

    Two pairs share a title up to case, so only the id separates them.

    :param provider: Clean provider.
    :returns: The provider.
    """
    names = ["delta", "Bravo", "alpha", "Alpha", "echo", "Charlie", "bravo"]
    with provider.unit_of_work() as store:
        for index, name in enumerate([*names, "Foxtrot"]):
            store.upsert_published(
                put_record(store, path=f"{index}.md", title=name)
            )
    return provider


def page_ids(
    provider: PostgresStoreProvider,
    sort: SearchSort,
    filters: SearchFilters,
    page_size: int,
) -> list[uuid.UUID]:
    """
    Walk every page and collect the hit ids in order.

    :param provider: Provider.
    :param sort: Requested order.
    :param filters: Filters.
    :param page_size: Page size.
    :returns: The ids of all pages, concatenated.
    """
    result: list[uuid.UUID] = []
    with provider.unit_of_work() as store:
        number = 1
        while True:
            page = store.search(
                None, filters, number, page_size, policy=POLICY, sort=sort
            )
            result += [item.id for item in page.items]
            if number * page_size >= page.total:
                return result
            number += 1


@pytest.mark.parametrize("filters", [ALL, NEEDS_APPROVAL])
def test_recent_pages_are_stable_on_equal_timestamps(
    same_instant: PostgresStoreProvider,
    engine: Engine,
    filters: SearchFilters,
) -> None:
    """Ensure equal ``updated_at`` values page by title, then id."""
    with engine.connect() as connection:
        instants = connection.execute(
            text("SELECT count(DISTINCT updated_at) FROM record")
        ).scalar_one()
        expected = list(
            connection.execute(
                text("SELECT id FROM record ORDER BY lower(title), id")
            ).scalars()
        )
    assert instants == 1

    paged = page_ids(same_instant, SearchSort.RECENT, filters, 3)

    assert paged == expected
    assert paged == page_ids(same_instant, SearchSort.RECENT, filters, 50)
    assert paged == page_ids(same_instant, SearchSort.TITLE, filters, 3)


def accept(provider: PostgresStoreProvider, write: RecordWrite) -> None:
    """
    Accept the current digest of a stored record.

    :param provider: Provider.
    :param write: The stored write.
    """
    assert write.adr_uuid is not None
    with provider.unit_of_work() as store:
        store.append_decision(
            NewDecision(
                identity=write.identity,
                adr_uuid=write.adr_uuid,
                digest=write.digest,
                action=DecisionAction.ACCEPTED,
                actor_issuer="iss",
                actor_subject="sub",
                actor_display=None,
                actor_email=None,
                comment=None,
                policy_id="global",
                policy_version=1,
            )
        )


def test_recent_with_needs_approval_and_record_kind(
    provider: PostgresStoreProvider,
) -> None:
    """Ensure ``recent`` keeps its order under every other filter."""
    accepted = store_one(
        provider, path="a.md", title="Accepted", adr_uuid=uuid.uuid4()
    )
    store_one(provider, path="o.md", title="Older", body="One.")
    with provider.unit_of_work() as store:
        erratum = put_record(store, path="e.md", title="Erratum")
        store.upsert_published(
            dataclasses.replace(erratum, record_kind=RecordKind.ERRATUM)
        )
    store_one(provider, path="n.md", title="Newer", body="Two.")
    accept(provider, accepted)
    decisions = SearchFilters(record_kind=RecordKind.DECISION)
    pending_decisions = SearchFilters(
        record_kind=RecordKind.DECISION, needs_approval=True
    )
    errata = SearchFilters(record_kind=RecordKind.ERRATUM, needs_approval=True)

    recent = SearchSort.RECENT
    assert titles(provider, None, recent, decisions) == [
        "Newer",
        "Older",
        "Accepted",
    ]
    assert titles(provider, None, recent, pending_decisions) == [
        "Newer",
        "Older",
    ]
    assert titles(provider, None, recent, errata) == ["Erratum"]
    assert titles(provider, None, recent, NEEDS_APPROVAL) == [
        "Newer",
        "Erratum",
        "Older",
    ]
