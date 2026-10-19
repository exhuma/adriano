"""
Synthetic dataset seeding for benchmarking (``adriano seed-synthetic``).

A twelve-factor "admin process": a one-off command that shares the
app's code and config, run against a throwaway dev/bench database. It
generates a deterministic synthetic ADR corpus
(:mod:`app.services.seed_synthetic_gen`) and ingests it through the
same shared path poll and push use
(:func:`app.services.ingest.prepare_document`,
:func:`app.services.ingest.ingest_document`), under
:meth:`~app.storage.port.CatalogStoreProvider.lock_registration`, in
batches -- never raw SQL. Decision events are appended directly
through the store port
(:meth:`~app.storage.port.CatalogStore.append_decision`) for a share
of identities, using a synthetic reviewer identity and the configured
(or a documented fallback) policy id/version.

The target registration must already be configured in ``catalog.yaml``
(see ``bench/catalog.bench.yaml``: a ``filesystem`` registration whose
``root`` never needs to exist, because seeding never calls the
adapter -- it writes rows directly through the store port, the same
way the push intake path never calls an adapter either).
:func:`seed_catalog` syncs registrations itself, exactly like
``adriano poll``.

Safety: refuses to run against a database whose name does not look
like a dev/test/bench database unless the caller passes ``force=True``
(see :func:`looks_like_dev_database`); the CLI wires this to
``--force``.

Public API: :class:`SeedConfig`, :class:`SeedSummary`,
:data:`DEFAULT_BATCH_SIZE`, :data:`SYNTHETIC_REVIEWER_ISSUER`,
:data:`SYNTHETIC_REVIEWER_SUBJECT`, :func:`looks_like_dev_database`,
:func:`resolve_source`, :func:`seed_catalog`.
"""

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from urllib.parse import urlsplit

from app.catalog_config import CatalogConfig, PolicyConfig, SourceRegistration
from app.domain.values import Identity
from app.errors import DecisionExistsError
from app.services.ingest import (
    IncomingDocument,
    ingest_document,
    prepare_document,
)
from app.services.registrations import sync_registrations
from app.services.seed_synthetic_gen import (
    GeneratedCandidate,
    GeneratedDecision,
    GeneratedPublished,
    generate_candidates,
    generate_decisions,
    generate_published,
)
from app.storage.port import CatalogStoreProvider, NewDecision, RecordState

logger = logging.getLogger(__name__)

__all__ = [
    "DEFAULT_BATCH_SIZE",
    "SYNTHETIC_REVIEWER_ISSUER",
    "SYNTHETIC_REVIEWER_SUBJECT",
    "SeedConfig",
    "SeedSummary",
    "looks_like_dev_database",
    "resolve_source",
    "seed_catalog",
]

#: Documents (or decisions) ingested per unit of work.
DEFAULT_BATCH_SIZE = 500

#: Identity asserted for seeded decision events. Never a real token's
#: issuer/subject, so it can never collide with an actual reviewer.
SYNTHETIC_REVIEWER_ISSUER = "adriano-synthetic"
SYNTHETIC_REVIEWER_SUBJECT = "synthetic-reviewer"

#: Fallback policy used only when ``catalog.yaml`` has no valid policy.
#: A deviation of convenience -- prefer configuring one, as
#: ``bench/catalog.bench.yaml`` does, so decisions reflect a real
#: policy id/version.
FALLBACK_POLICY_ID = "bench"
FALLBACK_POLICY_VERSION = 1

#: Database name fragments considered safe to seed without ``--force``.
_SAFE_DB_HINTS = ("dev", "test", "bench", "synthetic")

#: Exact database names considered safe (the ephemeral dev/test
#: database of ``task db:up``, see ``phases/DECISIONS.md``), in
#: addition to any name containing a :data:`_SAFE_DB_HINTS` fragment.
_SAFE_DB_NAMES = frozenset({"adriano"})

type _Progress = Callable[[str], None]


@dataclass(frozen=True, slots=True, kw_only=True)
class SeedConfig:
    """
    Parameters of one seeding run.

    :param records: Number of published records to generate.
    :param projects: Number of projects to spread them across.
    :param source_id: Target registration id (must be configured and
        enabled in the loaded ``catalog.yaml``).
    :param seed: Random seed; a run is fully determined by
        ``(records, projects, source_id, seed, candidates_ratio,
        decisions_ratio)``.
    :param candidates_ratio: Share of identities that also get a
        competing candidate row.
    :param decisions_ratio: Share of identities that get an
        accept/reject decision event.
    :param batch_size: Documents/decisions per database transaction.
    """

    records: int
    projects: int
    source_id: str
    seed: int = 42
    candidates_ratio: float = 0.1
    decisions_ratio: float = 0.3
    batch_size: int = DEFAULT_BATCH_SIZE


@dataclass(frozen=True, slots=True, kw_only=True)
class SeedSummary:
    """
    Outcome of one seeding run.

    :param published: Published rows ingested.
    :param candidates: Candidate rows ingested.
    :param decisions: Decision events appended.
    """

    published: int
    candidates: int
    decisions: int


def looks_like_dev_database(database_url: str) -> bool:
    """
    Heuristically tell whether a database looks safe to seed.

    :param database_url: The plain DSN. Only the path (database name)
        is inspected; the password is never read.
    :returns: ``True`` if the database name is the ephemeral dev
        database (``adriano``) or contains a dev/test/bench/synthetic
        hint, case-insensitively.
    """
    name = urlsplit(database_url).path.lstrip("/").lower()
    if name in _SAFE_DB_NAMES:
        return True
    return any(hint in name for hint in _SAFE_DB_HINTS)


def resolve_source(config: CatalogConfig, source_id: str) -> SourceRegistration:
    """
    Find the enabled registration seeding will write to.

    :param config: Loaded catalog configuration.
    :param source_id: Requested registration id.
    :returns: The registration.
    :raises ValueError: If it is not configured or disabled.
    """
    source = config.get_source(source_id)
    if source is None:
        raise ValueError(
            f"source {source_id!r} is not configured in catalog.yaml "
            "(see bench/catalog.bench.yaml for a template)"
        )
    if not source.enabled:
        raise ValueError(
            f"source {source_id!r} is disabled: {source.config_error}"
        )
    return source


def _policy_ids(policy_config: PolicyConfig) -> tuple[str, int]:
    """
    Resolve the policy id/version decisions are recorded against.

    :param policy_config: The loaded policy status.
    :returns: The configured policy's id/version, or the documented
        fallback when none is configured.
    """
    if policy_config.policy is not None:
        return policy_config.policy.id, policy_config.policy.version
    return FALLBACK_POLICY_ID, FALLBACK_POLICY_VERSION


def _batches[T](items: Sequence[T], size: int) -> list[Sequence[T]]:
    """
    Split *items* into fixed-size batches.

    :param items: Items to split.
    :param size: Maximum batch size.
    :returns: The batches, in order.
    """
    return [items[start : start + size] for start in range(0, len(items), size)]


def _ingest_published(
    provider: CatalogStoreProvider,
    source: SourceRegistration,
    docs: Sequence[GeneratedPublished],
    batch_size: int,
    report: _Progress,
) -> int:
    """
    Ingest published documents in batches, each its own unit of work.

    :param provider: Storage provider.
    :param source: Target registration.
    :param docs: Generated documents.
    :param batch_size: Documents per transaction.
    :param report: Progress callback.
    :returns: Number of documents ingested.
    """
    count = 0
    for batch in _batches(docs, batch_size):
        with provider.lock_registration(source.id) as store:
            for doc in batch:
                prepared = prepare_document(
                    IncomingDocument(
                        source_id=source.id,
                        project=doc.project,
                        path=doc.path,
                        ref=source.published_ref,
                        content=doc.content,
                    )
                )
                ingest_document(store, prepared, RecordState.PUBLISHED)
                count += 1
        report(f"published {count}/{len(docs)}")
    return count


def _ingest_candidates(
    provider: CatalogStoreProvider,
    source: SourceRegistration,
    docs: Sequence[GeneratedCandidate],
    batch_size: int,
    report: _Progress,
) -> int:
    """
    Ingest candidate documents in batches, each its own unit of work.

    :param provider: Storage provider.
    :param source: Target registration.
    :param docs: Generated candidates.
    :param batch_size: Documents per transaction.
    :param report: Progress callback.
    :returns: Number of candidates ingested.
    """
    count = 0
    for batch in _batches(docs, batch_size):
        with provider.lock_registration(source.id) as store:
            for doc in batch:
                prepared = prepare_document(
                    IncomingDocument(
                        source_id=source.id,
                        project=doc.project,
                        path=doc.path,
                        ref=doc.ref,
                        content=doc.content,
                    )
                )
                ingest_document(store, prepared, RecordState.CANDIDATE)
                count += 1
        report(f"candidates {count}/{len(docs)}")
    return count


def _append_decisions(
    provider: CatalogStoreProvider,
    source: SourceRegistration,
    decisions: Sequence[GeneratedDecision],
    policy_id: str,
    policy_version: int,
    batch_size: int,
    report: _Progress,
) -> int:
    """
    Append decision events in batches, each its own unit of work.

    Re-running with the same seed is safe: a decision that already
    exists for its (identity, digest) is skipped rather than failing
    the batch.

    :param provider: Storage provider.
    :param source: Target registration.
    :param decisions: Generated decisions.
    :param policy_id: Policy id to record.
    :param policy_version: Policy version to record.
    :param batch_size: Decisions per transaction.
    :param report: Progress callback.
    :returns: Number of decisions newly appended.
    """
    count = 0
    for batch in _batches(decisions, batch_size):
        with provider.unit_of_work() as store:
            for item in batch:
                decision = NewDecision(
                    identity=Identity(
                        source.id, item.project, str(item.adr_uuid)
                    ),
                    adr_uuid=item.adr_uuid,
                    digest=item.digest,
                    action=item.action,
                    actor_issuer=SYNTHETIC_REVIEWER_ISSUER,
                    actor_subject=SYNTHETIC_REVIEWER_SUBJECT,
                    actor_display="Synthetic Reviewer",
                    actor_email=None,
                    comment="seeded synthetic decision",
                    policy_id=policy_id,
                    policy_version=policy_version,
                )
                try:
                    store.append_decision(decision)
                    count += 1
                except DecisionExistsError:
                    logger.debug(
                        "decision for %s already exists; skipping",
                        decision.identity,
                    )
        report(f"decisions {count}/{len(decisions)}")
    return count


def seed_catalog(
    provider: CatalogStoreProvider,
    config: CatalogConfig,
    seed_config: SeedConfig,
    *,
    progress: _Progress | None = None,
) -> SeedSummary:
    """
    Generate and ingest a deterministic synthetic ADR corpus.

    :param provider: Storage provider for the target database.
    :param config: Loaded catalog configuration; the ``source_id`` of
        *seed_config* must be one of its enabled registrations.
    :param seed_config: Generation and batching parameters.
    :param progress: Called with a short status line after each batch
        and generation step; defaults to a no-op.
    :returns: Counts of what was written.
    :raises ValueError: If the source is not configured or disabled.
    """
    report = progress or (lambda _message: None)
    source = resolve_source(config, seed_config.source_id)
    sync_registrations(provider, config)
    policy_id, policy_version = _policy_ids(config.policy)
    published = generate_published(
        records=seed_config.records,
        projects=seed_config.projects,
        seed=seed_config.seed,
        path_prefix=source.path,
    )
    candidates = generate_candidates(
        published,
        ratio=seed_config.candidates_ratio,
        seed=seed_config.seed,
    )
    decisions = generate_decisions(
        published,
        ratio=seed_config.decisions_ratio,
        seed=seed_config.seed,
    )
    report(
        f"generated {len(published)} published, {len(candidates)} "
        f"candidates, {len(decisions)} decisions"
    )
    published_count = _ingest_published(
        provider, source, published, seed_config.batch_size, report
    )
    candidate_count = _ingest_candidates(
        provider, source, candidates, seed_config.batch_size, report
    )
    decision_count = _append_decisions(
        provider,
        source,
        decisions,
        policy_id,
        policy_version,
        seed_config.batch_size,
        report,
    )
    return SeedSummary(
        published=published_count,
        candidates=candidate_count,
        decisions=decision_count,
    )
