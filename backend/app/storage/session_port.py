"""
DB-neutral storage port of the sign-in sessions.

Kept apart from the catalog port (:mod:`app.storage.port`): sessions
are an authentication concern with their own unit of work. Values
crossing the port are already encrypted (Fernet tokens as text) by the
service layer; storage never sees a plain token, claim or cookie value.

Unit-of-work rules: :meth:`SessionStoreProvider.unit_of_work` commits
when the block exits normally and rolls back when it raises.
:meth:`SessionStore.get_session` with ``lock=True`` holds a row lock
until the unit of work ends, which serialises token refreshes of one
session across workers and replicas.

Public API: :class:`SessionKind`, :class:`StoredSession`,
:class:`SessionTokensUpdate`, :class:`PendingLogin`,
:class:`SessionStore`, :class:`SessionStoreProvider`.
"""

import datetime
from contextlib import AbstractContextManager
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

__all__ = [
    "PendingLogin",
    "SessionKind",
    "SessionStore",
    "SessionStoreProvider",
    "SessionTokensUpdate",
    "StoredSession",
]


class SessionKind(StrEnum):
    """How a session was created."""

    OIDC = "oidc"
    DEV = "dev"


@dataclass(frozen=True, slots=True)
class StoredSession:
    """
    One stored session; secret members are encrypted.

    :param id: Hex SHA-256 of the cookie value.
    :param kind: How it was created.
    :param subject: The user's ``sub`` (plain).
    :param claims: Encrypted claims JSON.
    :param access_token: Encrypted access token (``None`` for dev).
    :param refresh_token: Encrypted refresh token, if any.
    :param id_token: Encrypted ID token, if any.
    :param access_expires_at: Access token expiry (``None`` for dev).
    :param created_at: Sign-in time.
    :param last_seen_at: Last recorded activity.
    :param idle_expires_at: Sliding expiry (never after the absolute).
    :param absolute_expires_at: Hard expiry.
    """

    id: str
    kind: SessionKind
    subject: str
    claims: str
    access_token: str | None
    refresh_token: str | None
    id_token: str | None
    access_expires_at: datetime.datetime | None
    created_at: datetime.datetime
    last_seen_at: datetime.datetime
    idle_expires_at: datetime.datetime
    absolute_expires_at: datetime.datetime


@dataclass(frozen=True, slots=True)
class SessionTokensUpdate:
    """
    New tokens of a session after a refresh (encrypted).

    :param claims: Encrypted claims of the new access token.
    :param access_token: Encrypted access token.
    :param refresh_token: Encrypted (rotated) refresh token, if any.
    :param id_token: Encrypted ID token, if any.
    :param access_expires_at: New access token expiry.
    """

    claims: str
    access_token: str
    refresh_token: str | None
    id_token: str | None
    access_expires_at: datetime.datetime


@dataclass(frozen=True, slots=True)
class PendingLogin:
    """
    A pending OIDC sign-in.

    :param id: Hex SHA-256 of the sign-in ``state``.
    :param payload: Encrypted JSON (verifier, nonce, return path,
        redirect URI).
    :param expires_at: End of the sign-in window.
    """

    id: str
    payload: str
    expires_at: datetime.datetime


class SessionStore(Protocol):
    """Session operations inside one unit of work."""

    def insert_session(self, session: StoredSession) -> None:
        """
        Store a new session.

        :param session: The session.
        """
        ...

    def get_session(
        self, session_id: str, *, lock: bool = False
    ) -> StoredSession | None:
        """
        Load a session.

        :param session_id: Hex SHA-256 of the cookie value.
        :param lock: Hold a row lock until the unit of work ends.
        :returns: The session, or ``None``.
        """
        ...

    def update_tokens(
        self, session_id: str, update: SessionTokensUpdate
    ) -> None:
        """
        Replace the tokens and claims of a session.

        :param session_id: Session id.
        :param update: The new values.
        """
        ...

    def touch_session(
        self,
        session_id: str,
        *,
        seen_at: datetime.datetime,
        idle_expires_at: datetime.datetime,
    ) -> None:
        """
        Record activity.

        :param session_id: Session id.
        :param seen_at: Activity time.
        :param idle_expires_at: New sliding expiry.
        """
        ...

    def delete_session(self, session_id: str) -> StoredSession | None:
        """
        Delete a session.

        :param session_id: Session id.
        :returns: The deleted session, or ``None`` if there was none.
        """
        ...

    def insert_login(self, login: PendingLogin) -> None:
        """
        Store a pending sign-in.

        :param login: The pending sign-in.
        """
        ...

    def take_login(self, login_id: str) -> PendingLogin | None:
        """
        Delete and return a pending sign-in (single use).

        :param login_id: Hex SHA-256 of the ``state``.
        :returns: The pending sign-in, or ``None`` if there is none (or
            it was already taken).
        """
        ...

    def purge_expired(self, now: datetime.datetime) -> int:
        """
        Delete expired sessions and pending sign-ins.

        :param now: Current time.
        :returns: The number of deleted rows.
        """
        ...


class SessionStoreProvider(Protocol):
    """Hands out :class:`SessionStore` units of work."""

    def unit_of_work(self) -> AbstractContextManager[SessionStore]:
        """
        Open one transaction.

        :returns: A context manager yielding the store; commits on
            normal exit, rolls back on error.
        """
        ...
