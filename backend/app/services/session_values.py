"""
Value types of the sign-in sessions (plain, never encrypted).

Used by :mod:`app.services.auth_sessions` and
:mod:`app.services.oidc_login`.

Public API: :class:`SessionPolicy`, :class:`SessionTokens`,
:class:`ActiveSession`, :class:`EndedSession`, :func:`utc_now`,
:func:`session_id_for`, :func:`access_expiry`.
"""

import datetime
import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from app.config import Settings
from app.storage.session_port import SessionKind

__all__ = [
    "ActiveSession",
    "EndedSession",
    "SessionPolicy",
    "SessionTokens",
    "access_expiry",
    "session_id_for",
    "utc_now",
]


def utc_now() -> datetime.datetime:
    """
    Read the current UTC time.

    :returns: An aware datetime.
    """
    return datetime.datetime.now(datetime.UTC)


def session_id_for(cookie: str) -> str:
    """
    Derive the stored id of a session cookie value.

    :param cookie: The raw cookie value.
    :returns: Its hex SHA-256.
    """
    return hashlib.sha256(cookie.encode("ascii")).hexdigest()


def access_expiry(claims: Mapping[str, Any]) -> datetime.datetime:
    """
    Read the ``exp`` of verified access-token claims.

    :param claims: Verified claims (``exp`` is required by the
        validator).
    :returns: The expiry.
    """
    return datetime.datetime.fromtimestamp(float(claims["exp"]), datetime.UTC)


@dataclass(frozen=True, slots=True)
class SessionPolicy:
    """
    Session lifetimes.

    :param idle: Ends after this long without activity.
    :param max_age: Ends this long after sign-in.
    """

    idle: datetime.timedelta
    max_age: datetime.timedelta

    @classmethod
    def from_settings(cls, settings: Settings) -> SessionPolicy:
        """
        Read the lifetimes from the settings.

        :param settings: Application settings.
        :returns: The policy.
        """
        return cls(
            idle=datetime.timedelta(minutes=settings.session_idle_minutes),
            max_age=datetime.timedelta(hours=settings.session_max_hours),
        )


@dataclass(frozen=True, slots=True)
class SessionTokens:
    """
    The IdP tokens of a new OIDC session (plain).

    :param access_token: Validated access token.
    :param refresh_token: Refresh token, if issued.
    :param id_token: ID token.
    :param access_expires_at: Access token ``exp``.
    """

    access_token: str
    refresh_token: str | None
    id_token: str | None
    access_expires_at: datetime.datetime


@dataclass(frozen=True, slots=True)
class ActiveSession:
    """
    A valid session.

    :param kind: How it was created.
    :param claims: The verified claims (plain).
    :param expires_at: When it ends without further activity (never
        after the absolute expiry).
    """

    kind: SessionKind
    claims: dict[str, Any]
    expires_at: datetime.datetime


@dataclass(frozen=True, slots=True)
class EndedSession:
    """
    What logout needs of a deleted session (plain).

    :param kind: How it was created.
    :param refresh_token: Its refresh token, to revoke.
    :param id_token: Its ID token (``id_token_hint``).
    """

    kind: SessionKind
    refresh_token: str | None
    id_token: str | None
