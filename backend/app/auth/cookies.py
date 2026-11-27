"""
The session and sign-in cookies.

Both use the ``__Host-`` prefix, so the browser only accepts them from
a secure origin, with ``Path=/`` and without ``Domain`` (no subdomain
can set or read them). The ``Set-Cookie`` values are written here
verbatim so their attributes are exactly the documented ones:

- :data:`SESSION_COOKIE`: ``Secure; HttpOnly; SameSite=Strict;
  Path=/``, no ``Max-Age``/``Expires`` (a browser-session cookie; the
  server-side expiry is authoritative). The value is an opaque random
  id; only its SHA-256 is stored.
- :data:`LOGIN_COOKIE`: binds a pending sign-in to the browser that
  started it. ``SameSite=Lax`` because it must accompany the top-level
  redirect back from the IdP (a ``Strict`` cookie would not);
  ``Max-Age`` is the 10-minute sign-in window.

Public API: :data:`SESSION_COOKIE`, :data:`LOGIN_COOKIE`,
:data:`LOGIN_COOKIE_SECONDS`, :func:`read_cookie`,
:func:`set_session_cookie`, :func:`clear_session_cookie`,
:func:`set_login_cookie`, :func:`clear_login_cookie`.
"""

import re

from starlette.requests import Request
from starlette.responses import Response

__all__ = [
    "LOGIN_COOKIE",
    "LOGIN_COOKIE_SECONDS",
    "SESSION_COOKIE",
    "clear_login_cookie",
    "clear_session_cookie",
    "read_cookie",
    "set_login_cookie",
    "set_session_cookie",
]

SESSION_COOKIE = "__Host-adriano-session"
LOGIN_COOKIE = "__Host-adriano-login"

#: Lifetime of the sign-in binding cookie (and of a pending sign-in).
LOGIN_COOKIE_SECONDS = 600

#: Longest cookie value accepted; real values are 43 characters.
_MAX_VALUE_LENGTH = 256

#: Values this module issues (``secrets.token_urlsafe``).
_VALUE = re.compile(r"[A-Za-z0-9_-]+")

_EXPIRED = "Max-Age=0; Expires=Thu, 01 Jan 1970 00:00:00 GMT"


def read_cookie(request: Request, name: str) -> str | None:
    """
    Read a cookie this module issued.

    :param request: The request.
    :param name: Cookie name.
    :returns: The value, or ``None`` when absent or not well-formed.
    """
    value = request.cookies.get(name)
    if not value or len(value) > _MAX_VALUE_LENGTH:
        return None
    return value if _VALUE.fullmatch(value) else None


def _set(response: Response, name: str, value: str, attributes: str) -> None:
    """
    Append one ``Set-Cookie`` header.

    :param response: The response.
    :param name: Cookie name.
    :param value: Cookie value (url-safe characters only).
    :param attributes: Attributes after ``Path=/; Secure; HttpOnly``.
    """
    if value and not _VALUE.fullmatch(value):
        raise ValueError("cookie values must be url-safe tokens")
    response.headers.append(
        "set-cookie",
        f"{name}={value}; Path=/; Secure; HttpOnly; {attributes}",
    )


def set_session_cookie(response: Response, value: str) -> None:
    """
    Set the session cookie.

    :param response: The response.
    :param value: The opaque session id.
    """
    _set(response, SESSION_COOKIE, value, "SameSite=Strict")


def clear_session_cookie(response: Response) -> None:
    """
    Expire the session cookie.

    :param response: The response.
    """
    _set(response, SESSION_COOKIE, "", f"SameSite=Strict; {_EXPIRED}")


def set_login_cookie(response: Response, state: str) -> None:
    """
    Bind a pending sign-in to this browser.

    :param response: The response.
    :param state: The sign-in ``state``.
    """
    _set(
        response,
        LOGIN_COOKIE,
        state,
        f"SameSite=Lax; Max-Age={LOGIN_COOKIE_SECONDS}",
    )


def clear_login_cookie(response: Response) -> None:
    """
    Expire the sign-in binding cookie.

    :param response: The response.
    """
    _set(response, LOGIN_COOKIE, "", f"SameSite=Lax; {_EXPIRED}")
