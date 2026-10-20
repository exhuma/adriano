"""
PostgreSQL implementation of the storage port.

:class:`PostgresStoreProvider` is constructed at the composition root
with an engine; it opens one :class:`~sqlalchemy.orm.Session` per unit
of work and yields a :class:`PostgresCatalogStore` bound to it. The
store delegates each operation to a concern module
(:mod:`~app.storage.postgres.registrations`,
:mod:`~app.storage.postgres.records`,
:mod:`~app.storage.postgres.errata`,
:mod:`~app.storage.postgres.search`,
:mod:`~app.storage.postgres.events`). All SQL uses bound parameters.

Registration locks use ``pg_advisory_xact_lock(namespace,
hashtext(source_id))``: the lock lives exactly as long as the
transaction, so it is released by commit or rollback and works across
processes and replicas.

Public API: :data:`LOCK_NAMESPACE`, :class:`PostgresCatalogStore`,
:class:`PostgresStoreProvider`.
"""

import datetime
import uuid
from collections.abc import Collection, Iterator, Sequence
from contextlib import contextmanager

from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.domain.approval import Policy
from app.domain.frontmatter import JsonValue
from app.domain.relationships import RecordSummary
from app.domain.values import Identity
from app.storage.port import (
    ChangeTokenEntry,
    DecisionEvent,
    ErratumRow,
    FacetEntry,
    IntakeKind,
    IntakeRun,
    IntakeStatus,
    LinkTarget,
    NewDecision,
    PollStatus,
    RecordState,
    RecordWrite,
    Registration,
    RegistrationConfig,
    Revision,
    SearchFilters,
    SearchPage,
    SearchSort,
    StoredRecord,
    UpsertResult,
)
from app.storage.postgres import errata, events, records, search
from app.storage.postgres import registrations as registration_sql

#: First key of the two-key advisory lock; keeps registration locks
#: apart from any other advisory lock users of the database.
LOCK_NAMESPACE = 0x4144_5201


class PostgresCatalogStore:
    """
    :class:`~app.storage.port.CatalogStore` bound to one session.

    Instances are created by :class:`PostgresStoreProvider` only; see
    :class:`~app.storage.port.CatalogStore` for the operation contracts.

    :param session: The unit-of-work session (inside a transaction).
    """

    def __init__(self, session: Session) -> None:
        """:param session: The unit-of-work session."""
        self._session = session

    def acquire_registration_lock(self, source_id: str) -> None:
        """
        Take the registration's transaction-scoped advisory lock.

        :param source_id: Registration id.
        """
        self._session.execute(
            select(
                func.pg_advisory_xact_lock(
                    LOCK_NAMESPACE, func.hashtext(source_id)
                )
            )
        )

    def sync_registrations(
        self, registrations: Sequence[RegistrationConfig]
    ) -> None:
        """See :meth:`app.storage.port.CatalogStore.sync_registrations`."""
        registration_sql.sync_registrations(self._session, registrations)

    def get_registration(self, source_id: str) -> Registration | None:
        """See :meth:`app.storage.port.CatalogStore.get_registration`."""
        return registration_sql.get_registration(self._session, source_id)

    def list_registrations(self) -> list[Registration]:
        """See :meth:`app.storage.port.CatalogStore.list_registrations`."""
        return registration_sql.list_registrations(self._session)

    def update_poll_status(
        self,
        source_id: str,
        status: PollStatus,
        attempted_at: datetime.datetime,
        error: JsonValue = None,
    ) -> None:
        """See :meth:`app.storage.port.CatalogStore.update_poll_status`."""
        registration_sql.update_poll_status(
            self._session, source_id, status, attempted_at, error
        )

    def put_revision(self, digest: str, content: str) -> bool:
        """See :meth:`app.storage.port.CatalogStore.put_revision`."""
        return records.put_revision(self._session, digest, content)

    def get_revision(self, digest: str) -> Revision | None:
        """See :meth:`app.storage.port.CatalogStore.get_revision`."""
        return records.get_revision(self._session, digest)

    def upsert_published(self, record: RecordWrite) -> UpsertResult:
        """See :meth:`app.storage.port.CatalogStore.upsert_published`."""
        return records.upsert_record(
            self._session, record, RecordState.PUBLISHED
        )

    def upsert_candidate(self, record: RecordWrite) -> UpsertResult:
        """See :meth:`app.storage.port.CatalogStore.upsert_candidate`."""
        return records.upsert_record(
            self._session, record, RecordState.CANDIDATE
        )

    def create_candidate(self, record: RecordWrite) -> UpsertResult:
        """See :meth:`app.storage.port.CatalogStore.create_candidate`."""
        return records.create_candidate(self._session, record)

    def get_record(self, record_id: uuid.UUID) -> StoredRecord | None:
        """See :meth:`app.storage.port.CatalogStore.get_record`."""
        return records.get_record(self._session, record_id)

    def list_change_tokens(
        self, source_id: str, project: str | None = None
    ) -> list[ChangeTokenEntry]:
        """See :meth:`app.storage.port.CatalogStore.list_change_tokens`."""
        return records.list_change_tokens(self._session, source_id, project)

    def delete_published(self, record_ids: Collection[uuid.UUID]) -> int:
        """See :meth:`app.storage.port.CatalogStore.delete_published`."""
        return records.delete_published(self._session, record_ids)

    def list_identity_siblings(self, identity: Identity) -> list[StoredRecord]:
        """See :meth:`app.storage.port.CatalogStore.list_identity_siblings`."""
        return records.list_identity_siblings(self._session, identity)

    def list_relationship_summaries(
        self, kind: RecordState | None = RecordState.PUBLISHED
    ) -> list[RecordSummary]:
        """See :meth:`.CatalogStore.list_relationship_summaries`."""
        return records.list_relationship_summaries(self._session, kind)

    def list_relationship_candidates(
        self, self_uuid: uuid.UUID, link_targets: Collection[uuid.UUID]
    ) -> list[RecordSummary]:
        """See :meth:`.CatalogStore.list_relationship_candidates`."""
        return records.list_relationship_candidates(
            self._session, self_uuid, link_targets
        )

    def list_errata_for(self, target_uuid: uuid.UUID) -> list[ErratumRow]:
        """See :meth:`app.storage.port.CatalogStore.list_errata_for`."""
        return errata.list_errata_for(self._session, target_uuid)

    def list_published_by_uuid(
        self, uuids: Collection[uuid.UUID]
    ) -> list[LinkTarget]:
        """See :meth:`.CatalogStore.list_published_by_uuid`."""
        return errata.list_published_by_uuid(self._session, uuids)

    def list_facets(self) -> list[FacetEntry]:
        """See :meth:`app.storage.port.CatalogStore.list_facets`."""
        return records.list_facets(self._session)

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
        """See :meth:`app.storage.port.CatalogStore.search`."""
        return search.search(
            self._session, query, filters, page, page_size, policy, sort
        )

    def append_decision(self, decision: NewDecision) -> DecisionEvent:
        """See :meth:`app.storage.port.CatalogStore.append_decision`."""
        return events.append_decision(self._session, decision)

    def list_decisions(self, identity: Identity) -> list[DecisionEvent]:
        """See :meth:`app.storage.port.CatalogStore.list_decisions`."""
        return events.list_decisions(self._session, identity)

    def list_decisions_for(
        self, identities: Collection[Identity]
    ) -> list[DecisionEvent]:
        """See :meth:`.CatalogStore.list_decisions_for`."""
        return events.list_decisions_for(self._session, identities)

    def start_intake_run(
        self,
        source_id: str,
        kind: IntakeKind,
        *,
        identity: JsonValue = None,
        delivery_id: str | None = None,
    ) -> IntakeRun:
        """See :meth:`app.storage.port.CatalogStore.start_intake_run`."""
        return events.start_intake_run(
            self._session, source_id, kind, identity, delivery_id
        )

    def finish_intake_run(
        self,
        run_id: uuid.UUID,
        status: IntakeStatus,
        *,
        counts: JsonValue = None,
        errors: JsonValue = None,
    ) -> IntakeRun:
        """See :meth:`app.storage.port.CatalogStore.finish_intake_run`."""
        return events.finish_intake_run(
            self._session, run_id, status, counts, errors
        )

    def find_intake_run(
        self, source_id: str, delivery_id: str
    ) -> IntakeRun | None:
        """See :meth:`app.storage.port.CatalogStore.find_intake_run`."""
        return events.find_intake_run(self._session, source_id, delivery_id)


class PostgresStoreProvider:
    """
    :class:`~app.storage.port.CatalogStoreProvider` over an engine.

    :param engine: SQLAlchemy engine for the catalog database.
    """

    def __init__(self, engine: Engine) -> None:
        """:param engine: SQLAlchemy engine for the catalog database."""
        self._sessions = sessionmaker(
            bind=engine, autoflush=False, expire_on_commit=False
        )

    @contextmanager
    def unit_of_work(self) -> Iterator[PostgresCatalogStore]:
        """
        Open one session and transaction.

        :returns: A context manager yielding the store; commits on normal
            exit, rolls back on error.
        """
        with self._sessions() as session, session.begin():
            yield PostgresCatalogStore(session)

    @contextmanager
    def lock_registration(
        self, source_id: str
    ) -> Iterator[PostgresCatalogStore]:
        """
        Open a unit of work holding the registration's advisory lock.

        :param source_id: Registration id.
        :returns: A context manager yielding the store.
        """
        with self.unit_of_work() as store:
            store.acquire_registration_lock(source_id)
            yield store
