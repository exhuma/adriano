"""Helpers of the session router tests: raw ``auth_session`` rows."""

from sqlalchemy import Engine, text

from app.services.auth_sessions import session_id_for

ZERO_UUID = "00000000-0000-0000-0000-000000000000"


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
