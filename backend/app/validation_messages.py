"""
Readable, secret-free messages for pydantic validation errors.

Configuration problems are shown to operators (``check-config``,
startup log, ``/api/v1/sources``). :func:`describe_validation_error`
renders each error as ``<location>: <message>`` and deliberately leaves
out the offending input values, which could be secrets.

Public API: :func:`describe_validation_error`.
"""

from pydantic import ValidationError


def describe_validation_error(exc: ValidationError, prefix: str = "") -> str:
    """
    Render a validation error without echoing input values.

    :param exc: The pydantic error.
    :param prefix: Location prefix such as ``sources[0]``.
    :returns: ``"<loc>: <msg>; <loc>: <msg>"``.
    """
    parts = []
    for item in exc.errors(include_url=False, include_input=False):
        location = ".".join(str(part) for part in item["loc"])
        where = ".".join(part for part in (prefix, location) if part)
        parts.append(f"{where or 'value'}: {item['msg']}")
    return "; ".join(parts)
