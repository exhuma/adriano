"""Unit tests for claim mapping, reviewer eligibility and the mint CLI."""

import io

import jwt
import pytest

from app.auth.deps import principal_from_claims
from app.auth.dev import DEV_ISSUER, decode_dev_token
from app.auth.rbac import reviewer_eligibility
from app.catalog_config import PolicyConfig
from app.cli import EXIT_OK, EXIT_USAGE, main
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


def test_mint_dev_token_cli_prints_a_valid_token(
    test_settings: Settings,
) -> None:
    """Ensure the CLI mints a token the dev validator accepts."""
    out = io.StringIO()

    code = main(
        [
            "mint-dev-token",
            "--sub",
            "alice",
            "--roles",
            "admin, adr-reader",
            "--minutes",
            "5",
        ],
        settings=test_settings,
        out=out,
    )
    token = out.getvalue().strip()
    claims = decode_dev_token(token, test_settings)

    assert code == EXIT_OK
    assert jwt.get_unverified_header(token)["alg"] == "HS256"
    assert claims["iss"] == DEV_ISSUER
    assert claims["aud"] == "adr_viewer"
    assert claims["roles"] == ["admin", "adr-reader"]
    assert claims["exp"] - claims["iat"] == 300


def test_mint_dev_token_cli_nests_the_roles_claim(
    test_settings: Settings,
) -> None:
    """Ensure roles are written at the configured dotted claim path."""
    settings = test_settings.model_copy(
        update={"oidc_roles_claim": "realm_access.roles"}
    )
    out = io.StringIO()

    main(
        ["mint-dev-token", "--sub", "a", "--roles", "x"],
        settings=settings,
        out=out,
    )
    claims = decode_dev_token(out.getvalue().strip(), settings)

    assert claims["realm_access"] == {"roles": ["x"]}


def test_mint_dev_token_cli_needs_the_secret(test_settings: Settings) -> None:
    """Ensure the CLI refuses to mint without the dev shared secret."""
    settings = test_settings.model_copy(update={"dev_shared_secret": None})
    out = io.StringIO()

    code = main(["mint-dev-token", "--sub", "a"], settings=settings, out=out)

    assert code == EXIT_USAGE
    assert out.getvalue() == ""
