"""Unit tests for the CSRF origin check, cookies and return paths."""

import pytest
from pydantic import SecretStr
from starlette.requests import Request
from starlette.responses import Response

from app.auth.cipher import CipherError, SessionCipher
from app.auth.cookies import read_cookie, set_session_cookie
from app.auth.csrf import check_csrf, request_origin
from app.errors import ForbiddenError
from app.services.oidc_login import safe_return_to
from tests.auth_helpers import TEST_SESSION_KEY


def _request(
    *,
    scheme: str = "https",
    host: str = "adriano.example",
    headers: dict[str, str] | None = None,
    method: str = "POST",
) -> Request:
    """
    Build a bare request.

    :param scheme: Scope scheme (as set by the proxy-headers middleware).
    :param host: ``Host`` header.
    :param headers: Further headers.
    :param method: HTTP method.
    :returns: The request.
    """
    raw = [(b"host", host.encode())]
    raw += [
        (name.lower().encode(), value.encode())
        for name, value in (headers or {}).items()
    ]
    return Request(
        {
            "type": "http",
            "method": method,
            "scheme": scheme,
            "path": "/api/v1/sources/poll",
            "query_string": b"",
            "headers": raw,
            "server": ("10.0.0.1", 8000),
        }
    )


@pytest.mark.parametrize(
    ("scheme", "host", "origin"),
    [
        ("https", "adriano.example", "https://adriano.example"),
        ("https", "Adriano.Example:443", "https://adriano.example"),
        ("http", "localhost:5173", "http://localhost:5173"),
        ("https", "adriano.example:8443", "https://adriano.example:8443"),
    ],
)
def test_request_origin_is_normalised(
    scheme: str, host: str, origin: str
) -> None:
    """Ensure the own origin drops default ports and lower-cases."""
    assert request_origin(_request(scheme=scheme, host=host)) == origin


def test_forwarded_host_is_not_honoured() -> None:
    """Ensure a client cannot choose the origin it is compared with."""
    request = _request(
        headers={
            "X-Adriano-CSRF": "1",
            "Origin": "https://evil.example",
            "X-Forwarded-Host": "evil.example",
        }
    )

    with pytest.raises(ForbiddenError):
        check_csrf(request)


@pytest.mark.parametrize(
    "origin",
    [
        "https://evil.example",
        "http://adriano.example",
        "https://adriano.example:444",
        "https://adriano.example/path",
        "https://user@adriano.example",
        "null",
        "",
    ],
)
def test_foreign_or_malformed_origin_fails(origin: str) -> None:
    """Ensure any Origin but the request's own is refused."""
    request = _request(headers={"X-Adriano-CSRF": "1", "Origin": origin})

    with pytest.raises(ForbiddenError) as excinfo:
        check_csrf(request)

    assert excinfo.value.code == "csrf_failed"


@pytest.mark.parametrize(
    "headers",
    [
        {"X-Adriano-CSRF": "1"},
        {"X-Adriano-CSRF": "1", "Origin": "https://adriano.example"},
        {"X-Adriano-CSRF": "1", "Origin": "https://ADRIANO.example:443"},
    ],
)
def test_header_and_same_origin_pass(headers: dict[str, str]) -> None:
    """Ensure the header with an absent or same Origin passes."""
    check_csrf(_request(headers=headers))


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, "/"),
        ("", "/"),
        ("/", "/"),
        ("/records/a?b=1#c", "/records/a?b=1#c"),
        ("//evil.example", "/"),
        ("/\\evil.example", "/"),
        ("https://evil.example", "/"),
        ("javascript:alert(1)", "/"),
        ("records", "/"),
        ("/a\tb", "/"),
        ("/" + "a" * 2048, "/"),
    ],
)
def test_safe_return_to(value: str | None, expected: str) -> None:
    """Ensure only same-site relative paths survive as return targets."""
    assert safe_return_to(value) == expected


def test_cookie_values_must_be_tokens() -> None:
    """Ensure cookie values this app never issues are ignored."""
    request = _request(
        headers={"Cookie": "__Host-adriano-session=a.b"}, method="GET"
    )

    assert read_cookie(request, "__Host-adriano-session") is None
    with pytest.raises(ValueError):
        set_session_cookie(Response(), "bad value")


def test_cipher_round_trip_and_key_change() -> None:
    """Ensure data encrypted under another key cannot be read."""
    cipher = SessionCipher(SecretStr(TEST_SESSION_KEY))
    other = SessionCipher(
        SecretStr("hPbuVOp5vq3Kt6QZbGVfC0sZ8m0tZ8bE3dzGq4vXg2Q=")
    )
    sealed = cipher.encrypt_json({"sub": "alice"})

    assert cipher.decrypt_json(sealed) == {"sub": "alice"}
    assert "alice" not in sealed
    with pytest.raises(CipherError):
        other.decrypt_json(sealed)
