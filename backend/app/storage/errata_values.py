"""
Erratum value type crossing the storage port.

A plain frozen dataclass, independent of any ORM; kept apart from
:mod:`app.storage.values` only to keep modules small. Import it
through :mod:`app.storage.port`, which re-exports it.

Only rendered, sanitized HTML is stored for the erratum sections: the
raw Markdown is already kept in the immutable ``revision`` snapshot of
the row's digest, which is what diffs and approval evidence use.

Public API: :class:`StoredErratum`, :class:`LinkTarget`.
"""

import datetime
from dataclasses import dataclass

from app.domain.errata import ErratumType
from app.domain.relationships import RecordSummary


@dataclass(frozen=True, slots=True, kw_only=True)
class StoredErratum:
    """
    The stored content of one erratum record.

    :param type: Erratum type, ``None`` if missing or invalid.
    :param section: Where in the decision the error is, if given.
    :param reported_by: Free-text reporter; informational only, never an
        identity.
    :param reported_date: Authored report date, if valid.
    :param original_html: Sanitized HTML of "Original text", if any.
    :param corrected_html: Sanitized HTML of "Corrected text"; empty when
        the section is missing.
    :param notes_html: Sanitized HTML of the notes, if any.
    """

    type: ErratumType | None
    section: str | None
    reported_by: str | None
    reported_date: datetime.date | None
    original_html: str | None
    corrected_html: str
    notes_html: str | None


@dataclass(frozen=True, slots=True, kw_only=True)
class LinkTarget:
    """
    A published row that a link may resolve to, with its title.

    Used to label erratum search hits ("Erratum for <title>") without
    one query per hit.

    :param summary: Relationship summary, keyed by ``str(record id)``.
    :param title: Display title of the row.
    """

    summary: RecordSummary
    title: str
