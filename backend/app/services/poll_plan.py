"""
Value types and pure planning steps of a poll run.

Used by :mod:`app.services.polling`: :class:`PollPlan` collects what a
registration's poll found (counters, problems, documents to write,
tokens to refresh, locations that are gone); :func:`plan_project`
skips unchanged documents and records vanished files for one project
listing; :func:`plan_vanished_project` does the same for a project that
left a complete project listing; :func:`bounded` runs adapter calls
with bounded concurrency. Applying a plan (the UUID holder rule,
deletions, the not-indexed list) is :mod:`app.services.poll_apply`.

Listings know paths before content is fetched, so change detection is
keyed by location: the stored published rows of the registration
(:attr:`StoredState.own`) and its poll entries of the not-indexed list
(:attr:`StoredState.queued`), both by project and path.

Public API: :class:`PollProblem`, :class:`PollCounts`,
:class:`PollOutcome`, :class:`PollPlan`, :class:`StoredState`,
:func:`bounded`, :func:`plan_project`, :func:`plan_vanished_project`.
"""

import asyncio
import uuid
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import asdict, dataclass, field

from app.domain.frontmatter import JsonValue
from app.domain.titles import is_adr_filename
from app.services.ingest import PreparedDocument
from app.sources.port import DocumentListing, SourceDocument, SourceProject
from app.storage.port import (
    ChangeTokenEntry,
    NotIndexedEntry,
    NotIndexedWrite,
    PollStatus,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class PollProblem:
    """
    One finding of a poll run.

    :param code: Stable code: ``source_error``, ``projects_incomplete``,
        ``listing_failed``, ``listing_incomplete``, ``fetch_failed``,
        ``not_pollable``, ``internal_error``.
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
    :param documents: ADR files listed.
    :param unchanged: Documents skipped without fetching.
    :param fetched: Documents fetched.
    :param created: New published rows.
    :param updated: Rows whose digest changed.
    :param moved: Rows whose file moved (path, project or registration)
        and kept their identity.
    :param same_content: Fetched rows whose digest did not change.
    :param tokens_refreshed: Unchanged rows whose change token moved.
    :param deleted: Published rows removed by reconciliation.
    :param not_indexed: Documents written to the not-indexed list.
    :param failed: Listings or fetches that failed.
    """

    projects: int = 0
    documents: int = 0
    unchanged: int = 0
    fetched: int = 0
    created: int = 0
    updated: int = 0
    moved: int = 0
    same_content: int = 0
    tokens_refreshed: int = 0
    deleted: int = 0
    not_indexed: int = 0
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


@dataclass(frozen=True, slots=True)
class StoredState:
    """
    Stored state of one registration, read before collecting.

    :param own: Project -> path -> stored published row.
    :param queued: Project -> path -> poll entries of the not-indexed
        list (one per ref; normally exactly one).
    """

    own: dict[str, dict[str, ChangeTokenEntry]]
    queued: dict[str, dict[str, list[NotIndexedEntry]]]

    def token(self, project: str, path: str) -> str | None:
        """
        Pick the stored change token of a listed file.

        :param project: Project path.
        :param path: File path.
        :returns: The published row's token, else the token of a
            not-indexed entry, else ``None``.
        """
        entry = self.own.get(project, {}).get(path)
        if entry is not None:
            return entry.change_token
        for queued in self.queued.get(project, {}).get(path, []):
            if queued.change_token is not None:
                return queued.change_token
        return None


@dataclass(slots=True)
class PollPlan:
    """
    Everything collected for one registration, applied under lock.

    :param counts: Counters.
    :param problems: Findings.
    :param complete: ``False`` once anything was incomplete or failed.
    :param stored: Stored state the plan was made against.
    :param prepared: Fetched documents to index (or list as not
        indexed), in listing order.
    :param unreadable: Not-indexed entries of documents whose fetch
        failed.
    :param refresh: ``(stored row, new token)`` of unchanged documents.
    :param vanished: Stored rows whose file is gone from a complete
        listing.
    :param vanished_queue: Not-indexed entries whose file is gone from
        a complete listing.
    """

    counts: PollCounts = field(default_factory=PollCounts)
    problems: list[PollProblem] = field(default_factory=list)
    complete: bool = True
    stored: StoredState = field(default_factory=lambda: StoredState({}, {}))
    prepared: list[PreparedDocument] = field(default_factory=list)
    unreadable: list[NotIndexedWrite] = field(default_factory=list)
    refresh: list[tuple[ChangeTokenEntry, str | None]] = field(
        default_factory=list
    )
    vanished: list[ChangeTokenEntry] = field(default_factory=list)
    vanished_queue: list[NotIndexedEntry] = field(default_factory=list)

    def fail(self, problem: PollProblem) -> None:
        """
        Record a problem that makes the run partial.

        :param problem: The problem.
        """
        self.problems.append(problem)
        self.counts.failed += 1
        self.complete = False

    def forget_vanished(self) -> None:
        """Drop every planned removal (an incomplete project listing)."""
        self.vanished.clear()
        self.vanished_queue.clear()


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


def _needs_fetch(
    document: SourceDocument,
    entry: ChangeTokenEntry | None,
    queued: list[NotIndexedEntry],
) -> bool:
    """
    Tell whether a listed document must be read.

    :param document: The listed document.
    :param entry: Its stored published row, if any.
    :param queued: Its not-indexed entries, if any.
    :returns: ``True`` when it changed or nothing stored proves that it
        did not (a not-indexed entry without a matching token).
    """
    if document.changed:
        return True
    if entry is not None:
        return False
    return not any(
        q.change_token is not None and q.change_token == document.change_token
        for q in queued
    )


def plan_project(
    project: SourceProject,
    listing: DocumentListing,
    plan: PollPlan,
) -> list[SourceDocument]:
    """
    Skip unchanged documents and record vanished files of a project.

    :param project: The project.
    :param listing: Its document listing.
    :param plan: Plan to fill (its :attr:`PollPlan.stored` is read).
    :returns: Documents to fetch.
    """
    own = plan.stored.own.get(project.path, {})
    queued = plan.stored.queued.get(project.path, {})
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
        seen.add(document.path)
        plan.counts.documents += 1
        entry = own.get(document.path)
        if _needs_fetch(document, entry, queued.get(document.path, [])):
            to_fetch.append(document)
            continue
        plan.counts.unchanged += 1
        if entry is not None and entry.change_token != document.change_token:
            plan.refresh.append((entry, document.change_token))
    if listing.complete:
        plan.vanished += [e for p, e in own.items() if p not in seen]
        plan.vanished_queue += [
            q for p, entries in queued.items() if p not in seen for q in entries
        ]
    return to_fetch


def plan_vanished_project(project: str, plan: PollPlan) -> None:
    """
    Record every stored file of a project gone from the project listing.

    Only call this for a complete project listing.

    :param project: The project path.
    :param plan: Plan to fill.
    """
    plan.vanished += plan.stored.own.get(project, {}).values()
    plan.vanished_queue += [
        q
        for entries in plan.stored.queued.get(project, {}).values()
        for q in entries
    ]
