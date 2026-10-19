"""
DB-neutral storage port of the catalog.

Services depend only on this module: the :class:`CatalogStoreProvider`
protocol hands out :class:`CatalogStore` instances bound to one unit of
work (one transaction). Everything crossing the port is a plain value
type from :mod:`app.storage.values` (re-exported here) or
:mod:`app.domain`; no ORM object leaks out.

Unit-of-work rules:

- :meth:`CatalogStoreProvider.unit_of_work` commits when the block exits
  normally and rolls back when it raises.
- :meth:`CatalogStoreProvider.lock_registration` is a unit of work that
  first takes an exclusive per-registration lock, held until the unit of
  work ends. All writes for one registration (poll, push) run inside it,
  which makes concurrent workers and replicas safe.
- Conflicts are reported with domain errors from :mod:`app.errors`
  (:class:`~app.errors.DecisionExistsError`,
  :class:`~app.errors.CandidateExistsError`,
  :class:`~app.errors.DeliveryExistsError`); they leave the unit of
  work usable.

Public API:

- every value type of :mod:`app.storage.values` (re-exported here)
- protocols :class:`CatalogStore`, :class:`CatalogStoreProvider`
"""

import datetime
import uuid
from collections.abc import Collection, Sequence
from contextlib import AbstractContextManager
from typing import Protocol

from app.domain.approval import Policy
from app.domain.frontmatter import JsonValue
from app.domain.relationships import RecordSummary
from app.domain.values import Identity
from app.storage.values import (
    MAX_PAGE_SIZE,
    ChangeTokenEntry,
    DecisionEvent,
    FacetEntry,
    IntakeKind,
    IntakeRun,
    IntakeStatus,
    JsonObject,
    NewDecision,
    PollStatus,
    RecordState,
    RecordWrite,
    Registration,
    RegistrationConfig,
    Revision,
    SearchFilters,
    SearchItem,
    SearchPage,
    StoredRecord,
    UpsertResult,
)

__all__ = [
    "CatalogStore",
    "CatalogStoreProvider",
    "ChangeTokenEntry",
    "DecisionEvent",
    "FacetEntry",
    "IntakeKind",
    "IntakeRun",
    "IntakeStatus",
    "JsonObject",
    "MAX_PAGE_SIZE",
    "NewDecision",
    "PollStatus",
    "RecordState",
    "RecordWrite",
    "Registration",
    "RegistrationConfig",
    "Revision",
    "SearchFilters",
    "SearchItem",
    "SearchPage",
    "StoredRecord",
    "UpsertResult",
]


class CatalogStore(Protocol):
    """Catalog operations inside one unit of work."""

    def sync_registrations(
        self, registrations: Sequence[RegistrationConfig]
    ) -> None:
        """
        Make stored registrations match the configuration.

        Listed registrations are inserted or updated; an invalid one gets
        status ``disabled``, and a re-enabled one leaves ``disabled`` for
        ``never``. Registrations missing from the list are disabled,
        never deleted.

        :param registrations: All configured registrations.
        """
        ...

    def get_registration(self, source_id: str) -> Registration | None:
        """
        Fetch one registration.

        :param source_id: Registration id.
        :returns: The registration, or ``None``.
        """
        ...

    def list_registrations(self) -> list[Registration]:
        """
        List all registrations, enabled or not, ordered by id.

        :returns: The registrations.
        """
        ...

    def update_poll_status(
        self,
        source_id: str,
        status: PollStatus,
        attempted_at: datetime.datetime,
        error: JsonValue = None,
    ) -> None:
        """
        Record the outcome of a poll.

        ``last_success_at`` is set to *attempted_at* only for
        :attr:`PollStatus.OK`.

        :param source_id: Registration id.
        :param status: Poll outcome.
        :param attempted_at: When the poll started.
        :param error: Error details, ``None`` on success.
        """
        ...

    def put_revision(self, digest: str, content: str) -> bool:
        """
        Store a snapshot unless it exists (snapshots are immutable).

        :param digest: Digest string.
        :param content: Canonical text content.
        :returns: ``True`` if it was newly stored.
        """
        ...

    def get_revision(self, digest: str) -> Revision | None:
        """
        Fetch a snapshot.

        :param digest: Digest string.
        :returns: The snapshot, or ``None``.
        """
        ...

    def upsert_published(self, record: RecordWrite) -> UpsertResult:
        """
        Insert or replace the published row at a location.

        Keyed by ``(source_id, project, path)``.

        :param record: Row content.
        :returns: The outcome.
        """
        ...

    def upsert_candidate(self, record: RecordWrite) -> UpsertResult:
        """
        Insert or replace a candidate row.

        Keyed by ``(source_id, project, record_key, ref)``.

        :param record: Row content.
        :returns: The outcome.
        """
        ...

    def create_candidate(self, record: RecordWrite) -> UpsertResult:
        """
        Insert a candidate row only if its key is free.

        :param record: Row content.
        :returns: The outcome (always ``created``).
        :raises app.errors.CandidateExistsError: If the candidate
            ``(source_id, project, record_key, ref)`` exists.
        """
        ...

    def get_record(self, record_id: uuid.UUID) -> StoredRecord | None:
        """
        Fetch one record row.

        :param record_id: Record id.
        :returns: The row, or ``None``.
        """
        ...

    def list_change_tokens(
        self, source_id: str, project: str | None = None
    ) -> list[ChangeTokenEntry]:
        """
        List the stored change state of published files.

        :param source_id: Registration id.
        :param project: Restrict to one project; ``None`` means all.
        :returns: Entries ordered by project and path.
        """
        ...

    def delete_published(self, record_ids: Collection[uuid.UUID]) -> int:
        """
        Delete published rows (reconciliation). Candidates are kept.

        :param record_ids: Ids to delete.
        :returns: Number of deleted rows.
        """
        ...

    def list_identity_siblings(self, identity: Identity) -> list[StoredRecord]:
        """
        List every row (published and candidates) of an identity.

        :param identity: Logical identity.
        :returns: Rows, published first, then by ref and path.
        """
        ...

    def list_relationship_summaries(
        self, kind: RecordState | None = RecordState.PUBLISHED
    ) -> list[RecordSummary]:
        """
        List relationship summaries, keyed by ``str(record id)``.

        :param kind: Restrict to one state; ``None`` means all rows.
        :returns: One summary per row.
        """
        ...

    def list_relationship_candidates(
        self, self_uuid: uuid.UUID, link_targets: Collection[uuid.UUID]
    ) -> list[RecordSummary]:
        """
        List published rows that can affect one record's relationships.

        A bounded alternative to ``list_relationship_summaries(
        RecordState.PUBLISHED)`` for a single detail request: see
        :func:`app.storage.postgres.records.list_relationship_candidates`
        for exactly which rows this returns and why the result is
        equivalent for that one record's
        :meth:`~app.domain.relationships.RelationshipIndex.view`.

        :param self_uuid: The viewed record's own UUID.
        :param link_targets: UUIDs the viewed record's own ``updates``,
            ``obsoletes`` and ``corrects`` links target.
        :returns: The matching published rows.
        """
        ...

    def list_facets(self) -> list[FacetEntry]:
        """
        Count rows per ``(source_id, project)`` pair, for filter UIs.

        Counts include both published and candidate rows.

        :returns: One entry per non-empty ``(source_id, project)``
            pair, ordered by source id then project.
        """
        ...

    def search(
        self,
        query: str | None,
        filters: SearchFilters,
        page: int,
        page_size: int,
        *,
        policy: Policy | None,
    ) -> SearchPage:
        """
        Full-text search with filters and bounded pagination.

        Hits are ranked by relevance when *query* is given, else ordered
        by title.

        :param query: Free text (titles, bodies, UUIDs, paths); blank or
            ``None`` matches everything.
        :param filters: Filters.
        :param page: 1-based page number.
        :param page_size: Page size, 1 to :data:`MAX_PAGE_SIZE`.
        :param policy: The configured policy (``None`` when missing or
            invalid), used for approval states.
        :returns: The page.
        :raises ValueError: If *page* or *page_size* is out of bounds.
        """
        ...

    def append_decision(self, decision: NewDecision) -> DecisionEvent:
        """
        Append a decision event; the server sets id and timestamp.

        :param decision: The decision.
        :returns: The stored event.
        :raises app.errors.DecisionExistsError: If the identity already
            has a decision for the digest.
        """
        ...

    def list_decisions(self, identity: Identity) -> list[DecisionEvent]:
        """
        List all decision events of an identity, any digest.

        :param identity: Logical identity.
        :returns: Events, oldest first.
        """
        ...

    def start_intake_run(
        self,
        source_id: str,
        kind: IntakeKind,
        *,
        identity: JsonValue = None,
        delivery_id: str | None = None,
    ) -> IntakeRun:
        """
        Record the start of an intake run.

        :param source_id: Registration id as requested.
        :param kind: Poll or push.
        :param identity: Who triggered the run (no secrets).
        :param delivery_id: Push delivery id, if any.
        :returns: The running run.
        :raises app.errors.DeliveryExistsError: If *delivery_id* was
            already used for *source_id*.
        """
        ...

    def finish_intake_run(
        self,
        run_id: uuid.UUID,
        status: IntakeStatus,
        *,
        counts: JsonValue = None,
        errors: JsonValue = None,
    ) -> IntakeRun:
        """
        Record the end of an intake run.

        :param run_id: Run id.
        :param status: Final status.
        :param counts: Outcome counters.
        :param errors: Error details.
        :returns: The finished run.
        :raises LookupError: If the run does not exist.
        """
        ...

    def find_intake_run(
        self, source_id: str, delivery_id: str
    ) -> IntakeRun | None:
        """
        Find the run of an earlier push delivery.

        :param source_id: Registration id.
        :param delivery_id: Push delivery id.
        :returns: The run, or ``None``.
        """
        ...


class CatalogStoreProvider(Protocol):
    """Hands out :class:`CatalogStore` instances per unit of work."""

    def unit_of_work(self) -> AbstractContextManager[CatalogStore]:
        """
        Open a unit of work (one transaction).

        :returns: A context manager yielding the store; it commits on
            normal exit and rolls back on error.
        """
        ...

    def lock_registration(
        self, source_id: str
    ) -> AbstractContextManager[CatalogStore]:
        """
        Open a unit of work holding the registration's exclusive lock.

        The lock is taken before the store is yielded and released when
        the unit of work commits or rolls back. Other units of work for
        the same registration wait; other registrations are unaffected.

        :param source_id: Registration id.
        :returns: A context manager yielding the store.
        """
        ...
