"""
CI push-token checks for candidate intake (not OIDC).

Push tokens are per-registration shared secrets resolved at startup
from the env var **names** listed in ``push_tokens_env``
(:class:`~app.source_config.SourceRegistration.push_tokens`). They
authorize exactly one thing: writing candidates to that registration
through ``PUT``/``POST /api/v1/candidates``. They grant no catalog
read access (user routes accept only the session cookie and ignore
``Authorization``), and a session is never accepted for intake (intake
reads only the bearer push token).

Comparison is constant-time: both sides are hashed with SHA-256 first
(so token length does not leak either) and compared with
:func:`hmac.compare_digest`; every configured token is compared, with
no early exit. Tokens are never logged or stored.

Public API: :func:`token_matches`, :func:`registrations_for_token`.
"""

import hashlib
import hmac
from collections.abc import Iterable, Sequence

from pydantic import SecretStr

from app.source_config import SourceRegistration

__all__ = ["registrations_for_token", "token_matches"]


def _fingerprint(value: str) -> bytes:
    """
    Hash a token so comparisons do not depend on its length.

    :param value: Token text.
    :returns: Its SHA-256 digest.
    """
    return hashlib.sha256(value.encode("utf-8", "surrogatepass")).digest()


def token_matches(tokens: Iterable[SecretStr], presented: str) -> bool:
    """
    Tell whether *presented* equals one of *tokens* (constant time).

    :param tokens: The registration's configured push tokens.
    :param presented: The bearer token of the request.
    :returns: ``True`` on a match; ``False`` for an empty token or no
        configured tokens.
    """
    if not presented:
        return False
    wanted = _fingerprint(presented)
    results = [
        hmac.compare_digest(_fingerprint(token.get_secret_value()), wanted)
        for token in tokens
    ]
    return any(results)


def registrations_for_token(
    sources: Sequence[SourceRegistration], presented: str
) -> list[SourceRegistration]:
    """
    List the registrations whose push tokens include *presented*.

    Used only when a request does not name a usable registration, to
    decide between 401 (token valid nowhere) and a request error.

    :param sources: All configured registrations.
    :param presented: The bearer token of the request.
    :returns: Matching registrations (every one is checked).
    """
    matches = [
        (source, token_matches(source.push_tokens, presented))
        for source in sources
    ]
    return [source for source, matched in matches if matched]
