"""
Encryption at rest of the server-side session data.

Session claims, the IdP tokens and the pending sign-in data are stored
as Fernet tokens (AES-128-CBC plus HMAC-SHA256, from ``cryptography``)
under ``ADRIANO_SESSION_KEY``. A row read without the key reveals
nothing; a row encrypted under another key (the key was changed)
cannot be decrypted, and its session simply ends.

Public API: :class:`SessionCipher`, :class:`CipherError`.
"""

import json
from collections.abc import Mapping
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from pydantic import SecretStr

__all__ = ["CipherError", "SessionCipher"]


class CipherError(ValueError):
    """Raised when stored data cannot be decrypted with the key."""


class SessionCipher:
    """
    Encrypt and decrypt session values with one Fernet key.

    :param key: The Fernet key (``ADRIANO_SESSION_KEY``).
    """

    def __init__(self, key: SecretStr) -> None:
        """
        Build the Fernet instance.

        :param key: The Fernet key.
        :raises ValueError: If the key is not a Fernet key.
        """
        self._fernet = Fernet(key.get_secret_value().encode("ascii"))

    def encrypt(self, text: str) -> str:
        """
        Encrypt a string.

        :param text: Plain text.
        :returns: The Fernet token (ASCII).
        """
        return self._fernet.encrypt(text.encode("utf-8")).decode("ascii")

    def decrypt(self, token: str) -> str:
        """
        Decrypt a string.

        :param token: A token from :meth:`encrypt`.
        :returns: The plain text.
        :raises CipherError: If the token was not made with this key or
            was altered.
        """
        try:
            return self._fernet.decrypt(token.encode("ascii")).decode("utf-8")
        except (InvalidToken, UnicodeError) as exc:
            raise CipherError(
                "stored session data cannot be decrypted"
            ) from exc

    def encrypt_json(self, value: Mapping[str, Any]) -> str:
        """
        Encrypt a JSON object.

        :param value: The object (JSON-serialisable).
        :returns: The Fernet token.
        """
        return self.encrypt(json.dumps(value, separators=(",", ":")))

    def decrypt_json(self, token: str) -> dict[str, Any]:
        """
        Decrypt a JSON object.

        :param token: A token from :meth:`encrypt_json`.
        :returns: The object.
        :raises CipherError: If decryption fails or the plain text is
            not a JSON object.
        """
        try:
            value = json.loads(self.decrypt(token))
        except ValueError as exc:
            raise CipherError("stored session data is not JSON") from exc
        if not isinstance(value, dict):
            raise CipherError("stored session data is not a JSON object")
        return value  # pyright: ignore[reportUnknownVariableType]
