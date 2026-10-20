"""Tests for ``CatalogStore.list_facets``."""

import dataclasses

from app.domain.values import RecordKind
from app.storage.postgres.store import PostgresStoreProvider
from tests.storage.conftest import put_record


def test_list_facets_counts_rows_per_source_and_project(
    provider: PostgresStoreProvider,
) -> None:
    """Ensure counts are grouped by source then project, both states."""
    with provider.unit_of_work() as store:
        a = put_record(store, project="platform", path="doc/decisions/a.md")
        store.upsert_published(a)
        b = put_record(store, project="platform", path="doc/decisions/b.md")
        store.upsert_published(b)
        c = put_record(
            store,
            project="platform",
            path="doc/decisions/c.md",
            ref="feature",
        )
        store.upsert_candidate(c)
        d = put_record(
            store, source_id="other", project="payments", path="doc/d.md"
        )
        store.upsert_published(d)

        entries = store.list_facets()

    by_pair = {(e.source_id, e.project): e.count for e in entries}
    assert by_pair == {
        ("central", "platform"): 3,
        ("other", "payments"): 1,
    }


def test_list_facets_is_empty_for_an_empty_catalog(
    provider: PostgresStoreProvider,
) -> None:
    """Ensure no rows yields no facets."""
    with provider.unit_of_work() as store:
        entries = store.list_facets()

    assert entries == []


def test_list_facets_does_not_count_errata(
    provider: PostgresStoreProvider,
) -> None:
    """Ensure facets count decisions only, like the default search."""
    with provider.unit_of_work() as store:
        decision = put_record(store, path="doc/decisions/a.md")
        store.upsert_published(decision)
        erratum = dataclasses.replace(
            put_record(store, path="doc/decisions/errata/b.md"),
            record_kind=RecordKind.ERRATUM,
        )
        store.upsert_published(erratum)
        only_errata = dataclasses.replace(
            put_record(store, project="payments", path="doc/c.md"),
            record_kind=RecordKind.ERRATUM,
        )
        store.upsert_published(only_errata)

        entries = store.list_facets()

    by_pair = {(e.source_id, e.project): e.count for e in entries}
    assert by_pair == {("central", "platform"): 1}
