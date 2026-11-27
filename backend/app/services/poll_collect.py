"""
Collect phase of a poll: list, skip unchanged, fetch and prepare.

:class:`PollCollector` fills one registration's
:class:`~app.services.poll_plan.PollPlan` without holding a
transaction or lock: it reads the registration's stored state (its
published rows and not-indexed poll entries, by location), lists
projects and documents with the stored change tokens, fetches only
changed documents (bounded concurrency) and prepares them with the
shared ingest path (:func:`app.services.ingest.prepare_document`).
Applying the plan is :mod:`app.services.poll_apply`.

Public API: :class:`PollCollector`.
"""

from collections.abc import Awaitable, Callable, Sequence

from app.catalog_config import SourceRegistration
from app.domain.issues import IssueCode, error
from app.services.ingest import (
    IncomingDocument,
    PreparedDocument,
    prepare_document,
)
from app.services.poll_plan import (
    PollPlan,
    PollProblem,
    StoredState,
    bounded,
    plan_project,
    plan_vanished_project,
)
from app.sources.port import (
    DocumentListing,
    SourceAdapter,
    SourceDocument,
    SourceError,
    SourceProject,
)
from app.storage.port import (
    CatalogStoreProvider,
    ChangeTokenEntry,
    IntakeKind,
    NotIndexedEntry,
    NotIndexedKey,
    NotIndexedWrite,
)


class PollCollector:
    """
    Collects poll plans of registrations.

    :param provider: Storage provider (read-only use).
    :param concurrency: Bound for concurrent listings and fetches.
    """

    def __init__(
        self, provider: CatalogStoreProvider, concurrency: int
    ) -> None:
        """
        Store the collaborators.

        :param provider: Storage provider.
        :param concurrency: Bound for concurrent listings and fetches.
        """
        self._provider = provider
        self._concurrency = concurrency

    def _read_stored(self, source: SourceRegistration) -> StoredState:
        """
        Read the registration's published rows and not-indexed entries.

        :param source: The registration being polled.
        :returns: The stored state, by project and path.
        """
        own: dict[str, dict[str, ChangeTokenEntry]] = {}
        queued: dict[str, dict[str, list[NotIndexedEntry]]] = {}
        with self._provider.unit_of_work() as store:
            for entry in store.list_change_tokens(source.id):
                own.setdefault(entry.project, {})[entry.path] = entry
            for item in store.list_not_indexed(source.id, IntakeKind.POLL):
                key = item.key
                paths = queued.setdefault(key.project, {})
                paths.setdefault(key.path, []).append(item)
        return StoredState(own=own, queued=queued)

    async def collect(self, source: SourceRegistration, plan: PollPlan) -> None:
        """
        List, filter, fetch and prepare (no transaction held).

        :param source: The registration.
        :param plan: Plan to fill.
        :raises SourceError: If no project listing can be produced.
        """
        assert source.binding is not None
        plan.stored = self._read_stored(source)
        async with source.binding.open_adapter() as adapter:
            listing = await adapter.list_projects()
            plan.counts.projects = len(listing.projects)
            for message in listing.problems:
                plan.fail(
                    PollProblem(code="projects_incomplete", message=message)
                )
            plan.complete = plan.complete and listing.complete
            to_fetch = await self._list_all(adapter, listing.projects, plan)
            await self._fetch_all(source, adapter, to_fetch, plan)
        if not listing.complete:
            plan.forget_vanished()
            return
        listed = {project.path for project in listing.projects}
        stored = plan.stored
        for project in set(stored.own) | set(stored.queued):
            if project not in listed:
                plan_vanished_project(project, plan)

    async def _list_all(
        self,
        adapter: SourceAdapter,
        projects: Sequence[SourceProject],
        plan: PollPlan,
    ) -> list[SourceDocument]:
        """
        List every project's documents and decide what to fetch.

        :param adapter: Open adapter.
        :param projects: Listed projects.
        :param plan: Plan to fill.
        :returns: Documents to fetch.
        """
        stored = plan.stored

        def job(
            project: SourceProject,
        ) -> Callable[[], Awaitable[DocumentListing | PollProblem]]:
            paths = set(stored.own.get(project.path, {}))
            paths |= set(stored.queued.get(project.path, {}))
            tokens = {path: stored.token(project.path, path) for path in paths}
            return lambda: self._list_one(adapter, project, tokens)

        listings = await bounded(
            self._concurrency, [job(project) for project in projects]
        )
        to_fetch: list[SourceDocument] = []
        for project, listing in zip(projects, listings, strict=True):
            if isinstance(listing, PollProblem):
                plan.fail(listing)
                continue
            to_fetch += plan_project(project, listing, plan)
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

        A failed fetch makes the run partial and lists the document as
        not indexed (``fetch_failed``); its stored row, if any, is kept.

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
        for document, result in zip(documents, results, strict=True):
            if isinstance(result, PollProblem):
                plan.fail(result)
                plan.unreadable.append(_unreadable(source.id, document, result))
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


def _unreadable(
    source_id: str, document: SourceDocument, problem: PollProblem
) -> NotIndexedWrite:
    """
    Describe a document that could not be read for the not-indexed list.

    No change token is kept, so the next poll tries again.

    :param source_id: Registration id.
    :param document: The listed document.
    :param problem: The fetch problem.
    :returns: The entry.
    """
    return NotIndexedWrite(
        key=NotIndexedKey(
            source_id,
            document.project.path,
            document.path,
            document.project.ref,
        ),
        origin=IntakeKind.POLL,
        reasons=(error(IssueCode.FETCH_FAILED, problem.message),),
    )
