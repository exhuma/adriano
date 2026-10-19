"""Tests for the canonical content digest (``app.domain.hashing``)."""

import hashlib

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from app.domain.hashing import (
    HASH_VERSION,
    RAW_HASH_VERSION,
    Digest,
    canonicalize,
    content_digest,
)

DOC = "---\nuuid: x\n---\n# Title\n\nBody line\n"


def test_digest_format() -> None:
    """Ensure the digest renders as ``sha256-v1:<64 lowercase hex>``."""
    digest = content_digest(DOC.encode())

    text = str(digest)

    expected = hashlib.sha256(DOC.encode()).hexdigest()
    assert text == f"{HASH_VERSION}:{expected}"


@pytest.mark.parametrize(
    "variant",
    [
        DOC.replace("\n", "\r\n").encode(),
        DOC.replace("\n", "\r").encode(),
        b"\xef\xbb\xbf" + DOC.encode(),
        b"\xef\xbb\xbf" + DOC.replace("\n", "\r\n").encode(),
    ],
    ids=["crlf", "lone-cr", "bom", "bom-crlf"],
)
def test_line_endings_and_bom_do_not_change_digest(variant: bytes) -> None:
    """Ensure CRLF, lone CR and a leading BOM give the same digest."""
    baseline = content_digest(DOC.encode())

    result = content_digest(variant)

    assert result == baseline


def test_only_one_bom_is_removed() -> None:
    """Ensure a second BOM is content and changes the digest."""
    single = b"\xef\xbb\xbf" + DOC.encode()
    double = b"\xef\xbb\xbf" + single

    assert content_digest(double) != content_digest(single)


def test_content_edit_changes_digest() -> None:
    """Ensure editing a single character produces a different digest."""
    edited = DOC.replace("Body", "Bode")

    assert content_digest(edited.encode()) != content_digest(DOC.encode())


def test_digest_depends_only_on_bytes() -> None:
    """Ensure the digest API takes no path or provenance input."""
    first = content_digest(DOC.encode())
    second = content_digest(bytes(DOC.encode()))

    assert first == second


def test_invalid_utf8_uses_raw_digest() -> None:
    """Ensure undecodable bytes are hashed verbatim as sha256-raw-v1."""
    raw = b"---\nuuid: \xff\n---\n"

    digest = content_digest(raw)

    assert digest == Digest(RAW_HASH_VERSION, hashlib.sha256(raw).hexdigest())
    assert not digest.is_canonical


def test_canonicalize_rejects_invalid_utf8() -> None:
    """Ensure canonicalize raises for bytes that are not UTF-8."""
    with pytest.raises(UnicodeDecodeError):
        canonicalize(b"\xff")


def test_digest_parse_round_trip() -> None:
    """Ensure a stored digest string parses back to an equal digest."""
    digest = content_digest(DOC.encode())

    assert Digest.parse(str(digest)) == digest


@pytest.mark.parametrize(
    "value", ["sha256-v1", "md5:" + "0" * 64, "sha256-v1:XYZ", "sha256-v1:"]
)
def test_digest_parse_rejects_garbage(value: str) -> None:
    """Ensure malformed digest strings are refused."""
    with pytest.raises(ValueError):
        Digest.parse(value)


@given(st.text())
def test_crlf_invariance_property(text: str) -> None:
    """Ensure any text hashes the same with LF and with CRLF endings."""
    lf = text.replace("\r\n", "\n").replace("\r", "\n")
    crlf = lf.replace("\n", "\r\n")

    assert content_digest(crlf.encode()) == content_digest(lf.encode())


@given(st.text(min_size=1), st.text(min_size=1))
def test_distinct_canonical_text_gives_distinct_digest(
    first: str, second: str
) -> None:
    """Ensure different canonical texts never share a digest."""
    a = canonicalize(first.encode())
    b = canonicalize(second.encode())

    assume(a != b)

    assert content_digest(a.encode()) != content_digest(b.encode())
