"""Tests for the synthetic benchmark dataset generator and seeder."""

import datetime
import io
from pathlib import Path

import pytest

from app.catalog_config import CatalogConfig, parse_catalog_config
from app.cli import EXIT_OK, EXIT_USAGE, main
from app.config import Settings
from app.domain.issues import Severity
from app.domain.records import parse_record
from app.services.seed_synthetic import (
    SeedConfig,
    looks_like_dev_database,
    resolve_source,
    seed_catalog,
)
from app.services.seed_synthetic_gen import (
    generate_candidates,
    generate_decisions,
    generate_published,
)
from app.sources.registry import default_registry
from app.storage.port import RecordState, SearchFilters
from app.storage.postgres.store import PostgresStoreProvider

_SEED_CATALOG = """
sources:
  - id: central
    type: filesystem
    root: ./does-not-exist
    published_ref: bench
approval_policy: {id: bench, version: 1, reviewers: {roles: [r]}}
rbac: {roles: {admin: [read, operate]}}
"""

_TODAY = datetime.date(2026, 10, 19)


def _catalog(source_id: str = "central") -> CatalogConfig:
    """
    Build a small, valid catalog configuration for the tests.

    :param source_id: Registration id of the single filesystem source.
    :returns: The parsed configuration (``root`` never needs to exist).
    """
    data = {
        "sources": [
            {
                "id": source_id,
                "type": "filesystem",
                "root": "./does-not-exist",
                "path": "doc/decisions",
                "published_ref": "bench",
            }
        ],
        "approval_policy": {
            "id": "bench",
            "version": 1,
            "required": True,
            "reviewers": {"roles": ["adr-reviewer"]},
        },
    }
    return parse_catalog_config(
        data,
        path="<test>",
        env={},
        registry=default_registry(),
        base_dir=Path("."),
    )


def test_generate_published_is_deterministic() -> None:
    """Ensure the same seed and inputs yield byte-identical documents."""
    first = generate_published(records=25, projects=4, seed=7, today=_TODAY)
    second = generate_published(records=25, projects=4, seed=7, today=_TODAY)
    assert [doc.content for doc in first] == [doc.content for doc in second]
    assert [doc.path for doc in first] == [doc.path for doc in second]
    assert [doc.adr_uuid for doc in first] == [doc.adr_uuid for doc in second]


def test_generate_published_different_seed_differs() -> None:
    """Ensure a different seed produces a different corpus."""
    first = generate_published(records=25, projects=4, seed=1, today=_TODAY)
    second = generate_published(records=25, projects=4, seed=2, today=_TODAY)
    assert [doc.content for doc in first] != [doc.content for doc in second]


def test_generated_documents_are_mostly_valid() -> None:
    """Ensure most generated documents parse without validation errors."""
    docs = generate_published(records=200, projects=10, seed=3, today=_TODAY)
    parsed = [
        parse_record(doc.content, filename=doc.path.rsplit("/", 1)[-1])
        for doc in docs
    ]
    error_count = sum(
        1
        for record in parsed
        for issue in record.issues
        if issue.severity is Severity.ERROR
    )
    # The generator deliberately injects an error-causing issue (missing
    # uuid or a bad date) for ~5% x 2/3 of records; allow generous slack.
    assert error_count / len(docs) < 0.1
    # Body length bounds from the module docstring.
    for record in parsed:
        assert 300 <= len(record.body) <= 3100


def test_link_targets_exist_among_earlier_records() -> None:
    """Ensure every authored link targets an earlier record's UUID."""
    docs = generate_published(records=300, projects=15, seed=11, today=_TODAY)
    seen: set = set()
    for doc in docs:
        record = parse_record(doc.content, filename=doc.path.rsplit("/", 1)[-1])
        for target in record.links.updates + record.links.obsoletes:
            assert target in seen, "link target must be an earlier record"
        if record.links.corrects is not None:
            assert record.links.corrects in seen
        if doc.adr_uuid is not None:
            seen.add(doc.adr_uuid)


def test_generate_candidates_and_decisions_are_deterministic() -> None:
    """Ensure candidate and decision generation is seed-deterministic."""
    published = generate_published(records=50, projects=5, seed=4, today=_TODAY)
    candidates_a = generate_candidates(published, ratio=0.4, seed=4)
    candidates_b = generate_candidates(published, ratio=0.4, seed=4)
    assert [c.adr_uuid for c in candidates_a] == [
        c.adr_uuid for c in candidates_b
    ]
    decisions_a = generate_decisions(published, ratio=0.4, seed=4)
    decisions_b = generate_decisions(published, ratio=0.4, seed=4)
    assert [(d.adr_uuid, d.action) for d in decisions_a] == [
        (d.adr_uuid, d.action) for d in decisions_b
    ]
    # Every candidate/decision digest matches a real published document.
    published_uuids = {doc.adr_uuid for doc in published}
    assert all(c.adr_uuid in published_uuids for c in candidates_a)
    assert all(d.adr_uuid in published_uuids for d in decisions_a)


def test_looks_like_dev_database() -> None:
    """Ensure the safety heuristic matches dev/test/bench names only."""
    assert looks_like_dev_database("postgresql://u:p@host:5432/adriano_test")
    assert looks_like_dev_database("postgresql://u:p@host:5432/bench_db")
    # The ephemeral `task db:up` dev database, used by `task bench`.
    assert looks_like_dev_database("postgresql://u:p@host:55432/adriano")
    assert not looks_like_dev_database("postgresql://u:p@host:5432/production")


def test_resolve_source_rejects_unknown_or_disabled() -> None:
    """Ensure resolve_source reports a clear error for a bad source id."""
    config = _catalog()
    with pytest.raises(ValueError, match="missing"):
        resolve_source(config, "missing")


def test_seed_catalog_ingests_through_the_shared_path(
    provider: PostgresStoreProvider,
) -> None:
    """Ensure seeding writes published, candidate and decision rows."""
    config = _catalog("central")
    seed_config = SeedConfig(
        records=12,
        projects=3,
        source_id="central",
        seed=5,
        candidates_ratio=0.5,
        decisions_ratio=0.5,
    )
    messages: list[str] = []
    summary = seed_catalog(
        provider, config, seed_config, progress=messages.append
    )
    assert summary.published == 12
    assert summary.candidates >= 1
    assert summary.decisions >= 1
    assert messages  # progress was reported

    with provider.unit_of_work() as store:
        page = store.search(
            None,
            SearchFilters(source_id="central"),
            1,
            50,
            policy=config.policy.policy,
        )
        published_rows = [
            item for item in page.items if item.kind is RecordState.PUBLISHED
        ]
        candidate_rows = [
            item for item in page.items if item.kind is RecordState.CANDIDATE
        ]
    assert len(published_rows) == 12
    assert len(candidate_rows) == summary.candidates

    # Re-running with the same seed is idempotent (no duplicate-key
    # failures from upserts or already-decided decisions).
    summary_again = seed_catalog(provider, config, seed_config)
    assert summary_again.published == 12
    assert summary_again.decisions == 0  # already recorded


def test_cli_seeds_through_the_test_database(
    tmp_path: Path, test_settings: Settings, provider: PostgresStoreProvider
) -> None:
    """Ensure ``adriano seed-synthetic`` runs end to end via the CLI."""
    path = tmp_path / "catalog.yaml"
    path.write_text(_SEED_CATALOG, encoding="utf-8")
    settings = test_settings.model_copy(update={"config_file": str(path)})
    out = io.StringIO()

    code = main(
        [
            "seed-synthetic",
            "--records",
            "5",
            "--projects",
            "2",
            "--source-id",
            "central",
        ],
        settings=settings,
        out=out,
    )

    assert code == EXIT_OK
    assert "seeded 5 published" in out.getvalue()
    with provider.unit_of_work() as store:
        page = store.search(
            None, SearchFilters(source_id="central"), 1, 50, policy=None
        )
    assert page.total >= 5


def test_cli_refuses_unsafe_database_without_force(
    tmp_path: Path, test_settings: Settings
) -> None:
    """Ensure seed-synthetic refuses a database that is not dev/bench."""
    path = tmp_path / "catalog.yaml"
    path.write_text(_SEED_CATALOG, encoding="utf-8")
    unsafe_url = "postgresql://u:p@localhost:55432/production"
    settings = test_settings.model_copy(
        update={"config_file": str(path), "database_url": unsafe_url}
    )

    code = main(
        [
            "seed-synthetic",
            "--records",
            "5",
            "--projects",
            "2",
            "--source-id",
            "central",
        ],
        settings=settings,
        out=io.StringIO(),
    )

    assert code == EXIT_USAGE


def test_cli_rejects_unknown_source(
    tmp_path: Path, test_settings: Settings
) -> None:
    """Ensure seed-synthetic reports an unconfigured ``--source-id``."""
    path = tmp_path / "catalog.yaml"
    path.write_text(_SEED_CATALOG, encoding="utf-8")
    settings = test_settings.model_copy(update={"config_file": str(path)})

    code = main(
        [
            "seed-synthetic",
            "--records",
            "5",
            "--projects",
            "2",
            "--source-id",
            "nope",
        ],
        settings=settings,
        out=io.StringIO(),
    )

    assert code == EXIT_USAGE
