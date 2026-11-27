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
  which makes concurrent workers and replicas safe. Polls also take
  :meth:`CatalogStore.lock_published`, because a UUID is unique across
  registrations.
- Conflicts are reported with domain errors from :mod:`app.errors`
  (:class:`~app.errors.DecisionExistsError`,
  :class:`~app.errors.CandidateExistsError`,
  :class:`~app.errors.DeliveryExistsError`); they leave the unit of
  work usable.

Public API:

- every value type of :mod:`app.storage.values`,
  :mod:`app.storage.errata_values` and :mod:`app.storage.queue_values`
  (re-exported here)
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
from app.storage.errata_values import StoredErratum
from app.storage.queue_values import (
    NotIndexedEntry,
    NotIndexedFilters,
    NotIndexedKey,
    NotIndexedPage,
    NotIndexedWrite,
)
from app.storage.values import (
    MAX_PAGE_SIZE,
    ChangeTokenEntry,
    DecisionEvent,
    ErratumRow,
    FacetEntry,
    IntakeKind,
    IntakeRun,
    IntakeStatus,
    JsonObject,
    Location,
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
    SearchSort,
    StoredRecord,
    UpsertResult,
)

__all__ = [
    "CatalogStore",
    "CatalogStoreProvider",
    "ChangeTokenEntry",
    "DecisionEvent",
    "ErratumRow",
    "FacetEntry",
    "IntakeKind",
    "IntakeRun",
    "IntakeStatus",
    "JsonObject",
    "Location",
    "MAX_PAGE_SIZE",
    "NewDecision",
    "NotIndexedEntry",
    "NotIndexedFilters",
    "NotIndexedKey",
    "NotIndexedPage",
    "NotIndexedWrite",
    "PollStatus",
    "RecordState",
    "RecordWrite",
    "Registration",
    "RegistrationConfig",
    "Revision",
    "SearchFilters",
    "SearchItem",
    "SearchPage",
    "SearchSort",
    "StoredErratum",
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

    def lock_published(self) -> None:
        """
        Take the catalog-wide lock for writing published rows.

        Held until the unit of work ends. A UUID is unique across all
        registrations, so a poll that decides who holds a UUID (and
        moves rows between registrations) must not interleave with
        another registration's poll; candidates and pushes do not need
        it.
        """
        ...

    def upsert_published(self, record: RecordWrite) -> UpsertResult:
        """
        Insert or replace the published row of an ADR.

        Keyed by ``adr_uuid`` alone: an existing row is updated in place,
        including its location (a move keeps ``first_seen_at``, digest
        history and approvals). Deciding *whether* a file may hold the
        UUID is the caller's job (the holder rule of
        :mod:`app.services.poll_apply`).

        :param record: Row content.
        :returns: The outcome.
        """
        ...

    def upsert_candidate(self, record: RecordWrite) -> UpsertResult:
        """
        Insert or replace a candidate row.

        Keyed by ``(adr_uuid, ref)``.

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
            ``(adr_uuid, ref)`` exists.
        """
        ...

    def get_published(self, adr_uuid: uuid.UUID) -> StoredRecord | None:
        """
        Fetch the published row of an ADR.

        :param adr_uuid: The ADR's UUID.
        :returns: The row, or ``None``.
        """
        ...

    def get_candidate(
        self, adr_uuid: uuid.UUID, ref: str
    ) -> StoredRecord | None:
        """
        Fetch one candidate row.

        :param adr_uuid: The ADR's UUID.
        :param ref: The candidate's ref.
        :returns: The row, or ``None``.
        """
        ...

    def list_records(self, adr_uuid: uuid.UUID) -> list[StoredRecord]:
        """
        List every row (published and candidates) of an ADR.

        :param adr_uuid: The ADR's UUID.
        :returns: Rows, published first, then candidates by ref.
        """
        ...

    def list_change_tokens(
        self, source_id: str, project: str | None = None
    ) -> list[ChangeTokenEntry]:
        """
        List the published files of a registration with their tokens.

        Listings know paths before content is fetched, so change
        detection looks up by location; the row it maps to is keyed by
        the UUID in :attr:`ChangeTokenEntry.adr_uuid`.

        :param source_id: Registration id.
        :param project: Restrict to one project; ``None`` means all.
        :returns: Entries ordered by project and path.
        """
        ...

    def list_published_entries(
        self, uuids: Collection[uuid.UUID]
    ) -> list[ChangeTokenEntry]:
        """
        List where the published rows of some UUIDs live (any source).

        :param uuids: ADR UUIDs.
        :returns: One entry per UUID that has a published row.
        """
        ...

    def set_change_token(
        self, entry: ChangeTokenEntry, change_token: str | None
    ) -> bool:
        """
        Rewrite the change token of an unchanged published file.

        Only touches the row if it still lives at the entry's location.

        :param entry: The stored entry (UUID and location).
        :param change_token: The new token.
        :returns: ``True`` if a row was updated.
        """
        ...

    def delete_published(self, entries: Collection[ChangeTokenEntry]) -> int:
        """
        Delete published rows (reconciliation). Candidates are kept.

        A row is deleted only if it still lives at the entry's location,
        so a row another registration moved in the meantime survives.

        :param entries: UUIDs with their expected locations.
        :returns: Number of deleted rows.
        """
        ...

    def list_relationship_candidates(
        self, self_uuid: uuid.UUID, link_targets: Collection[uuid.UUID]
    ) -> list[RecordSummary]:
        """
        List published rows that can affect one record's relationships.

        See
        :func:`app.storage.postgres.records.list_relationship_candidates`
        for exactly which rows this returns.

        :param self_uuid: The viewed record's own UUID.
        :param link_targets: UUIDs the viewed record's own ``updates``,
            ``obsoletes`` and ``corrects`` links target.
        :returns: One summary per matching published ADR.
        """
        ...

    def list_errata_for(self, target_uuid: uuid.UUID) -> list[ErratumRow]:
        """
        List the erratum rows whose ``corrects`` link is *target_uuid*.

        Includes published rows and candidates (proposed errata), from
        every registration and project. Decisions are never returned.

        :param target_uuid: UUID of the corrected decision.
        :returns: Published rows first, then by source, project, path,
            ref and UUID.
        """
        ...

    def published_titles(
        self, uuids: Collection[uuid.UUID]
    ) -> dict[uuid.UUID, str]:
        """
        Look up the titles of the published rows of some UUIDs.

        One query for a whole set (link targets of a detail page,
        erratum targets of a search page).

        :param uuids: ADR UUIDs.
        :returns: Title by UUID, for UUIDs with a published row.
        """
        ...

    def list_facets(self) -> list[FacetEntry]:
        """
        Count decision ADRs per ``(source_id, project)``, for filter UIs.

        Counts distinct UUIDs (an ADR with candidates counts once), from
        published and candidate rows, but not errata (matching the
        default ``record_type=decision`` search).

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
        sort: SearchSort = SearchSort.RELEVANCE,
    ) -> SearchPage:
        """
        Full-text search with filters and bounded pagination.

        Hits are ordered by *sort* (see :class:`SearchSort`); the
        default ranks by relevance when *query* is given, else orders
        by title.

        :param query: Free text (titles, bodies, UUIDs, paths); blank or
            ``None`` matches everything.
        :param filters: Filters.
        :param page: 1-based page number.
        :param page_size: Page size, 1 to :data:`MAX_PAGE_SIZE`.
        :param policy: The configured policy (``None`` when missing or
            invalid), used for approval states.
        :param sort: Result order; ``relevance`` without a query
            falls back to ``title``.
        :returns: The page.
        :raises ValueError: If *page* or *page_size* is out of bounds.
        """
        ...

    def append_decision(self, decision: NewDecision) -> DecisionEvent:
        """
        Append a decision event; the server sets id and timestamp.

        :param decision: The decision.
        :returns: The stored event.
        :raises app.errors.DecisionExistsError: If the ADR already has
            a decision for the digest.
        """
        ...

    def list_decisions(self, adr_uuid: uuid.UUID) -> list[DecisionEvent]:
        """
        List all decision events of an ADR, any digest.

        :param adr_uuid: The ADR's UUID.
        :returns: Events, oldest first.
        """
        ...

    def list_decisions_for(
        self, uuids: Collection[uuid.UUID]
    ) -> list[DecisionEvent]:
        """
        List all decision events of several ADRs in one query.

        :param uuids: ADR UUIDs.
        :returns: Events of all of them, oldest first; group them by
            :attr:`~app.storage.port.DecisionEvent.adr_uuid`.
        """
        ...

    def put_not_indexed(self, entry: NotIndexedWrite) -> None:
        """
        Insert or replace a not-indexed entry at its key.

        ``first_seen_at`` is kept for an existing key; ``last_seen_at``
        moves to now.

        :param entry: The entry.
        """
        ...

    def list_not_indexed(
        self, source_id: str | None = None, origin: IntakeKind | None = None
    ) -> list[NotIndexedEntry]:
        """
        List not-indexed entries.

        :param source_id: Restrict to one registration; ``None`` = all.
        :param origin: Restrict to one intake; ``None`` = both.
        :returns: Entries ordered by key.
        """
        ...

    def page_not_indexed(
        self, filters: NotIndexedFilters, page: int, page_size: int
    ) -> NotIndexedPage:
        """
        List one page of not-indexed entries, newest first.

        :param filters: Filters.
        :param page: 1-based page number.
        :param page_size: Page size, 1 to :data:`MAX_PAGE_SIZE`.
        :returns: The page, ordered by ``last_seen_at`` descending, then
            by key.
        :raises ValueError: If *page* or *page_size* is out of bounds.
        """
        ...

    def get_not_indexed(self, key: NotIndexedKey) -> NotIndexedEntry | None:
        """
        Fetch one not-indexed entry.

        :param key: Its location.
        :returns: The entry, or ``None``.
        """
        ...

    def count_not_indexed(self) -> dict[str, int]:
        """
        Count not-indexed entries per registration.

        :returns: Count by registration id; registrations without
            entries are absent.
        """
        ...

    def clear_pushed_at(self, locations: Collection[Location]) -> int:
        """
        Delete every push entry at the given file locations.

        A poll that indexes a document at a file location settles
        whatever a push was refused there, whatever its ref or reason:
        an author who fixed the document and merged it no longer has a
        problem to resolve.

        :param locations: File locations a poll just indexed.
        :returns: Number of deleted entries; no query for no locations.
        """
        ...

    def delete_not_indexed(self, keys: Collection[NotIndexedKey]) -> int:
        """
        Delete not-indexed entries (automatic clearing only).

        :param keys: Keys to delete; unknown keys are ignored.
        :returns: Number of deleted entries.
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
