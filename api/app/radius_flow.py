from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.audit import audit
from app.ldap_auth import authenticate_ldap
from app.mfa_channels import (
    express_usable,
    push_wait_seconds,
    resolve_mfa_scenario,
    totp_usable,
)
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
from app.policy_resolve import default_policy, resolve_policy
from app.settings_service import ldap_config
from app.token_service import touch_last_used
from app.tasks import send_expressms_otp, send_telegram_otp

VALID_METHODS = ("NONE", "TOTP", "EXPRESSMS", "TELEGRAM")
OTP_ONLY_SCHEMES = frozenset({"otp_only", "token", "pap"})


def find_radius_user(db: Session, username: str) -> User | None:
    raw = (username or "").strip()
    if not raw:
        return None
    names = [raw]
    if "\\" in raw:
        names.append(raw.rsplit("\\", 1)[-1].strip())
    if "@" in raw:
        names.append(raw.split("@", 1)[0].strip())
    seen: set[str] = set()
    for name in names:
        key = name.lower()
        if not name or key in seen:
            continue
        seen.add(key)
        user = db.query(User).filter(User.ad_username.ilike(name)).first()
        if user:
            return user
    return None


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
    policy = resolve_policy(db, nas_ip)
    scheme = (policy.radius_scheme_preference or "challenge").strip().lower()
    if scheme in OTP_ONLY_SCHEMES:
        return _otp_only(db, username, password, policy, nas_ip=nas_ip)

    cfg = ldap_config(db)
    if not authenticate_ldap(username, password, cfg):
        audit(db, "LDAP_FAIL", username=username, nas_ip=nas_ip, reason="invalid_credentials")
        return {"decision": "reject", "reply_message": "Invalid credentials"}

    user = get_or_create_user(db, username)
    audit(db, "LDAP_OK", user_id=user.id, username=username, nas_ip=nas_ip)

    if not policy.require_2fa:
        touch_last_used(user, db)
        audit(db, "RADIUS_ACCEPT", user_id=user.id, username=username, reason="2fa_disabled", nas_ip=nas_ip)
        return {"decision": "accept", "reply_message": "OK"}

    return _mfa_after_ldap(db, user, policy, password="", nas_ip=nas_ip, otp_only=False)


def _otp_only(
    db: Session, username: str, password: str, policy: Policy, nas_ip: str | None = None
) -> dict:
    """NAS (Check Point / UAG) уже проверил 1-й фактор (LDAP).

    На RADIUS приходит только 2-й фактор:
    - TOTP: User-Password = код;
    - Express push: Approve/Deny (поле пароля не проверяем, hold до ответа).
    """
    user = find_radius_user(db, username)
    if not user:
        audit(db, "RADIUS_REJECT", username=username, nas_ip=nas_ip, reason="unknown_user")
        return {"decision": "reject", "reply_message": "Unknown user"}
    if not user.token_active:
        audit(db, "RADIUS_REJECT", user_id=user.id, username=user.ad_username, nas_ip=nas_ip, reason="token_inactive")
        return {"decision": "reject", "reply_message": "Token disabled"}
    if not policy.require_2fa:
        touch_last_used(user, db)
        audit(db, "RADIUS_ACCEPT", user_id=user.id, username=user.ad_username, reason="2fa_disabled", nas_ip=nas_ip)
        return {"decision": "accept", "reply_message": "OK"}
    return _mfa_after_ldap(db, user, policy, password=password or "", nas_ip=nas_ip, otp_only=True)


def _try_totp_accept_otp_only(
    db: Session,
    user: User,
    policy: Policy,
    password: str,
    *,
    nas_ip: str | None,
    reason: str,
) -> dict | None:
    """otp_only: User-Password уже содержит TOTP (повтор после таймаута push)."""
    pwd = (password or "").strip()
    if not pwd or not totp_usable(user, policy):
        return None
    if not verify_totp(user.totp_secret_encrypted, pwd, policy.totp_window_steps):
        return None
    touch_last_used(user, db)
    audit(db, "OTP_OK", user_id=user.id, username=user.ad_username, method="TOTP", nas_ip=nas_ip)
    audit(db, "RADIUS_ACCEPT", user_id=user.id, username=user.ad_username, reason=reason, nas_ip=nas_ip)
    return {"decision": "accept", "reply_message": "OK"}


def _mfa_after_ldap(
    db: Session,
    user: User,
    policy: Policy,
    *,
    password: str,
    nas_ip: str | None,
    otp_only: bool,
) -> dict:
    scenario = resolve_mfa_scenario(policy)
    can_totp = totp_usable(user, policy)
    can_express = express_usable(user, policy)

    if scenario in ("express_push", "express_push_then_totp") and can_express:
        if scenario == "express_push_then_totp" and otp_only:
            from app.express_push import clear_push_fallback, push_fallback_active

            if push_fallback_active(user.id):
                fast = _try_totp_accept_otp_only(
                    db, user, policy, password, nas_ip=nas_ip, reason="express_push_fallback_totp"
                )
                if fast:
                    clear_push_fallback(user.id)
                    return fast
        return _express_push_hold(
            db,
            user,
            policy,
            nas_ip=nas_ip,
            password=password,
            otp_only=otp_only,
            then_totp=(scenario == "express_push_then_totp"),
        )

    if can_totp:
        return _totp_path(db, user, policy, password=password, nas_ip=nas_ip, otp_only=otp_only)

    # legacy: текстовый OTP Express/Telegram при challenge (сценарий totp, но канала TOTP нет)
    if not otp_only and scenario == "totp":
        mode = (getattr(policy, "expressms_mode", None) or "otp").strip().lower()
        if (
            mode == "otp"
            and user.expressms_id
            and _method_allowed(policy, "EXPRESSMS")
            and user.otp_method == "EXPRESSMS"
        ):
            otp = generate_numeric_otp()
            salt = new_state_token()
            otp_hash = hash_otp(otp, salt) + ":" + salt
            send_expressms_otp.delay(user.expressms_id, otp)
            audit(db, "SEND_EXPRESSMS", user_id=user.id, username=user.ad_username)
            return _open_challenge(db, user, policy, "EXPRESSMS", otp_hash, nas_ip=nas_ip)
        if user.telegram_chat_id and _method_allowed(policy, "TELEGRAM") and user.otp_method == "TELEGRAM":
            otp = generate_numeric_otp()
            salt = new_state_token()
            otp_hash = hash_otp(otp, salt) + ":" + salt
            send_telegram_otp.delay(user.telegram_chat_id, otp)
            audit(db, "SEND_TELEGRAM", user_id=user.id, username=user.ad_username)
            return _open_challenge(db, user, policy, "TELEGRAM", otp_hash, nas_ip=nas_ip)

    audit(
        db,
        "RADIUS_REJECT",
        user_id=user.id,
        username=user.ad_username,
        nas_ip=nas_ip,
        reason="not_enrolled",
    )
    return {"decision": "reject", "reply_message": "2FA is not enrolled"}


def _totp_path(
    db: Session,
    user: User,
    policy: Policy,
    *,
    password: str,
    nas_ip: str | None,
    otp_only: bool,
) -> dict:
    if otp_only:
        if verify_totp(user.totp_secret_encrypted, (password or "").strip(), policy.totp_window_steps):
            touch_last_used(user, db)
            audit(db, "OTP_OK", user_id=user.id, username=user.ad_username, method="TOTP", nas_ip=nas_ip)
            audit(db, "RADIUS_ACCEPT", user_id=user.id, username=user.ad_username, reason="otp_only", nas_ip=nas_ip)
            return {"decision": "accept", "reply_message": "OK"}
        audit(db, "OTP_FAIL", user_id=user.id, username=user.ad_username, method="TOTP", nas_ip=nas_ip)
        return {"decision": "reject", "reply_message": "Invalid OTP"}
    return _open_challenge(db, user, policy, "TOTP", None, nas_ip=nas_ip)


def _express_push_hold(
    db: Session,
    user: User,
    policy: Policy,
    *,
    nas_ip: str | None = None,
    password: str = "",
    otp_only: bool = True,
    then_totp: bool = False,
) -> dict:
    """2-й фактор = только push. LDAP/пароль CP уже проверил (otp_only).

    User-Password в пакете не используется, кроме fallback express_push_then_totp.
    """
    from app.express_push import (
        clear_push_fallback,
        mark_push_fallback,
        request_bot_push,
        wait_decision,
    )

    state = new_state_token()
    wait_s = push_wait_seconds(policy)
    ttl = max(policy.challenge_ttl_seconds, wait_s + 30)
    row = OtpChallenge(
        state_token=state,
        user_id=user.id,
        method_used="EXPRESSMS",
        otp_hash=None,
        otp_expires_at=None,
        expires_at=challenge_expiry(ttl),
    )
    db.add(row)
    db.commit()
    audit(db, "EXPRESS_PUSH_SEND", user_id=user.id, username=user.ad_username, nas_ip=nas_ip)
    sent = request_bot_push(
        state=state,
        username=user.ad_username,
        email=user.ldap_email or "",
        chat_id=user.expressms_id or "",
    )
    if not sent:
        row.consumed = True
        db.commit()
        if then_totp and totp_usable(user, policy):
            audit(
                db,
                "EXPRESS_PUSH_FALLBACK_TOTP",
                user_id=user.id,
                username=user.ad_username,
                nas_ip=nas_ip,
                reason="send_failed",
            )
            return _totp_path(db, user, policy, password=password, nas_ip=nas_ip, otp_only=otp_only)
        audit(db, "RADIUS_REJECT", user_id=user.id, username=user.ad_username, nas_ip=nas_ip, reason="express_push_send")
        return {"decision": "reject", "reply_message": "Push was not sent"}

    # Kontur-like UX: один RADIUS-запрос «висит» до Approve/Deny, без Access-Challenge.
    audit(
        db,
        "EXPRESS_PUSH_HOLD",
        user_id=user.id,
        username=user.ad_username,
        nas_ip=nas_ip,
        reason=f"wait_{wait_s}s",
    )
    result = wait_decision(state, wait_s)
    row.consumed = True
    db.commit()
    if result == "approve":
        clear_push_fallback(user.id)
        touch_last_used(user, db)
        audit(db, "OTP_OK", user_id=user.id, username=user.ad_username, method="EXPRESSMS", nas_ip=nas_ip)
        audit(db, "RADIUS_ACCEPT", user_id=user.id, username=user.ad_username, reason="express_push", nas_ip=nas_ip)
        return {"decision": "accept", "reply_message": "OK"}

    # Deny — явный отказ, без fallback на TOTP
    if result == "deny":
        audit(db, "RADIUS_REJECT", user_id=user.id, username=user.ad_username, nas_ip=nas_ip, reason="express_push_deny")
        return {"decision": "reject", "reply_message": "Push denied"}

    # timeout
    if then_totp and totp_usable(user, policy):
        mark_push_fallback(user.id, wait_s + 60)
        fast = _try_totp_accept_otp_only(
            db, user, policy, password, nas_ip=nas_ip, reason="express_push_fallback_totp"
        )
        if fast:
            clear_push_fallback(user.id)
            return fast
        audit(
            db,
            "EXPRESS_PUSH_FALLBACK_TOTP",
            user_id=user.id,
            username=user.ad_username,
            nas_ip=nas_ip,
            reason="timeout",
        )
        if otp_only:
            return _open_challenge(db, user, policy, "TOTP", None, nas_ip=nas_ip)
        return _totp_path(db, user, policy, password=password, nas_ip=nas_ip, otp_only=otp_only)

    audit(db, "RADIUS_REJECT", user_id=user.id, username=user.ad_username, nas_ip=nas_ip, reason="express_push_timeout")
    return {"decision": "reject", "reply_message": "Push timed out"}


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

    policy = resolve_policy(db, nas_ip)
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
