"""
Value types and pure planning steps of a poll run.

Used by :mod:`app.services.polling`: :class:`PollPlan` collects what a
run found (counters, problems, documents to write, tokens to refresh,
rows to delete); :func:`plan_project` applies the ownership rule, skips
unchanged documents and plans deletions for one project listing;
:func:`bounded` runs adapter calls with bounded concurrency.

Public API: :class:`PollProblem`, :class:`PollCounts`,
:class:`PollOutcome`, :class:`PollPlan`, :class:`StoredState`,
:func:`bounded`, :func:`plan_project`.
"""

import asyncio
import uuid
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import asdict, dataclass, field

from app.domain.frontmatter import JsonValue
from app.domain.titles import is_adr_filename
from app.services.ingest import PreparedDocument
from app.sources.port import DocumentListing, SourceDocument, SourceProject
from app.storage.port import ChangeTokenEntry, PollStatus


@dataclass(frozen=True, slots=True, kw_only=True)
class PollProblem:
    """
    One finding of a poll run.

    :param code: Stable code: ``source_error``, ``projects_incomplete``,
        ``listing_failed``, ``listing_incomplete``, ``fetch_failed``,
        ``ownership_conflict``, ``not_pollable``, ``internal_error``.
    :param message: Actionable, secret-free description.
    :param project: Affected project, if any.
    :param path: Affected file path, if any.
    """

    code: str
    message: str
    project: str | None = None
    path: str | None = None

    def to_json(self) -> dict[str, JsonValue]:
        """
        Convert to the JSON stored in ``intake_run.errors``.

        :returns: The mapping (``None`` fields omitted).
        """
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass(slots=True)
class PollCounts:
    """
    Counters of one poll run.

    :param projects: Projects listed.
    :param documents: Documents listed and owned by the registration.
    :param unchanged: Documents skipped without fetching.
    :param fetched: Documents fetched.
    :param created: New published rows.
    :param updated: Rows whose digest changed.
    :param same_content: Fetched rows whose digest did not change.
    :param tokens_refreshed: Unchanged rows whose change token moved.
    :param deleted: Published rows removed by reconciliation.
    :param skipped_owned: Files skipped (owned by an earlier
        registration).
    :param failed: Listings or fetches that failed.
    """

    projects: int = 0
    documents: int = 0
    unchanged: int = 0
    fetched: int = 0
    created: int = 0
    updated: int = 0
    same_content: int = 0
    tokens_refreshed: int = 0
    deleted: int = 0
    skipped_owned: int = 0
    failed: int = 0

    def to_json(self) -> dict[str, JsonValue]:
        """
        Convert to the JSON stored in ``intake_run.counts``.

        :returns: The counters.
        """
        return dict(asdict(self))


@dataclass(frozen=True, slots=True, kw_only=True)
class PollOutcome:
    """
    Result of polling one registration.

    :param source_id: Registration id.
    :param status: Outcome (``disabled`` when not pollable).
    :param run_id: Intake run id (``None`` when nothing ran).
    :param counts: Counters.
    :param problems: Findings.
    """

    source_id: str
    status: PollStatus
    run_id: uuid.UUID | None
    counts: PollCounts
    problems: tuple[PollProblem, ...]


@dataclass(slots=True)
class PollPlan:
    """
    Everything collected for one registration, applied under lock.

    :param counts: Counters.
    :param problems: Findings.
    :param complete: ``False`` once anything was incomplete or failed.
    :param prepared: Fetched documents to ingest.
    :param refresh: ``(record id, new token)`` of unchanged documents.
    :param delete: Published row ids to delete.
    """

    counts: PollCounts = field(default_factory=PollCounts)
    problems: list[PollProblem] = field(default_factory=list)
    complete: bool = True
    prepared: list[PreparedDocument] = field(default_factory=list)
    refresh: list[tuple[uuid.UUID, str | None]] = field(default_factory=list)
    delete: list[uuid.UUID] = field(default_factory=list)

    def fail(self, problem: PollProblem) -> None:
        """
        Record a problem that makes the run partial.

        :param problem: The problem.
        """
        self.problems.append(problem)
        self.counts.failed += 1
        self.complete = False


@dataclass(frozen=True, slots=True)
class StoredState:
    """
    Stored state read before collecting.

    :param own: Project -> path -> stored entry of this registration.
    :param owned_elsewhere: ``(project, path)`` stored by earlier
        registrations.
    """

    own: dict[str, dict[str, ChangeTokenEntry]]
    owned_elsewhere: frozenset[tuple[str, str]]


async def bounded[T](
    limit: int, jobs: Iterable[Callable[[], Awaitable[T]]]
) -> list[T]:
    """
    Run coroutine factories with bounded concurrency, keeping order.

    :param limit: Maximum concurrently running jobs.
    :param jobs: Coroutine factories.
    :returns: Results in job order.
    """
    semaphore = asyncio.Semaphore(limit)

    async def run(job: Callable[[], Awaitable[T]]) -> T:
        async with semaphore:
            return await job()

    return list(await asyncio.gather(*(run(job) for job in jobs)))


def plan_project(
    project: SourceProject,
    listing: DocumentListing,
    stored: StoredState,
    plan: PollPlan,
) -> list[SourceDocument]:
    """
    Apply ownership, skip unchanged and plan deletions of a project.

    :param project: The project.
    :param listing: Its document listing.
    :param stored: Stored state.
    :param plan: Plan to fill.
    :returns: Documents to fetch.
    """
    own = stored.own.get(project.path, {})
    for message in listing.problems:
        plan.fail(
            PollProblem(
                code="listing_incomplete",
                message=message,
                project=project.path,
            )
        )
    if not listing.complete:
        plan.complete = False
    seen: set[str] = set()
    to_fetch: list[SourceDocument] = []
    for document in listing.documents:
        if not is_adr_filename(document.path):
            continue
        if (project.path, document.path) in stored.owned_elsewhere:
            plan.counts.skipped_owned += 1
            plan.problems.append(
                PollProblem(
                    code="ownership_conflict",
                    message="owned by an earlier registration; skipped",
                    project=project.path,
                    path=document.path,
                )
            )
            continue
        seen.add(document.path)
        plan.counts.documents += 1
        entry = own.get(document.path)
        if document.changed or entry is None:
            to_fetch.append(document)
            continue
        plan.counts.unchanged += 1
        if entry.change_token != document.change_token:
            plan.refresh.append((entry.id, document.change_token))
    if listing.complete:
        plan.delete += [e.id for p, e in own.items() if p not in seen]
    return to_fetch
