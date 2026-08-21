from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.audit import audit
from app.config import settings
from app.ldap_auth import authenticate_ldap
from app.models import OtpChallenge, Policy, User
from app.otp import (
    challenge_expiry,
    generate_numeric_otp,
    hash_otp,
    new_state_token,
    otp_hash_matches,
    utcnow,
    verify_totp,
)
from app.settings_service import ldap_config
from app.token_service import touch_last_used
from app.tasks import send_expressms_otp, send_telegram_otp

VALID_METHODS = ("NONE", "TOTP", "EXPRESSMS", "TELEGRAM")


def default_policy(db: Session) -> Policy:
    row = db.query(Policy).order_by(Policy.id.asc()).first()
    if row:
        return row
    row = Policy()
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_or_create_user(db: Session, username: str) -> User:
    user = db.query(User).filter(User.ad_username == username).first()
    if user:
        return user
    user = User(ad_username=username, otp_method="NONE")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _method_allowed(policy: Policy, method: str) -> bool:
    allowed = {m.strip().upper() for m in policy.allowed_second_factors.split(",") if m.strip()}
    return method.upper() in allowed


def handle_access_request(
    db: Session, username: str, password: str, state: str | None = None, nas_ip: str | None = None
) -> dict:
    if state:
        return _complete(db, username, password, state, nas_ip=nas_ip)
    return _start(db, username, password, nas_ip=nas_ip)


def _start(db: Session, username: str, password: str, nas_ip: str | None = None) -> dict:
    cfg = ldap_config(db)
    if not authenticate_ldap(username, password, cfg):
        audit(db, "LDAP_FAIL", username=username, nas_ip=nas_ip, reason="invalid_credentials")
        return {"decision": "reject", "reply_message": "Invalid credentials"}

    user = get_or_create_user(db, username)
    audit(db, "LDAP_OK", user_id=user.id, username=username, nas_ip=nas_ip)
    policy = default_policy(db)

    if not policy.require_2fa:
        touch_last_used(user, db)
        audit(db, "RADIUS_ACCEPT", user_id=user.id, username=username, reason="2fa_disabled", nas_ip=nas_ip)
        return {"decision": "accept", "reply_message": "OK"}

    method = user.otp_method
    if method == "TOTP" and user.totp_secret_encrypted and user.totp_confirmed and _method_allowed(policy, "TOTP"):
        return _open_challenge(db, user, policy, "TOTP", None, nas_ip=nas_ip)
    if method == "EXPRESSMS" and user.expressms_id and _method_allowed(policy, "EXPRESSMS"):
        otp = generate_numeric_otp()
        salt = new_state_token()
        otp_hash = hash_otp(otp, salt) + ":" + salt
        send_expressms_otp.delay(user.expressms_id, otp)
        audit(db, "SEND_EXPRESSMS", user_id=user.id, username=username)
        return _open_challenge(db, user, policy, "EXPRESSMS", otp_hash, nas_ip=nas_ip)
    if method == "TELEGRAM" and user.telegram_chat_id and _method_allowed(policy, "TELEGRAM"):
        otp = generate_numeric_otp()
        salt = new_state_token()
        otp_hash = hash_otp(otp, salt) + ":" + salt
        send_telegram_otp.delay(user.telegram_chat_id, otp)
        audit(db, "SEND_TELEGRAM", user_id=user.id, username=username)
        return _open_challenge(db, user, policy, "TELEGRAM", otp_hash, nas_ip=nas_ip)

    audit(db, "RADIUS_REJECT", user_id=user.id, username=username, reason="not_enrolled", nas_ip=nas_ip)
    return {"decision": "reject", "reply_message": "2FA is not enrolled"}


def _open_challenge(
    db: Session, user: User, policy: Policy, method: str, otp_hash: str | None, nas_ip: str | None = None
) -> dict:
    state = new_state_token()
    ttl = policy.challenge_ttl_seconds
    otp_ttl = policy.otp_ttl_seconds
    now = utcnow()
    row = OtpChallenge(
        state_token=state,
        user_id=user.id,
        method_used=method,
        otp_hash=otp_hash,
        otp_expires_at=(now + timedelta(seconds=otp_ttl)) if otp_hash else None,
        expires_at=challenge_expiry(ttl),
    )
    db.add(row)
    db.commit()
    messages = {
        "TOTP": "Enter TOTP code",
        "EXPRESSMS": "Enter OTP from ExpressMS",
        "TELEGRAM": "Enter OTP from Telegram",
    }
    msg = messages.get(method, "Enter OTP")
    audit(db, "RADIUS_CHALLENGE", user_id=user.id, username=user.ad_username, method=method, nas_ip=nas_ip)
    return {"decision": "challenge", "state": state, "reply_message": msg}


def _consume(row: OtpChallenge, db: Session) -> None:
    row.consumed = True
    db.commit()


def _complete(db: Session, username: str, otp: str, state: str, nas_ip: str | None = None) -> dict:
    row = db.query(OtpChallenge).filter(OtpChallenge.state_token == state).first()
    if not row:
        audit(db, "OTP_FAIL", username=username, reason="unknown_state")
        return {"decision": "reject", "reply_message": "Invalid or expired challenge"}
    if row.consumed:
        audit(db, "OTP_FAIL", username=username, reason="replay", user_id=row.user_id)
        return {"decision": "reject", "reply_message": "Challenge already used"}

    now = utcnow()
    if _aware(row.expires_at) < now:
        _consume(row, db)
        audit(db, "OTP_FAIL", user_id=row.user_id, username=username, reason="expired")
        return {"decision": "reject", "reply_message": "Challenge expired"}

    user = db.query(User).filter(User.id == row.user_id).first()
    if not user or (username and user.ad_username != username):
        audit(db, "OTP_FAIL", username=username, reason="user_mismatch")
        return {"decision": "reject", "reply_message": "Invalid challenge"}

    policy = default_policy(db)
    row.attempts_count += 1
    db.commit()
    if row.attempts_count > policy.max_otp_attempts_per_challenge:
        row.consumed = True
        db.commit()
        audit(db, "OTP_FAIL", user_id=user.id, username=username, reason="attempts")
        return {"decision": "reject", "reply_message": "Too many attempts"}

    ok = False
    if row.method_used == "TOTP" and user.totp_secret_encrypted:
        ok = verify_totp(user.totp_secret_encrypted, otp.strip(), policy.totp_window_steps)
    elif row.method_used in ("EXPRESSMS", "TELEGRAM") and row.otp_hash:
        if row.otp_expires_at and _aware(row.otp_expires_at) < now:
            audit(db, "OTP_FAIL", user_id=user.id, username=username, reason="otp_ttl")
            return {"decision": "reject", "reply_message": "OTP expired"}
        digest, salt = row.otp_hash.split(":", 1)
        ok = otp_hash_matches(otp.strip(), salt, digest)

    if not ok:
        audit(db, "OTP_FAIL", user_id=user.id, username=username, method=row.method_used)
        return {"decision": "reject", "reply_message": "Invalid OTP"}

    row.consumed = True
    db.commit()
    touch_last_used(user, db)
    audit(db, "OTP_OK", user_id=user.id, username=username, method=row.method_used)
    audit(db, "RADIUS_ACCEPT", user_id=user.id, username=username, nas_ip=nas_ip)
    return {"decision": "accept", "reply_message": "OK"}
