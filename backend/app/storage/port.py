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
  :mod:`app.storage.search_values`, :mod:`app.storage.approval_values`,
  :mod:`app.storage.intake_values`, :mod:`app.storage.errata_values`
  and :mod:`app.storage.queue_values` (re-exported here)
- protocols :class:`CatalogStore`, :class:`CatalogStoreProvider`

:class:`CatalogStore` is composed from one protocol per concern:
:mod:`app.storage.port_sources` (registrations, intake runs),
:mod:`app.storage.port_records` (revisions, records),
:mod:`app.storage.port_search`, :mod:`app.storage.port_approval` and
:mod:`app.storage.port_queue` (not-indexed list).
"""

from contextlib import AbstractContextManager
from typing import Protocol

from app.storage.approval_values import DecisionEvent, NewDecision
from app.storage.errata_values import StoredErratum
from app.storage.intake_values import IntakeRun
from app.storage.port_approval import ApprovalStore
from app.storage.port_queue import NotIndexedStore
from app.storage.port_records import RecordStore
from app.storage.port_search import SearchStore
from app.storage.port_sources import SourceStore
from app.storage.queue_values import (
    NotIndexedEntry,
    NotIndexedFilters,
    NotIndexedKey,
    NotIndexedPage,
    NotIndexedWrite,
)
from app.storage.search_values import (
    FacetEntry,
    SearchFilters,
    SearchItem,
    SearchPage,
)
from app.storage.values import (
    MAX_PAGE_SIZE,
    ChangeTokenEntry,
    ErratumRow,
    IntakeKind,
    IntakeStatus,
    JsonObject,
    Location,
    PollStatus,
    RecordState,
    RecordWrite,
    Registration,
    RegistrationConfig,
    Revision,
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


class CatalogStore(
    SourceStore,
    RecordStore,
    SearchStore,
    ApprovalStore,
    NotIndexedStore,
    Protocol,
):
    """Catalog operations inside one unit of work."""


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
