"""
Poll orchestration: list, skip unchanged, fetch, ingest, reconcile, log.

:class:`PollingService` polls registrations in configuration order.
One poll run (all pollable registrations for :meth:`~PollingService.
poll_all`, one for :meth:`~PollingService.poll_source`) has three
phases:

1. **Run log** -- per registration, an ``intake_run`` row is started in
   its own unit of work, so it survives a rollback of the ingest
   transaction.
2. **Collect** (no transaction held, no lock), registration by
   registration, with :class:`~app.services.poll_collect.PollCollector`
   -- open the adapter
   (:attr:`~app.sources.registry.SourceBinding.open_adapter`), list
   projects, list each project's documents with the stored change
   tokens (bounded concurrency), fetch only changed documents (bounded
   concurrency) and prepare them with the shared ingest path
   (:func:`app.services.ingest.prepare_document`).
3. **Apply** -- registration by registration, in configuration order,
   under :meth:`~app.storage.port.CatalogStoreProvider.
   lock_registration` (one transaction each):
   :func:`app.services.poll_apply.apply_plan` applies the UUID holder
   rule (moves included), rewrites change tokens of unchanged
   documents whose token moved, deletes published rows whose file is
   gone and maintains the not-indexed list. Every registration's
   findings are known to every apply of the run
   (:class:`~app.services.poll_apply.PollRun`), so a file that moved
   between registrations keeps its identity.

Finally, in a separate unit of work per registration, the run is
finished and the registration's ``last_attempt_at / last_success_at /
last_status / last_error`` are set.

Reconciliation rules: nothing is deleted unless the project listing was
complete; within a project, nothing is deleted unless its document
listing was complete. A vanished project (complete project listing)
loses its published rows. Candidates are never deleted by polling.
:meth:`~PollingService.poll_all` also clears the not-indexed poll
entries of registrations no longer configured.

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
from dataclasses import dataclass, field

from app.catalog_config import SourceRegistration
from app.domain.frontmatter import JsonValue
from app.errors import NotFoundError
from app.services.poll_apply import (
    PollRun,
    apply_plan,
    clear_removed_sources,
)
from app.services.poll_collect import PollCollector
from app.services.poll_plan import (
    PollCounts,
    PollOutcome,
    PollPlan,
    PollProblem,
)
from app.sources.port import (
    SourceError,
)
from app.storage.port import (
    CatalogStoreProvider,
    IntakeKind,
    IntakeStatus,
    PollStatus,
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


@dataclass(slots=True)
class _Job:
    """
    One registration's part of a poll run.

    :param source: The registration.
    :param run_id: Its intake run id.
    :param attempted_at: When its poll started.
    :param plan: What it collected.
    :param status: ``FAILED`` once something failed, else ``None``.
    """

    source: SourceRegistration
    run_id: uuid.UUID
    attempted_at: datetime.datetime
    plan: PollPlan = field(default_factory=PollPlan)
    status: PollStatus | None = None

    @property
    def final_status(self) -> PollStatus:
        """
        The poll status of the registration.

        :returns: ``FAILED``, else ``PARTIAL`` or ``OK``.
        """
        if self.status is not None:
            return self.status
        return PollStatus.OK if self.plan.complete else PollStatus.PARTIAL


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
        self._collector = PollCollector(provider, max(1, concurrency))
        self._sources = tuple(sorted(sources, key=lambda s: s.position))
        self._clock = clock

    async def poll_all(self, *, trigger: JsonValue = None) -> list[PollOutcome]:
        """
        Poll every pollable registration, in configuration order.

        :param trigger: Who triggered the poll (stored, no secrets).
        :returns: One outcome per pollable registration.
        """
        if self._sources:
            with self._provider.unit_of_work() as store:
                clear_removed_sources(store, (s.id for s in self._sources))
        sources = [source for source in self._sources if source.pollable]
        return await self._poll(sources, trigger)

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
        return (await self._poll([source], trigger))[0]

    async def _poll(
        self, sources: Sequence[SourceRegistration], trigger: JsonValue
    ) -> list[PollOutcome]:
        """
        Collect every registration, then apply them in order.

        :param sources: Pollable registrations, in configuration order.
        :param trigger: Who triggered the poll.
        :returns: One outcome per registration.
        """
        jobs: list[_Job] = []
        for source in sources:
            attempted_at = self._clock()
            with self._provider.unit_of_work() as store:
                run = store.start_intake_run(
                    source.id, IntakeKind.POLL, identity=trigger
                )
            job = _Job(source, run.id, attempted_at)
            await self._guarded(job, self._collector.collect(source, job.plan))
            jobs.append(job)
        run_state = PollRun(frozenset(s.id for s in self._sources))
        for job in jobs:
            if job.status is None:
                run_state.add(job.source.position, job.plan)
        outcomes = []
        for job in jobs:
            if job.status is None:
                await self._guarded(job, self._apply(job, run_state))
            outcomes.append(self._finish(job))
        return outcomes

    async def _guarded(self, job: _Job, step: Awaitable[None]) -> None:
        """
        Run one step of a registration, turning failures into ``failed``.

        :param job: The registration's job.
        :param step: The collect or apply coroutine.
        """
        source_id, plan = job.source.id, job.plan
        try:
            await step
        except SourceError as exc:
            logger.warning("poll %s failed: %s", source_id, exc.message)
            plan.problems.append(
                PollProblem(code="source_error", message=exc.message)
            )
            job.status = PollStatus.FAILED
        except Exception:
            logger.exception("poll %s failed unexpectedly", source_id)
            plan.problems.append(
                PollProblem(
                    code="internal_error",
                    message="unexpected error; see the server log",
                )
            )
            job.status = PollStatus.FAILED

    async def _apply(self, job: _Job, run_state: PollRun) -> None:
        """
        Apply one registration's plan under its lock.

        :param job: The registration's job.
        :param run_state: Knowledge of the whole run.
        """
        with self._provider.lock_registration(job.source.id) as store:
            apply_plan(store, job.plan, run_state, job.source.position)

    def _finish(self, job: _Job) -> PollOutcome:
        """
        Finish the run and update the registration poll status.

        :param job: The registration's job.
        :returns: The outcome.
        """
        status, plan = job.final_status, job.plan
        problems: list[JsonValue] = [
            p.to_json() for p in plan.problems[:_MAX_STORED_PROBLEMS]
        ]
        with self._provider.unit_of_work() as store:
            store.finish_intake_run(
                job.run_id,
                _INTAKE_STATUS[status],
                counts=plan.counts.to_json(),
                errors=problems or None,
            )
            store.update_poll_status(
                job.source.id,
                status,
                job.attempted_at,
                None if status is PollStatus.OK else {"problems": problems},
            )
        logger.info(
            "poll %s finished: %s %s", job.source.id, status, plan.counts
        )
        return PollOutcome(
            source_id=job.source.id,
            status=status,
            run_id=job.run_id,
            counts=plan.counts,
            problems=tuple(plan.problems),
        )
