"""
Shared helpers for the push intake, decision and diff router tests.

:func:`catalog_yaml` renders a catalog with a pollable + pushable
filesystem registration ``central`` (scope ``platform``/``payments``),
a push-only ``other`` and a poll-only ``pollonly`` (which has a push
token but no push intake). Push tokens are set in the environment by
:func:`set_push_tokens`; the values are throwaway test strings.

The fixtures live in ``tests/routers/approval/conftest.py``.
"""

import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from httpx import Response

from app.auth.dev import DEV_ISSUER
from tests.auth_helpers import sign_in

type ClientFactory = Callable[[str | None], TestClient]

CENTRAL_TOKEN = "push-central-" + "a1" * 16
OTHER_TOKEN = "push-other-" + "b2" * 16
POLLONLY_TOKEN = "push-pollonly-" + "c3" * 16

#: The approval policy used by default (``None`` omits the section).
POLICY = f"""
approval_policy:
  id: global
  version: 3
  required: true
  reviewers:
    users: ["{DEV_ISSUER}|carol"]
    roles: [adr-reviewer]
  allow_self_approval: false
"""

RBAC = """
rbac:
  roles:
    admin: [read, operate]
    adr-reader: [read]
    adr-reviewer: [read]
"""


def catalog_yaml(root: Path, policy: str | None = POLICY) -> str:
    """
    Render the test catalog.

    :param root: Filesystem root shared by the registrations.
    :param policy: ``approval_policy`` section text, or ``None``.
    :returns: The YAML text.
    """
    sources = f"""
sources:
  - id: central
    type: filesystem
    root: {root}
    published_ref: local
    scope: {{projects: [platform, payments]}}
    intake: [poll, push]
    push_tokens_env: [ADRIANO_PUSH_TOKEN_CENTRAL]
  - id: other
    type: filesystem
    root: {root}
    published_ref: local
    intake: [push]
    push_tokens_env: [ADRIANO_PUSH_TOKEN_OTHER]
  - id: pollonly
    type: filesystem
    root: {root}
    published_ref: local
    push_tokens_env: [ADRIANO_PUSH_TOKEN_POLLONLY]
"""
    return sources + (policy or "") + RBAC


def set_push_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Export the test push tokens.

    :param monkeypatch: Pytest monkeypatch.
    """
    monkeypatch.setenv("ADRIANO_PUSH_TOKEN_CENTRAL", CENTRAL_TOKEN)
    monkeypatch.setenv("ADRIANO_PUSH_TOKEN_OTHER", OTHER_TOKEN)
    monkeypatch.setenv("ADRIANO_PUSH_TOKEN_POLLONLY", POLLONLY_TOKEN)


def adr_text(
    adr_uuid: uuid.UUID | str,
    *,
    title: str = "Use a catalog",
    body: str = "We use a catalog.",
) -> str:
    """
    Render an ADR document.

    :param adr_uuid: Frontmatter UUID.
    :param title: Title.
    :param body: Markdown body.
    :returns: The text (LF line endings).
    """
    return (
        f"---\nuuid: {adr_uuid}\ntitle: {title}\n"
        f"decision-date: 2024-03-01\n---\n{body}\n"
    )


def candidate(
    adr_uuid: uuid.UUID,
    *,
    content: str | None = None,
    **overrides: Any,
) -> dict[str, Any]:
    """
    Build a candidate request body.

    :param adr_uuid: ADR UUID.
    :param content: Document text (default: :func:`adr_text`).
    :param overrides: Fields to set (``None`` removes a field).
    :returns: The JSON body.
    """
    body: dict[str, Any] = {
        "source_id": "central",
        "project": "platform",
        "adr_uuid": str(adr_uuid),
        "ref": "feature/catalog",
        "content": content if content is not None else adr_text(adr_uuid),
        "path": "doc/decisions/2024-03-01-use-a-catalog.md",
    }
    body.update(overrides)
    return {k: v for k, v in body.items() if v is not None}


def push(
    client: TestClient,
    body: Any,
    *,
    token: str | None = CENTRAL_TOKEN,
    method: str = "PUT",
) -> Response:
    """
    Send a candidate with a push token.

    :param client: Test client (its session cookie is sent too, and
        ignored by intake).
    :param body: JSON body.
    :param token: Push token, ``None`` for no ``Authorization`` header.
    :param method: ``PUT`` or ``POST``.
    :returns: The response.
    """
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return client.request(
        method, "/api/v1/candidates", json=body, headers=headers
    )


def as_user(
    client: TestClient,
    *,
    sub: str = "rita",
    roles: tuple[str, ...] = ("adr-reviewer",),
    email: str | None = "rita@example.com",
) -> None:
    """
    Switch the client's session to another dev identity.

    :param client: Test client.
    :param sub: Subject.
    :param roles: Roles.
    :param email: Verified email.
    """
    sign_in(client, sub=sub, roles=roles, email=email, name=sub.title())


def decide(
    client: TestClient,
    record_id: str,
    action: str = "accepted",
    **extra: Any,
) -> Response:
    """
    Post a decision with the client's current identity.

    :param client: Test client.
    :param record_id: Record id.
    :param action: ``accepted`` or ``rejected``.
    :param extra: Further body fields (``comment``, ``expected_digest``).
    :returns: The response.
    """
    return client.post(
        f"/api/v1/records/{record_id}/decisions",
        json={"action": action, **extra},
    )
