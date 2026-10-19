"""
YAML frontmatter splitting and loading for Markdown ADR files.

A document has frontmatter when its first line is ``---``; the block ends
at the next line that is ``---`` (or ``...``). YAML is loaded with a
:class:`yaml.SafeLoader` variant that does **not** turn unquoted dates
into :class:`datetime.date` objects: ``decision-date: 2024-13-01`` would
otherwise make the whole block unparseable. Dates stay strings and are
validated by :mod:`app.domain.records`.

Public API:

- :class:`FrontmatterSplit`, :func:`split_frontmatter`
- :class:`LoadedFrontmatter`, :func:`load_frontmatter`
- :func:`json_safe`
"""

import datetime
from collections.abc import Mapping
from dataclasses import dataclass

import yaml

from app.domain.issues import Issue, IssueCode, error

_DELIMITER = "---"
_END_MARKERS = frozenset({"---", "..."})
_TIMESTAMP_TAG = "tag:yaml.org,2002:timestamp"

type JsonValue = (
    str | int | float | bool | None | list[JsonValue] | dict[str, JsonValue]
)


class _NoDateSafeLoader(yaml.SafeLoader):
    """Safe YAML loader that keeps implicit timestamps as strings."""


_NoDateSafeLoader.yaml_implicit_resolvers = {
    first: [(tag, rx) for tag, rx in resolvers if tag != _TIMESTAMP_TAG]
    for first, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


@dataclass(frozen=True, slots=True)
class FrontmatterSplit:
    """
    Result of splitting a document into frontmatter and body.

    :param yaml_text: Text between the delimiters, or ``None`` when the
        document has no (closed) frontmatter block.
    :param body: Markdown body. The whole text if there is no block.
    :param unclosed: ``True`` when an opening ``---`` has no closing line.
    """

    yaml_text: str | None
    body: str
    unclosed: bool = False


@dataclass(frozen=True, slots=True)
class LoadedFrontmatter:
    """
    Result of loading a frontmatter block.

    :param fields: The parsed mapping (empty on failure).
    :param issue: A ``bad_yaml`` issue when loading failed, else ``None``.
    """

    fields: dict[str, object]
    issue: Issue | None = None


def split_frontmatter(text: str) -> FrontmatterSplit:
    """
    Split canonical (LF-only) text into frontmatter and body.

    :param text: Canonical document text.
    :returns: The split result; never raises.
    """
    lines = text.split("\n")
    if lines[0].rstrip() != _DELIMITER:
        return FrontmatterSplit(yaml_text=None, body=text)
    for index in range(1, len(lines)):
        if lines[index].rstrip() in _END_MARKERS:
            return FrontmatterSplit(
                yaml_text="\n".join(lines[1:index]),
                body="\n".join(lines[index + 1 :]),
            )
    return FrontmatterSplit(yaml_text=None, body=text, unclosed=True)


def _yaml_error_message(exc: Exception) -> str:
    """
    Build a concise message from a YAML loader exception.

    :param exc: The exception raised while loading.
    :returns: A human-readable message with the line number if known.
    """
    mark = getattr(exc, "problem_mark", None)
    problem = getattr(exc, "problem", None) or str(exc)
    if mark is not None:
        # Marks are zero-based and the opening "---" line precedes the
        # YAML block, so the file line number is mark.line + 2.
        line = mark.line + 2
        return f"frontmatter is not valid YAML (line {line}): {problem}"
    return f"frontmatter is not valid YAML: {problem}"


def load_frontmatter(yaml_text: str) -> LoadedFrontmatter:
    """
    Load a frontmatter block as a mapping of field names to values.

    :param yaml_text: The text between the delimiters.
    :returns: The loaded fields, or an empty mapping plus a ``bad_yaml``
        issue. Never raises for malformed content.
    """
    try:
        # The loader is a SafeLoader subclass, so this is a safe load.
        data = yaml.load(yaml_text, Loader=_NoDateSafeLoader)
    except (yaml.YAMLError, ValueError) as exc:
        issue = error(IssueCode.BAD_YAML, _yaml_error_message(exc))
        return LoadedFrontmatter({}, issue)
    if data is None:
        return LoadedFrontmatter({})
    if not isinstance(data, Mapping):
        kind = type(data).__name__
        return LoadedFrontmatter(
            {},
            error(
                IssueCode.BAD_YAML,
                f"frontmatter must be a mapping of fields; got a {kind}",
            ),
        )
    return LoadedFrontmatter({str(key): value for key, value in data.items()})


def json_safe(value: object) -> JsonValue:
    """
    Convert a loaded YAML value into a JSON-serialisable value.

    Mappings get string keys, sequences and sets become lists, dates use
    ISO format and any other unexpected scalar is rendered with ``str``.

    :param value: A value produced by the YAML loader.
    :returns: An equivalent JSON-serialisable value.
    """
    if value is None or isinstance(value, str | bool | int | float):
        return value
    if isinstance(value, Mapping):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, list | tuple | set | frozenset):
        return [json_safe(item) for item in value]
    if isinstance(value, datetime.date):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)
