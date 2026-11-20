"""TOTP (RFC 6238) helpers. Secrets are stored Fernet-encrypted in users.mfa_secret_enc."""
import pyotp

from app.modules.compliance.crypto import decrypt, encrypt

ISSUER = "LEADEX AI"


def new_secret() -> tuple[str, str]:
    secret = pyotp.random_base32()
    return secret, encrypt(secret)


def otpauth_uri(secret: str, email: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=ISSUER)


def verify(secret_enc: str | None, code: str | None) -> bool:
    if not secret_enc or not code:
        return False
    code = code.strip().replace(" ", "")
    if not code.isdigit():
        return False
    return pyotp.TOTP(decrypt(secret_enc)).verify(code, valid_window=1)
