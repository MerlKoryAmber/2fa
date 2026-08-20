import hashlib
import hmac
import io
import secrets
from datetime import datetime, timedelta, timezone

import pyotp
import qrcode

from app.config import settings
from app.crypto import decrypt_secret, encrypt_secret


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def hash_otp(otp: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{otp}".encode()).hexdigest()


def otp_hash_matches(otp: str, salt: str, stored: str) -> bool:
    return hmac.compare_digest(hash_otp(otp, salt), stored)


def generate_numeric_otp(digits: int = 6) -> str:
    n = secrets.randbelow(10**digits)
    return str(n).zfill(digits)


def new_state_token() -> str:
    return secrets.token_urlsafe(32)


def generate_totp_secret() -> str:
    return pyotp.random_base32()


def totp_uri(secret: str, username: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=username, issuer_name=settings.totp_issuer)


def totp_qr_png_bytes(uri: str) -> bytes:
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def encrypt_totp_secret(secret: str) -> str:
    return encrypt_secret(secret)


def verify_totp(encrypted_secret: str, code: str, window: int) -> bool:
    secret = decrypt_secret(encrypted_secret)
    totp = pyotp.TOTP(secret)
    return bool(totp.verify(code, valid_window=window))


def challenge_expiry(seconds: int) -> datetime:
    return utcnow() + timedelta(seconds=seconds)
