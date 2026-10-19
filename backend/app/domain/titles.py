"""
ADR file names, filename dates and display-title derivation.

Public API: :data:`ADR_FILENAME_RE`, :func:`is_adr_filename`,
:func:`filename_date`, :func:`derive_title`.
"""

import datetime
import re

from app.domain.fields import parse_iso_date
from app.domain.values import TitleSource

#: Legacy discovery pattern for ADR filenames (applied to the basename).
ADR_FILENAME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-(.*)\.md$")

_H1_RE = re.compile(r"^ {0,3}#[ \t]+(.+?)(?:[ \t]+#+)?[ \t]*$")
_FENCE_RE = re.compile(r"^ {0,3}(```|~~~)")
_SLUG_SEP_RE = re.compile(r"[-_\s]+")


def _basename(filename: str) -> str:
    """
    Strip any directory part from a POSIX-style file name.

    :param filename: File name or repository path.
    :returns: The last path segment.
    """
    return filename.rsplit("/", 1)[-1]


def is_adr_filename(name: str) -> bool:
    """
    Tell whether a file name matches the legacy ADR discovery pattern.

    :param name: File name or repository path; only the basename counts.
    :returns: ``True`` for names like ``2024-12-24-use-postgresql.md``.
    """
    return ADR_FILENAME_RE.match(_basename(name)) is not None


def filename_date(name: str) -> datetime.date | None:
    """
    Extract the date prefix of an ADR file name.

    :param name: File name or repository path.
    :returns: The date if the basename starts with a valid
        ``YYYY-MM-DD-`` prefix, else ``None``.
    """
    base = _basename(name)
    if len(base) < 11 or base[10] != "-":
        return None
    return parse_iso_date(base[:10])


def _first_h1(body: str) -> str | None:
    """
    Find the text of the first ATX H1 heading outside code fences.

    :param body: Markdown body.
    :returns: The heading text, or ``None``.
    """
    in_fence = False
    for line in body.split("\n"):
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        match = None if in_fence else _H1_RE.match(line)
        if match:
            return match.group(1).strip()
    return None


def _humanise_filename(filename: str) -> str:
    """
    Turn an ADR file name into a readable title.

    :param filename: File name or repository path.
    :returns: E.g. ``"Use postgresql"`` for
        ``2024-12-24-use-postgresql.md``.
    """
    base = _basename(filename)
    match = ADR_FILENAME_RE.match(base)
    slug = match.group(1) if match else base.removesuffix(".md")
    words = _SLUG_SEP_RE.sub(" ", slug).strip()
    if not words:
        return base or "Untitled"
    return words[0].upper() + words[1:]


def derive_title(
    explicit: str | None, body: str, filename: str
) -> tuple[str, TitleSource]:
    """
    Choose the display title: frontmatter, first H1, then filename.

    :param explicit: Validated frontmatter ``title``, if any.
    :param body: Markdown body.
    :param filename: File name or repository path.
    :returns: The title and where it came from.
    """
    if explicit:
        return explicit, TitleSource.FRONTMATTER
    heading = _first_h1(body)
    if heading:
        return heading, TitleSource.H1
    return _humanise_filename(filename), TitleSource.FILENAME
