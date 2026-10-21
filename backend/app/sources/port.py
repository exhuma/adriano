"""
Provider-neutral port between polling and the source adapters.

A :class:`SourceAdapter` reads the published ref of one source
registration. Everything crossing the port is provider-neutral: project
id/path, file path, change token, content bytes, source URL, author and
ref. Pagination, API formats, scopes and credentials stay inside the
adapter module.

Polling drives an adapter in three steps:

1. :meth:`SourceAdapter.list_projects` -- the in-scope projects with the
   resolved published ref of each. ``complete=False`` means the listing
   may miss projects; polling then deletes nothing.
2. :meth:`SourceAdapter.list_documents` -- the ADR files of one project
   under the registration ``path`` with their change tokens. The adapter
   receives the stored tokens and marks each document ``changed`` or
   not; polling fetches only changed documents. ``complete=False`` means
   files may be missing; polling then deletes nothing in that project.
3. :meth:`SourceAdapter.fetch` -- the exact bytes of one changed file.

Change tokens are opaque strings chosen by the adapter (for example
``mtime_ns:size`` or a blob id). A document reported with
``changed=False`` but a token different from the stored one keeps its
content; polling only rewrites the stored token. Adapters may use that
to carry project-level state (such as a branch head) in the token.

Adapters raise :class:`SourceError` subclasses for source problems;
messages must be actionable and must never contain secrets.

Public API: :class:`SourceProject`, :class:`ProjectListing`,
:class:`SourceDocument`, :class:`DocumentListing`,
:class:`FetchedDocument`, :class:`SourceAdapter`, :class:`SourceError`,
:class:`ConfigErrorCode`, :class:`SourceConfigError`,
:class:`SourceUnavailableError`,
:class:`SourceAccessError`, :class:`SourceNotFoundError`.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from app.errors import AdrianoError


class SourceError(AdrianoError):
    """A source could not be read; prior content must be preserved."""


class ConfigErrorCode(StrEnum):
    """
    Stable, machine-readable reason why a registration is disabled.

    The readable ``config_error`` text stays the detailed explanation;
    the code lets the UI show plain-language copy.

    - ``invalid_settings`` -- a field of the entry, its type-specific
      options or its ``scope`` failed validation (missing, wrong type,
      bad URL, unknown key, ...).
    - ``unknown_type`` -- the ``type`` is not a known source type.
    - ``type_unavailable`` -- the type is known but has no adapter in
      this build.
    - ``invalid_published_ref`` -- ``published_ref`` is not usable for
      the type.
    - ``token_env_missing`` -- the env var named by ``token_env`` is
      not set.
    - ``removed_from_config`` -- the registration is stored but no
      longer in ``catalog.yaml``.
    - ``other`` -- any other configuration error.
    """

    INVALID_SETTINGS = "invalid_settings"
    UNKNOWN_TYPE = "unknown_type"
    TYPE_UNAVAILABLE = "type_unavailable"
    INVALID_PUBLISHED_REF = "invalid_published_ref"
    TOKEN_ENV_MISSING = "token_env_missing"
    REMOVED_FROM_CONFIG = "removed_from_config"
    OTHER = "other"


class SourceConfigError(SourceError):
    """
    Type-specific registration settings are invalid.

    :param message: Readable, secret-free description.
    :param config_code: Stable reason code (:class:`ConfigErrorCode`).
    """

    def __init__(
        self,
        message: str,
        *,
        config_code: ConfigErrorCode = ConfigErrorCode.OTHER,
    ) -> None:
        """
        Store the message and its stable reason code.

        :param message: Readable, secret-free description.
        :param config_code: Stable reason code.
        """
        super().__init__(message, code=config_code.value)
        self.config_code = config_code


class SourceUnavailableError(SourceError):
    """The source is temporarily unreachable (network, timeout, 5xx)."""


class SourceAccessError(SourceError):
    """The source refused access (bad or insufficient credentials)."""


class SourceNotFoundError(SourceError):
    """A configured root, project or path does not exist at the source."""


@dataclass(frozen=True, slots=True, kw_only=True)
class SourceProject:
    """
    One in-scope project (repository or directory) of a registration.

    :param id: Adapter-internal stable id (opaque to polling).
    :param path: Project path stored as the record ``project``.
    :param ref: Resolved published ref polled for this project.
    """

    id: str
    path: str
    ref: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ProjectListing:
    """
    The in-scope projects of a registration.

    :param projects: Projects found, without duplicates.
    :param complete: ``True`` only if no in-scope project can be
        missing (all pages read, no project skipped by an error).
    :param problems: Actionable descriptions of skipped parts.
    """

    projects: tuple[SourceProject, ...]
    complete: bool = True
    problems: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class SourceDocument:
    """
    One ADR file found in a project listing.

    :param project: Owning project.
    :param path: POSIX file path inside the project (including the
        registration ``path`` prefix).
    :param change_token: Opaque token that changes when the content may
        have changed; ``None`` if the source offers none.
    :param changed: Whether the content may differ from the content that
        produced the stored token; polling fetches only these.
    """

    project: SourceProject
    path: str
    change_token: str | None
    changed: bool = True


@dataclass(frozen=True, slots=True, kw_only=True)
class DocumentListing:
    """
    The ADR files of one project.

    :param documents: Documents found, without duplicate paths.
    :param complete: ``True`` only if no file under the registration
        path can be missing.
    :param problems: Actionable descriptions of skipped parts.
    """

    documents: tuple[SourceDocument, ...]
    complete: bool = True
    problems: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class FetchedDocument:
    """
    The content of one document.

    :param content: The exact bytes at the source.
    :param source_url: Link (or display path) to the file at the source.
    :param author: Commit author email, if cheaply known.
    """

    content: bytes
    source_url: str | None = None
    author: str | None = None


class SourceAdapter(Protocol):
    """Reads the published ref of one source registration."""

    async def list_projects(self) -> ProjectListing:
        """
        List the in-scope projects.

        :returns: The listing.
        :raises SourceError: If no listing can be produced at all.
        """
        ...

    async def list_documents(
        self,
        project: SourceProject,
        previous_tokens: Mapping[str, str | None],
    ) -> DocumentListing:
        """
        List the ADR files of one project.

        :param project: A project from :meth:`list_projects`.
        :param previous_tokens: Stored change token per file path of
            this project (empty on the first poll).
        :returns: The listing.
        :raises SourceError: If the project cannot be listed.
        """
        ...

    async def fetch(self, document: SourceDocument) -> FetchedDocument:
        """
        Read one document.

        :param document: A document from :meth:`list_documents`.
        :returns: Its content.
        :raises SourceError: If the document cannot be read.
        """
        ...
