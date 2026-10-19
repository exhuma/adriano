"""
Canonical content hashing for ADR files (``sha256-v1``).

The digest identifies a *content revision* only. It is computed from the
exact bytes that were fetched or pushed, after this canonicalization:

1. Decode as strict UTF-8.
2. Remove one leading U+FEFF (byte order mark).
3. Replace CRLF with LF, then any remaining lone CR with LF.
4. Encode as UTF-8 and hash with SHA-256.

No path, ref, commit, project or registration id enters the hash. Bytes
that are not valid UTF-8 cannot be canonicalized; they are hashed as-is
under the separate ``sha256-raw-v1`` algorithm so the record can still be
stored (such records cannot be approved).

Public API:

- :data:`HASH_VERSION`, :data:`RAW_HASH_VERSION`
- :func:`canonicalize_text`, :func:`canonicalize`
- :class:`Digest` (``str(digest)`` -> ``"sha256-v1:<hex>"``;
  :meth:`Digest.parse` for the reverse)
- :func:`content_digest`
"""

import hashlib
import re
from dataclasses import dataclass

#: Algorithm label of the canonical digest.
HASH_VERSION = "sha256-v1"

#: Algorithm label used for bytes that are not valid UTF-8.
RAW_HASH_VERSION = "sha256-raw-v1"

_KNOWN_ALGORITHMS = frozenset({HASH_VERSION, RAW_HASH_VERSION})
_HEX_RE = re.compile(r"^[0-9a-f]{64}$")
_BOM = "﻿"


@dataclass(frozen=True, slots=True)
class Digest:
    """
    A content digest together with the algorithm that produced it.

    :param algorithm: :data:`HASH_VERSION` or :data:`RAW_HASH_VERSION`.
    :param hex: 64 lowercase hexadecimal characters.
    """

    algorithm: str
    hex: str

    def __post_init__(self) -> None:
        """
        Validate the algorithm label and the hex string.

        :raises ValueError: If either part is malformed.
        """
        if self.algorithm not in _KNOWN_ALGORITHMS:
            raise ValueError(f"unknown digest algorithm {self.algorithm!r}")
        if not _HEX_RE.match(self.hex):
            raise ValueError("digest hex must be 64 lowercase hex chars")

    def __str__(self) -> str:
        """
        Render the digest as ``<algorithm>:<hex>``.

        :returns: The storable digest string.
        """
        return f"{self.algorithm}:{self.hex}"

    @property
    def is_canonical(self) -> bool:
        """
        Tell whether the digest was computed from canonical UTF-8 text.

        :returns: ``True`` for ``sha256-v1``, ``False`` for the raw
            fallback.
        """
        return self.algorithm == HASH_VERSION

    @classmethod
    def parse(cls, value: str) -> Digest:
        """
        Parse a digest string produced by :meth:`__str__`.

        :param value: A string such as ``"sha256-v1:<hex>"``.
        :returns: The parsed digest.
        :raises ValueError: If the string is not a known digest.
        """
        algorithm, sep, hex_part = value.partition(":")
        if not sep:
            raise ValueError(f"not a digest string: {value!r}")
        return cls(algorithm=algorithm, hex=hex_part)


def canonicalize_text(text: str) -> str:
    """
    Apply the text-level canonicalization steps (BOM, line endings).

    :param text: Already decoded file content.
    :returns: Text without a leading BOM and with LF line endings only.
    """
    if text.startswith(_BOM):
        text = text[1:]
    return text.replace("\r\n", "\n").replace("\r", "\n")


def canonicalize(raw: bytes) -> str:
    """
    Decode and canonicalize raw file bytes.

    :param raw: The exact bytes fetched or pushed.
    :returns: The canonical text that is hashed by :func:`content_digest`.
    :raises UnicodeDecodeError: If *raw* is not valid UTF-8.
    """
    return canonicalize_text(raw.decode("utf-8", errors="strict"))


def content_digest(raw: bytes) -> Digest:
    """
    Compute the content digest of raw file bytes.

    Never raises for undecodable input: bytes that are not valid UTF-8 are
    hashed verbatim under :data:`RAW_HASH_VERSION`.

    :param raw: The exact bytes fetched or pushed.
    :returns: A ``sha256-v1`` digest, or a ``sha256-raw-v1`` digest when
        *raw* is not valid UTF-8.
    """
    try:
        canonical = canonicalize(raw).encode("utf-8")
    except UnicodeDecodeError:
        return Digest(RAW_HASH_VERSION, hashlib.sha256(raw).hexdigest())
    return Digest(HASH_VERSION, hashlib.sha256(canonical).hexdigest())
