import hashlib
import secrets
import uuid
from datetime import timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.config import get_settings
from app.core.db import utcnow

_hasher = PasswordHasher()  # Argon2id defaults


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def create_access_token(user_id: uuid.UUID) -> str:
    s = get_settings()
    now = utcnow()
    payload = {
        "sub": str(user_id),
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=s.access_token_minutes),
        "jti": secrets.token_hex(8),
    }
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm)


def decode_access_token(token: str) -> uuid.UUID | None:
    s = get_settings()
    try:
        payload = jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm])
        if payload.get("type") != "access":
            return None
        return uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None


def new_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


PORTAL_TOKEN_MINUTES = 30


def create_portal_token(account_id: uuid.UUID, org_id: uuid.UUID, role: str, subject_id: uuid.UUID) -> str:
    """Short-lived session for external marketplace portal users. Distinct `type` so it can never pass as a
    staff access token (decode_access_token requires type == "access")."""
    s = get_settings()
    now = utcnow()
    payload = {
        "sub": str(account_id), "type": "portal", "org": str(org_id), "role": role, "sid": str(subject_id),
        "iat": now, "exp": now + timedelta(minutes=PORTAL_TOKEN_MINUTES), "jti": secrets.token_hex(8),
    }
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm)


def decode_portal_token(token: str) -> dict | None:
    s = get_settings()
    try:
        p = jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm])
        if p.get("type") != "portal" or p.get("role") not in ("provider", "customer"):
            return None
        return {"account_id": uuid.UUID(p["sub"]), "org_id": uuid.UUID(p["org"]), "role": p["role"],
                "subject_id": uuid.UUID(p["sid"])}
    except (jwt.PyJWTError, KeyError, ValueError):
        return None
