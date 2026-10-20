"""
Read-only views of source registrations and search facets.

Same rules as :mod:`app.services.search` (a
:class:`~app.storage.port.CatalogStore` inside the caller's unit of
work, plain dataclasses out, no FastAPI, no source adapter).

Public API: :class:`SourceSummary`, :class:`FacetProject`,
:class:`FacetSource`, :class:`CatalogFacets`, :func:`is_stale`,
:func:`list_sources`, :func:`get_facets`.
"""

import datetime
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from app.catalog_config import SourceRegistration
from app.domain.frontmatter import JsonValue
from app.storage.port import (
    CatalogStore,
    IntakeKind,
    PollStatus,
    Registration,
)

__all__ = [
    "CatalogFacets",
    "FacetProject",
    "FacetSource",
    "SourceSummary",
    "get_facets",
    "is_stale",
    "list_sources",
]


def is_stale(
    registration: Registration | None,
    now: datetime.datetime,
    stale_after_minutes: int,
) -> bool:
    """
    Tell whether a registration's indexed content may be out of date.

    Stale when the registration never succeeded, its latest poll
    failed or was partial, or its latest success is older than
    *stale_after_minutes*.

    :param registration: The registration, or ``None`` if unknown.
    :param now: The current time (injected for testability).
    :param stale_after_minutes: Configured staleness threshold.
    :returns: Whether the registration is stale.
    """
    if registration is None or registration.last_success_at is None:
        return True
    if registration.last_status in (PollStatus.FAILED, PollStatus.PARTIAL):
        return True
    age = now - registration.last_success_at
    return age > datetime.timedelta(minutes=stale_after_minutes)


@dataclass(frozen=True, slots=True, kw_only=True)
class SourceSummary:
    """
    One source registration's configuration and freshness.

    :param id: Registration id.
    :param type: Source type.
    :param enabled: Whether the registration may be polled / pushed to.
    :param config_error: Why the registration is disabled, if invalid.
    :param intake: Enabled intake mechanisms, from the current
        configuration (empty for a registration removed from
        ``catalog.yaml``).
    :param published_ref: Configured published ref, from the current
        configuration (blank if removed from ``catalog.yaml``).
    :param last_attempt_at: Start of the latest poll attempt.
    :param last_success_at: Start of the latest fully successful poll.
    :param last_status: Outcome of the latest poll.
    :param last_error: Secret-free error details of the latest poll.
    :param stale: Whether the indexed content may be out of date.
    """

    id: str
    type: str
    enabled: bool
    config_error: str | None
    intake: tuple[IntakeKind, ...]
    published_ref: str
    last_attempt_at: datetime.datetime | None
    last_success_at: datetime.datetime | None
    last_status: PollStatus
    last_error: JsonValue
    stale: bool


def list_sources(
    store: CatalogStore,
    config_sources: Sequence[SourceRegistration],
    *,
    now: datetime.datetime,
    stale_after_minutes: int,
) -> tuple[SourceSummary, ...]:
    """
    List every stored registration with its configuration and freshness.

    Registrations removed from ``catalog.yaml`` are still listed (they
    are disabled, never deleted, per ``sync_registrations``); their
    ``intake``/``published_ref`` are empty/blank since the current
    configuration no longer describes them.

    :param store: Store of the caller's unit of work.
    :param config_sources: The current configuration's registrations.
    :param now: The current time (injected for testability).
    :param stale_after_minutes: Configured staleness threshold.
    :returns: One summary per stored registration, ordered by id.
    """
    config_by_id = {source.id: source for source in config_sources}
    summaries = []
    for registration in store.list_registrations():
        config = config_by_id.get(registration.id)
        summaries.append(
            SourceSummary(
                id=registration.id,
                type=registration.type,
                enabled=registration.enabled,
                config_error=registration.config_error,
                intake=(
                    tuple(sorted(config.intake, key=lambda k: k.value))
                    if config
                    else ()
                ),
                published_ref=config.published_ref if config else "",
                last_attempt_at=registration.last_attempt_at,
                last_success_at=registration.last_success_at,
                last_status=registration.last_status,
                last_error=registration.last_error,
                stale=is_stale(registration, now, stale_after_minutes),
            )
        )
    return tuple(summaries)


@dataclass(frozen=True, slots=True, kw_only=True)
class FacetProject:
    """
    Record count of one project within a source.

    :param project: Project path.
    :param count: Number of decision rows (published and candidate)
        in it; errata are not counted.
    """

    project: str
    count: int


@dataclass(frozen=True, slots=True, kw_only=True)
class FacetSource:
    """
    One source's projects, for the filter select.

    :param source_id: Registration id.
    :param count: Total rows across the source's projects.
    :param projects: Projects of this source, with their counts.
    """

    source_id: str
    count: int
    projects: tuple[FacetProject, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class CatalogFacets:
    """
    Filter options for the search UI.

    :param sources: Sources with their projects and counts.
    """

    sources: tuple[FacetSource, ...]


def get_facets(store: CatalogStore) -> CatalogFacets:
    """
    Build the source/project filter options with record counts.

    :param store: Store of the caller's unit of work.
    :returns: The facets, sources ordered as
        :meth:`~app.storage.port.CatalogStore.list_facets` returns them.
    """
    by_source: dict[str, list[FacetProject]] = defaultdict(list)
    for entry in store.list_facets():
        by_source[entry.source_id].append(
            FacetProject(project=entry.project, count=entry.count)
        )
    return CatalogFacets(
        sources=tuple(
            FacetSource(
                source_id=source_id,
                count=sum(project.count for project in projects),
                projects=tuple(projects),
            )
            for source_id, projects in by_source.items()
        )
    )
