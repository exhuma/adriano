"""
Unit tests for :class:`app.auth.oidc.OidcValidator`.

Tokens come from :class:`tests.auth_helpers.FakeIdp` (local RSA key,
mocked discovery, local JWKS); no network.
"""

import datetime
from typing import Any

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.errors import AuthenticationError, AuthUnavailableError
from tests.auth_helpers import CLIENT_ID, IDP_ISSUER, FakeIdp


def test_valid_access_token_is_accepted() -> None:
    """Ensure a well-formed RS256 token yields its claims."""
    idp = FakeIdp()
    validator = idp.validator()

    claims = validator.decode(idp.token())
    again = validator.decode(idp.token())

    assert claims["sub"] == "alice-123"
    assert again["iss"] == IDP_ISSUER
    assert idp.discovery_calls == 1  # discovery is cached


def test_issuer_defaults_to_discovery() -> None:
    """Ensure an unset issuer uses the discovery document's issuer."""
    idp = FakeIdp()
    validator = idp.validator(issuer=None)

    assert validator.decode(idp.token())["iss"] == IDP_ISSUER
    with pytest.raises(AuthenticationError):
        validator.decode(idp.token(iss="https://other"))


@pytest.mark.parametrize(
    "overrides",
    [
        {"aud": "another-app"},
        {"iss": "https://evil.example"},
        {"sub": None},
        {"nbf": datetime.datetime(2999, 1, 1, tzinfo=datetime.UTC)},
    ],
)
def test_token_with_bad_claims_is_rejected(overrides: dict[str, Any]) -> None:
    """Ensure tokens enforce aud, iss, sub and nbf."""
    idp = FakeIdp()

    with pytest.raises(AuthenticationError) as excinfo:
        idp.validator().decode(idp.token(**overrides))

    assert excinfo.value.code == "invalid_token"


def test_expired_token_is_rejected() -> None:
    """Ensure an expired token is token_expired."""
    idp = FakeIdp()

    with pytest.raises(AuthenticationError) as excinfo:
        idp.validator().decode(idp.token(expires_in=-60))

    assert excinfo.value.code == "token_expired"


def test_tampered_signature_is_rejected() -> None:
    """Ensure a token signed by another key under the same kid fails."""
    idp = FakeIdp()
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    with pytest.raises(AuthenticationError):
        idp.validator().decode(idp.token(key=other))


def test_unknown_kid_is_rejected() -> None:
    """Ensure a token whose kid is not in the JWKS fails."""
    idp = FakeIdp()

    with pytest.raises(AuthenticationError):
        idp.validator().decode(FakeIdp(kid="unknown-kid").token())


def test_failed_discovery_is_unavailable_and_retried() -> None:
    """Ensure an unreachable IdP is a 503 error, retried next time."""
    idp = FakeIdp(discovery_status=500)
    validator = idp.validator()

    for _ in range(2):
        with pytest.raises(AuthUnavailableError):
            validator.decode(idp.token())

    assert idp.discovery_calls == 2


def test_discovery_document_is_shared() -> None:
    """Ensure discovery() returns the cached document with endpoints."""
    idp = FakeIdp()
    validator = idp.validator()

    document = validator.discovery()

    assert validator.discovery() is document
    assert document["token_endpoint"].endswith("/token")
    assert idp.discovery_calls == 1


def _id_token(idp: FakeIdp, **overrides: Any) -> str:
    """
    Sign an ID token for the test client.

    :param idp: The fake IdP.
    :param overrides: Claims to set.
    :returns: The token.
    """
    claims: dict[str, Any] = {"aud": CLIENT_ID, "nonce": "n-1", "roles": None}
    claims.update(overrides)
    return idp.token(**claims)


def test_id_token_is_accepted() -> None:
    """Ensure a matching ID token yields its claims."""
    idp = FakeIdp()

    claims = idp.validator().decode_id_token(
        _id_token(idp), client_id=CLIENT_ID, nonce="n-1"
    )

    assert claims["sub"] == "alice-123"


@pytest.mark.parametrize(
    "overrides",
    [
        {"nonce": "other"},
        {"nonce": None},
        {"aud": "adr_viewer"},
        {"aud": [CLIENT_ID, "other"], "azp": "other"},
        {"iss": "https://evil.example"},
    ],
)
def test_id_token_with_bad_claims_is_rejected(
    overrides: dict[str, Any],
) -> None:
    """Ensure ID tokens enforce nonce, aud (client id), azp and iss."""
    idp = FakeIdp()

    with pytest.raises(AuthenticationError):
        idp.validator().decode_id_token(
            _id_token(idp, **overrides), client_id=CLIENT_ID, nonce="n-1"
        )


def test_id_token_with_several_audiences_and_azp_is_accepted() -> None:
    """Ensure azp equal to the client id admits several audiences."""
    idp = FakeIdp()
    token = _id_token(idp, aud=[CLIENT_ID, "other"], azp=CLIENT_ID)

    claims = idp.validator().decode_id_token(
        token, client_id=CLIENT_ID, nonce="n-1"
    )

    assert claims["azp"] == CLIENT_ID
