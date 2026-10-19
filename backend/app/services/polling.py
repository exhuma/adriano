"""
Poll orchestration: list, skip unchanged, fetch, ingest, reconcile, log.

:class:`PollingService` polls registrations one after another in
configuration order (ownership depends on that order). Each registration
runs in three phases:

1. **Run log** -- an ``intake_run`` row is started in its own unit of
   work, so it survives a rollback of the ingest transaction.
2. **Collect** (no transaction held, no lock) -- open the adapter
   (:attr:`~app.sources.registry.SourceBinding.open_adapter`), list
   projects, list each project's documents with the stored change
   tokens (bounded concurrency), drop documents owned by an earlier
   registration (``ownership_conflict`` warning), fetch only changed
   documents (bounded concurrency) and prepare them with the shared
   ingest path (:func:`app.services.ingest.prepare_document`).
3. **Apply** -- under
   :meth:`~app.storage.port.CatalogStoreProvider.lock_registration` (one
   transaction): ingest the fetched documents, rewrite change tokens of
   unchanged documents whose token moved, and delete published rows that
   a *complete* listing no longer contains.

Finally, in a separate unit of work, the run is finished and the
registration's ``last_attempt_at / last_success_at / last_status /
last_error`` are set.

Reconciliation rules: nothing is deleted unless the project listing was
complete; within a project, nothing is deleted unless its document
listing was complete. A vanished project (complete project listing)
loses its published rows. Candidates are never deleted by polling.

Ownership: the first enabled registration in configuration order whose
stored published rows contain a ``(project, path)`` owns it; later
registrations skip that file (and drop their own stale copy).

Statuses: ``failed`` when no project listing could be produced, the
adapter could not be opened or the write failed (prior content is kept);
``partial`` when any listing was incomplete or any fetch failed;
otherwise ``ok``. A failure in one registration never affects others.

Public API: :data:`DEFAULT_CONCURRENCY`, :class:`PollingService`, and
re-exported from :mod:`app.services.poll_plan`: :class:`PollProblem`,
:class:`PollCounts`, :class:`PollOutcome`.
"""

import datetime
import logging
import uuid
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import fields

from app.catalog_config import SourceRegistration
from app.domain.frontmatter import JsonValue
from app.errors import NotFoundError
from app.services.ingest import (
    IncomingDocument,
    PreparedDocument,
    ingest_document,
    prepare_document,
)
from app.services.poll_plan import (
    PollCounts,
    PollOutcome,
    PollPlan,
    PollProblem,
    StoredState,
    bounded,
    plan_project,
)
from app.sources.port import (
    DocumentListing,
    SourceAdapter,
    SourceDocument,
    SourceError,
    SourceProject,
)
from app.storage.port import (
    CatalogStore,
    CatalogStoreProvider,
    ChangeTokenEntry,
    IntakeKind,
    IntakeStatus,
    PollStatus,
    RecordState,
    RecordWrite,
)

__all__ = [
    "DEFAULT_CONCURRENCY",
    "PollCounts",
    "PollOutcome",
    "PollProblem",
    "PollingService",
]

#: Default bound for concurrent listings and fetches per registration.
DEFAULT_CONCURRENCY = 8

_MAX_STORED_PROBLEMS = 100

_INTAKE_STATUS = {
    PollStatus.OK: IntakeStatus.OK,
    PollStatus.PARTIAL: IntakeStatus.PARTIAL,
    PollStatus.FAILED: IntakeStatus.FAILED,
}

logger = logging.getLogger(__name__)


type Clock = Callable[[], datetime.datetime]


def _utcnow() -> datetime.datetime:
    """
    Read the current time.

    :returns: Timezone-aware UTC now.
    """
    return datetime.datetime.now(datetime.UTC)


def _as_write(record: RecordWrite, change_token: str | None) -> RecordWrite:
    """
    Copy the writable fields of a stored row with a new change token.

    :param record: Stored row.
    :param change_token: New token.
    :returns: The row write.
    """
    values = {f.name: getattr(record, f.name) for f in fields(RecordWrite)}
    values["change_token"] = change_token
    return RecordWrite(**values)


class PollingService:
    """
    Polls source registrations into the catalog.

    :param provider: Storage provider.
    :param sources: All configured registrations, in configuration order.
    :param concurrency: Bound for concurrent listings and fetches.
    :param clock: Time source for ``last_attempt_at``.
    """

    def __init__(
        self,
        provider: CatalogStoreProvider,
        sources: Sequence[SourceRegistration],
        *,
        concurrency: int = DEFAULT_CONCURRENCY,
        clock: Clock = _utcnow,
    ) -> None:
        """
        Store the collaborators.

        :param provider: Storage provider.
        :param sources: Registrations in configuration order.
        :param concurrency: Bound for concurrent listings and fetches.
        :param clock: Time source.
        """
        self._provider = provider
        self._sources = tuple(sorted(sources, key=lambda s: s.position))
        self._concurrency = max(1, concurrency)
        self._clock = clock

    async def poll_all(self, *, trigger: JsonValue = None) -> list[PollOutcome]:
        """
        Poll every pollable registration, in configuration order.

        :param trigger: Who triggered the poll (stored, no secrets).
        :returns: One outcome per pollable registration.
        """
        return [
            await self._poll(source, trigger)
            for source in self._sources
            if source.pollable
        ]

    async def poll_source(
        self, source_id: str, *, trigger: JsonValue = None
    ) -> PollOutcome:
        """
        Poll one registration.

        :param source_id: Registration id.
        :param trigger: Who triggered the poll (stored, no secrets).
        :returns: The outcome; ``disabled`` (nothing ran) when the
            registration is invalid or has no ``poll`` intake.
        :raises NotFoundError: If no such registration is configured.
        """
        source = next((s for s in self._sources if s.id == source_id), None)
        if source is None:
            raise NotFoundError(f"no source registration {source_id!r}")
        if not source.pollable:
            reason = source.config_error or "poll intake is not enabled"
            problem = PollProblem(code="not_pollable", message=reason)
            return PollOutcome(
                source_id=source_id,
                status=PollStatus.DISABLED,
                run_id=None,
                counts=PollCounts(),
                problems=(problem,),
            )
        return await self._poll(source, trigger)

    async def _poll(
        self, source: SourceRegistration, trigger: JsonValue
    ) -> PollOutcome:
        """
        Poll one pollable registration and record the outcome.

        :param source: The registration.
        :param trigger: Who triggered the poll.
        :returns: The outcome.
        """
        attempted_at = self._clock()
        with self._provider.unit_of_work() as store:
            run = store.start_intake_run(
                source.id, IntakeKind.POLL, identity=trigger
            )
        plan = PollPlan()
        status = await self._run(source, plan)
        self._finish(source.id, run.id, status, plan, attempted_at)
        logger.info("poll %s finished: %s %s", source.id, status, plan.counts)
        return PollOutcome(
            source_id=source.id,
            status=status,
            run_id=run.id,
            counts=plan.counts,
            problems=tuple(plan.problems),
        )

    async def _run(
        self, source: SourceRegistration, plan: PollPlan
    ) -> PollStatus:
        """
        Collect and apply, turning failures into a ``failed`` status.

        :param source: The registration.
        :param plan: Plan to fill.
        :returns: The poll status.
        """
        try:
            await self._collect(source, plan)
            with self._provider.lock_registration(source.id) as store:
                self._apply(store, plan)
        except SourceError as exc:
            logger.warning("poll %s failed: %s", source.id, exc.message)
            plan.problems.append(
                PollProblem(code="source_error", message=exc.message)
            )
            return PollStatus.FAILED
        except Exception:
            logger.exception("poll %s failed unexpectedly", source.id)
            plan.problems.append(
                PollProblem(
                    code="internal_error",
                    message="unexpected error; see the server log",
                )
            )
            return PollStatus.FAILED
        return PollStatus.OK if plan.complete else PollStatus.PARTIAL

    def _finish(
        self,
        source_id: str,
        run_id: uuid.UUID,
        status: PollStatus,
        plan: PollPlan,
        attempted_at: datetime.datetime,
    ) -> None:
        """
        Finish the run and update the registration poll status.

        :param source_id: Registration id.
        :param run_id: Intake run id.
        :param status: Poll status.
        :param plan: Collected counters and problems.
        :param attempted_at: When the poll started.
        """
        problems: list[JsonValue] = [
            p.to_json() for p in plan.problems[:_MAX_STORED_PROBLEMS]
        ]
        with self._provider.unit_of_work() as store:
            store.finish_intake_run(
                run_id,
                _INTAKE_STATUS[status],
                counts=plan.counts.to_json(),
                errors=problems or None,
            )
            store.update_poll_status(
                source_id,
                status,
                attempted_at,
                None if status is PollStatus.OK else {"problems": problems},
            )

    def _read_stored(self, source: SourceRegistration) -> StoredState:
        """
        Read stored tokens and the locations owned by earlier sources.

        :param source: The registration being polled.
        :returns: The stored state.
        """
        earlier = [
            s.id
            for s in self._sources
            if s.position < source.position and s.pollable
        ]
        own: dict[str, dict[str, ChangeTokenEntry]] = {}
        with self._provider.unit_of_work() as store:
            for entry in store.list_change_tokens(source.id):
                own.setdefault(entry.project, {})[entry.path] = entry
            elsewhere = frozenset(
                (entry.project, entry.path)
                for other in earlier
                for entry in store.list_change_tokens(other)
            )
        return StoredState(own=own, owned_elsewhere=elsewhere)

    async def _collect(
        self, source: SourceRegistration, plan: PollPlan
    ) -> None:
        """
        List, filter, fetch and prepare (no transaction held).

        :param source: The registration.
        :param plan: Plan to fill.
        :raises SourceError: If no project listing can be produced.
        """
        assert source.binding is not None
        stored = self._read_stored(source)
        async with source.binding.open_adapter() as adapter:
            listing = await adapter.list_projects()
            plan.counts.projects = len(listing.projects)
            for message in listing.problems:
                plan.fail(
                    PollProblem(code="projects_incomplete", message=message)
                )
            plan.complete = plan.complete and listing.complete
            to_fetch = await self._list_all(
                adapter, listing.projects, stored, plan
            )
            await self._fetch_all(source, adapter, to_fetch, plan)
        if not listing.complete:
            plan.delete.clear()
            return
        listed = {project.path for project in listing.projects}
        for project, entries in stored.own.items():
            if project not in listed:
                plan.delete.extend(e.id for e in entries.values())

    async def _list_all(
        self,
        adapter: SourceAdapter,
        projects: Sequence[SourceProject],
        stored: StoredState,
        plan: PollPlan,
    ) -> list[SourceDocument]:
        """
        List every project's documents and decide what to fetch.

        :param adapter: Open adapter.
        :param projects: Listed projects.
        :param stored: Stored state.
        :param plan: Plan to fill.
        :returns: Documents to fetch.
        """

        def job(
            project: SourceProject,
        ) -> Callable[[], Awaitable[DocumentListing | PollProblem]]:
            tokens = {
                path: entry.change_token
                for path, entry in stored.own.get(project.path, {}).items()
            }
            return lambda: self._list_one(adapter, project, tokens)

        listings = await bounded(
            self._concurrency, [job(project) for project in projects]
        )
        to_fetch: list[SourceDocument] = []
        for project, listing in zip(projects, listings, strict=True):
            if isinstance(listing, PollProblem):
                plan.fail(listing)
                continue
            to_fetch += plan_project(project, listing, stored, plan)
        return to_fetch

    @staticmethod
    async def _list_one(
        adapter: SourceAdapter,
        project: SourceProject,
        tokens: dict[str, str | None],
    ) -> DocumentListing | PollProblem:
        """
        List one project, turning source errors into a problem.

        :param adapter: Open adapter.
        :param project: The project.
        :param tokens: Stored tokens by path.
        :returns: The listing, or the problem.
        """
        try:
            return await adapter.list_documents(project, tokens)
        except SourceError as exc:
            return PollProblem(
                code="listing_failed", message=exc.message, project=project.path
            )

    async def _fetch_all(
        self,
        source: SourceRegistration,
        adapter: SourceAdapter,
        documents: Sequence[SourceDocument],
        plan: PollPlan,
    ) -> None:
        """
        Fetch and prepare changed documents with bounded concurrency.

        :param source: The registration.
        :param adapter: Open adapter.
        :param documents: Documents to fetch.
        :param plan: Plan to fill.
        """

        def job(
            document: SourceDocument,
        ) -> Callable[[], Awaitable[PreparedDocument | PollProblem]]:
            return lambda: self._fetch_one(source.id, adapter, document)

        results = await bounded(
            self._concurrency, [job(document) for document in documents]
        )
        for result in results:
            if isinstance(result, PollProblem):
                plan.fail(result)
            else:
                plan.counts.fetched += 1
                plan.prepared.append(result)

    @staticmethod
    async def _fetch_one(
        source_id: str, adapter: SourceAdapter, document: SourceDocument
    ) -> PreparedDocument | PollProblem:
        """
        Fetch and prepare one document.

        :param source_id: Registration id.
        :param adapter: Open adapter.
        :param document: The document.
        :returns: The prepared document, or the problem.
        """
        try:
            fetched = await adapter.fetch(document)
        except SourceError as exc:
            return PollProblem(
                code="fetch_failed",
                message=exc.message,
                project=document.project.path,
                path=document.path,
            )
        return prepare_document(
            IncomingDocument(
                source_id=source_id,
                project=document.project.path,
                path=document.path,
                ref=document.project.ref,
                content=fetched.content,
                change_token=document.change_token,
                source_url=fetched.source_url,
                author=fetched.author,
            )
        )

    @staticmethod
    def _apply(store: CatalogStore, plan: PollPlan) -> None:
        """
        Write the plan inside the locked unit of work.

        :param store: Locked store.
        :param plan: The plan.
        """
        for prepared in plan.prepared:
            result = ingest_document(store, prepared, RecordState.PUBLISHED)
            if result.created:
                plan.counts.created += 1
            elif result.digest_changed:
                plan.counts.updated += 1
            else:
                plan.counts.same_content += 1
        for record_id, token in plan.refresh:
            stored = store.get_record(record_id)
            if stored is not None:
                store.upsert_published(_as_write(stored, token))
                plan.counts.tokens_refreshed += 1
        if plan.delete:
            plan.counts.deleted = store.delete_published(plan.delete)
