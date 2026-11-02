"""Unit tests for claim mapping, dev claims and reviewer eligibility."""

import pytest

from app.auth.deps import principal_from_claims
from app.auth.dev import DEV_ISSUER, DevIdentity, dev_claims
from app.auth.rbac import reviewer_eligibility
from app.catalog_config import PolicyConfig
from app.config import Settings
from app.domain.approval import Policy, PolicyStatus
from app.errors import AuthenticationError

POLICY = PolicyConfig(
    PolicyStatus.CONFIGURED,
    Policy(
        id="global",
        version=1,
        required=True,
        reviewer_users=frozenset({"https://idp|bob"}),
        reviewer_roles=frozenset({"adr-reviewer"}),
        allow_self_approval=False,
    ),
)


def test_principal_falls_back_for_display_and_drops_unverified_email() -> None:
    """Ensure display falls back to the username and unverified email."""
    principal = principal_from_claims(
        {
            "iss": "https://idp",
            "sub": "u1",
            "preferred_username": "alice",
            "email": "a@example.com",
            "email_verified": False,
            "roles": "admin",
        },
        roles_claim="roles",
    )

    assert principal.display == "alice"
    assert principal.email is None
    assert principal.roles == ()  # a string is not a list of roles


def test_principal_requires_string_iss_and_sub() -> None:
    """Ensure claims without a usable subject are refused."""
    with pytest.raises(AuthenticationError):
        principal_from_claims({"iss": "x", "sub": 5}, roles_claim="roles")


@pytest.mark.parametrize(
    ("policy", "subject", "roles", "eligible"),
    [
        (None, "bob", [], False),
        (PolicyConfig(PolicyStatus.INVALID), "bob", [], False),
        (POLICY, "bob", [], True),
        (POLICY, "carol", ["adr-reviewer"], True),
        (POLICY, "carol", ["admin"], False),
    ],
)
def test_reviewer_eligibility(
    policy: PolicyConfig | None,
    subject: str,
    roles: list[str],
    eligible: bool,
) -> None:
    """Ensure eligibility follows the policy users and roles only."""
    result = reviewer_eligibility(
        policy, issuer="https://idp", subject=subject, roles=roles
    )

    assert result.eligible is eligible
    assert result.reason


def test_dev_claims_map_like_real_claims(test_settings: Settings) -> None:
    """Ensure dev-session claims go through the shared claim mapping."""
    claims = dev_claims(
        test_settings,
        DevIdentity(
            sub="alice", name="Alice", email="a@example.com", roles=["x"]
        ),
    )

    principal = principal_from_claims(claims, roles_claim="roles")

    assert principal.issuer == DEV_ISSUER
    assert principal.subject == "alice"
    assert principal.display == "Alice"
    assert principal.email == "a@example.com"
    assert principal.roles == ("x",)


def test_dev_claims_nest_the_roles_claim(test_settings: Settings) -> None:
    """Ensure roles are written at the configured dotted claim path."""
    settings = test_settings.model_copy(
        update={"oidc_roles_claim": "realm_access.roles"}
    )

    claims = dev_claims(settings, DevIdentity(sub="a", roles=["x"]))

    assert claims["realm_access"] == {"roles": ["x"]}
    assert "name" not in claims


def test_dev_claims_use_the_configured_issuer(test_settings: Settings) -> None:
    """Ensure a configured OIDC issuer becomes the dev issuer."""
    settings = test_settings.model_copy(
        update={"oidc_issuer": "https://idp.example"}
    )

    claims = dev_claims(settings, DevIdentity(sub="a"))

    assert claims["iss"] == "https://idp.example"
