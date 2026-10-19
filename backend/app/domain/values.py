"""
Value types shared by record parsing, relationships and storage.

Public API: :class:`RecordKind`, :class:`TitleSource`, :class:`LinkType`,
:class:`Links` (``to_dict`` / ``from_dict`` for the stored JSON shape),
:class:`Identity` and :func:`record_key`.
"""

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum


class RecordKind(StrEnum):
    """Kind of ADR record."""

    DECISION = "decision"
    ERRATUM = "erratum"


class TitleSource(StrEnum):
    """Where the display title came from."""

    FRONTMATTER = "frontmatter"
    H1 = "h1"
    FILENAME = "filename"


class LinkType(StrEnum):
    """Outbound relationship types, named as written in frontmatter."""

    UPDATES = "updates"
    OBSOLETES = "obsoletes"
    CORRECTS = "corrects"


@dataclass(frozen=True, slots=True)
class Links:
    """
    Outbound UUID relationships of one record.

    :param updates: Earlier decisions this record updates.
    :param obsoletes: Decisions this record replaces (includes the
        legacy ``deprecates`` value).
    :param corrects: The decision this erratum corrects, if any.
    """

    updates: tuple[uuid.UUID, ...] = ()
    obsoletes: tuple[uuid.UUID, ...] = ()
    corrects: uuid.UUID | None = None

    def pairs(self) -> tuple[tuple[LinkType, uuid.UUID], ...]:
        """
        List every outbound link with its type, in a stable order.

        :returns: ``(link type, target UUID)`` pairs.
        """
        result = [(LinkType.UPDATES, target) for target in self.updates]
        result += [(LinkType.OBSOLETES, target) for target in self.obsoletes]
        if self.corrects is not None:
            result.append((LinkType.CORRECTS, self.corrects))
        return tuple(result)

    def to_dict(self) -> dict[str, list[str] | str | None]:
        """
        Convert to the JSON-serialisable shape stored in ``record.links``.

        :returns: ``{"updates": [...], "obsoletes": [...],
            "corrects": uuid-or-None}`` with UUIDs as strings.
        """
        return {
            "updates": [str(target) for target in self.updates],
            "obsoletes": [str(target) for target in self.obsoletes],
            "corrects": None if self.corrects is None else str(self.corrects),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> Links:
        """
        Rebuild links from :meth:`to_dict` output.

        :param data: Stored mapping; missing keys mean no links.
        :returns: The links.
        :raises ValueError: If a stored UUID is malformed.
        """
        updates = data.get("updates") or []
        obsoletes = data.get("obsoletes") or []
        corrects = data.get("corrects")
        return cls(
            updates=tuple(uuid.UUID(str(item)) for item in updates),
            obsoletes=tuple(uuid.UUID(str(item)) for item in obsoletes),
            corrects=None if corrects is None else uuid.UUID(str(corrects)),
        )


@dataclass(frozen=True, slots=True, order=True)
class Identity:
    """
    Logical identity of an ADR: record key within registration + project.

    :param source_id: Source registration id.
    :param project: Owning project path.
    :param record_key: UUID string or fallback key (:func:`record_key`).
    """

    source_id: str
    project: str
    record_key: str

    def __str__(self) -> str:
        """
        Render the identity for messages and logs.

        :returns: ``<source_id>/<project>/<record_key>``.
        """
        return f"{self.source_id}/{self.project}/{self.record_key}"


def record_key(
    adr_uuid: uuid.UUID | None, source_id: str, project: str, path: str
) -> str:
    """
    Compute the stable record key used in the logical identity.

    :param adr_uuid: Authored UUID, if valid.
    :param source_id: Source registration id.
    :param project: Owning project path.
    :param path: File path inside the project.
    :returns: The lowercase UUID string, or
        ``src:<source_id>/<project>/<path>`` when there is no valid UUID.
        A UUID is never invented.
    """
    if adr_uuid is not None:
        return str(adr_uuid)
    return f"src:{source_id}/{project}/{path}"
