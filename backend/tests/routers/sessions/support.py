"""Helpers of the session router tests: raw ``auth_session`` rows."""

import datetime
from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.services.auth_sessions import session_id_for

type ClientFactory = Callable[..., TestClient]

SESSION_COOKIE = "__Host-adriano-session"
ZERO_UUID = "00000000-0000-0000-0000-000000000000"


def session_row(engine: Engine, cookie: str) -> dict[str, Any] | None:
    """
    Read the raw session row of a cookie.

    :param engine: Test database engine.
    :param cookie: The cookie value.
    :returns: The row as a mapping, or ``None``.
    """
    with engine.connect() as connection:
        row = (
            connection.execute(
                text("SELECT * FROM auth_session WHERE id = :id"),
                {"id": session_id_for(cookie)},
            )
            .mappings()
            .one_or_none()
        )
    return None if row is None else dict(row)


def set_session_times(engine: Engine, cookie: str, **values: object) -> None:
    """
    Overwrite timestamp columns of a session row.

    :param engine: Test database engine.
    :param cookie: The cookie value.
    :param values: Column values.
    """
    assignments = ", ".join(f"{name} = :{name}" for name in values)
    with engine.begin() as connection:
        connection.execute(
            text(f"UPDATE auth_session SET {assignments} WHERE id = :id"),
            {"id": session_id_for(cookie), **values},
        )


def utc_now() -> datetime.datetime:
    """
    Read the current UTC time.

    :returns: An aware datetime.
    """
    return datetime.datetime.now(datetime.UTC)
