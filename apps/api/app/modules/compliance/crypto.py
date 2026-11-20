"""Symmetric encryption for stored secrets (integration credentials, MFA seeds).

Primary key: settings.encryption_key (env ENCRYPTION_KEY, a Fernet key), required in production
(Settings.validate_for_runtime). Outside production, if ENCRYPTION_KEY is unset, a key derived from JWT_SECRET via
HKDF-SHA256 is used. Decryption always also tries the legacy JWT-derived key so values written before a dedicated
key was configured stay readable; re-encrypting them (any write) migrates them to the new key.
"""
import base64
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.core.config import get_settings
from app.core.errors import AppError


@lru_cache(maxsize=4)
def _fernet(secret: str) -> Fernet:
    """Legacy key: HKDF(JWT_SECRET)."""
    key = HKDF(algorithm=hashes.SHA256(), length=32, salt=b"leadex-ai/secrets", info=b"leadex-secrets-v1").derive(
        secret.encode()
    )
    return Fernet(base64.urlsafe_b64encode(key))


@lru_cache(maxsize=8)
def _keyring(encryption_key: str | None, jwt_secret: str, production: bool) -> MultiFernet:
    keys: list[Fernet] = []
    if encryption_key:
        keys.append(Fernet(encryption_key.encode()))
    elif production:
        raise AppError(500, "encryption_key_missing", "ENCRYPTION_KEY is not configured")
    keys.append(_fernet(jwt_secret))  # first key encrypts; legacy key kept for decryption only
    return MultiFernet(keys)


def _current() -> MultiFernet:
    s = get_settings()
    return _keyring(s.encryption_key, s.jwt_secret, s.is_production)


def encrypt(plaintext: str) -> str:
    return _current().encrypt(plaintext.encode()).decode()


def decrypt(token: str) -> str:
    try:
        return _current().decrypt(token.encode()).decode()
    except InvalidToken as e:
        raise AppError(500, "secret_unreadable", "Stored secret could not be decrypted") from e
