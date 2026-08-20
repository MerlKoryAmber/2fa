import secrets
from datetime import timedelta, timezone

from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.config import settings
from app.models import EnrollmentInvite, User
from app.otp import encrypt_totp_secret, generate_totp_secret, utcnow
from app.radius_flow import default_policy
from app.token_service import ensure_token_serial


def new_invite_token() -> str:
    return secrets.token_urlsafe(32)


def create_invite(db: Session, user: User, admin_username: str, email_to: str, ttl_seconds: int) -> EnrollmentInvite:
    now = utcnow()
    row = EnrollmentInvite(
        token=new_invite_token(),
        user_id=user.id,
        created_by=admin_username,
        email_to=email_to,
        expires_at=now + timedelta(seconds=ttl_seconds),
        created_at=now,
    )
    db.add(row)
    return row


def ensure_totp_pending(user: User, db: Session) -> str:
    """Generate TOTP secret if missing; leave totp_confirmed false."""
    if user.totp_secret_encrypted:
        from app.crypto import decrypt_secret

        return decrypt_secret(user.totp_secret_encrypted)
    secret = generate_totp_secret()
    user.totp_secret_encrypted = encrypt_totp_secret(secret)
    user.totp_confirmed = False
    user.otp_method = "TOTP"
    ensure_token_serial(user, db)
    return secret


def _aware(dt):
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def get_valid_invite(db: Session, token: str) -> EnrollmentInvite | None:
    row = db.query(EnrollmentInvite).filter(EnrollmentInvite.token == token).first()
    if not row:
        return None
    if row.consumed_at is not None:
        return None
    if utcnow() > _aware(row.expires_at):
        return None
    return row


def consume_invite(row: EnrollmentInvite, db: Session) -> None:
    row.consumed_at = utcnow()
    db.commit()


def invite_ttl(db: Session) -> int:
    return default_policy(db).enroll_invite_ttl_seconds


def username_matches_invite(user: User, username: str) -> bool:
    u = (username or "").strip()
    if not u:
        return False
    if u.lower() == user.ad_username.lower():
        return True
    if "@" in u:
        local = u.split("@", 1)[0].strip()
        if local.lower() == user.ad_username.lower():
            return True
    if "\\" in u:
        local = u.split("\\", 1)[-1].strip()
        if local.lower() == user.ad_username.lower():
            return True
    return False


def create_enroll_proof(invite_token: str) -> str:
    exp = utcnow() + timedelta(minutes=30)
    return jwt.encode(
        {"sub": invite_token, "typ": "enroll", "exp": exp},
        settings.jwt_secret,
        algorithm="HS256",
    )


def verify_enroll_proof(proof: str, invite_token: str) -> bool:
    if not proof:
        return False
    try:
        payload = jwt.decode(proof, settings.jwt_secret, algorithms=["HS256"])
    except JWTError:
        return False
    return payload.get("typ") == "enroll" and payload.get("sub") == invite_token
