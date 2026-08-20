import base64

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.audit import audit
from app.db import get_db
from app.enroll_service import (
    consume_invite,
    create_enroll_proof,
    get_valid_invite,
    username_matches_invite,
    verify_enroll_proof,
)
from app.ldap_auth import authenticate_ldap
from app.models import User
from app.otp import totp_qr_png_bytes, totp_uri, verify_totp
from app.radius_flow import default_policy
from app.settings_service import ldap_config

router = APIRouter(prefix="/api/public/enroll", tags=["public-enroll"])


class EnrollAuthIn(BaseModel):
    username: str
    password: str


class EnrollConfirmIn(BaseModel):
    code: str
    expressms_id: str | None = None
    telegram_chat_id: str | None = None
    enroll_proof: str


def _qr_payload(user: User, secret: str) -> dict:
    uri = totp_uri(secret, user.ad_username)
    png = totp_qr_png_bytes(uri)
    return {
        "username": user.ad_username,
        "otpauth_uri": uri,
        "secret": secret,
        "qr_png_base64": base64.b64encode(png).decode(),
    }


def _invite_user(db: Session, token: str) -> tuple:
    invite = get_valid_invite(db, token)
    if not invite:
        raise HTTPException(404, "Ссылка недействительна или истекла")
    user = db.query(User).filter(User.id == invite.user_id).first()
    if not user or not user.totp_secret_encrypted:
        raise HTTPException(404, "Enrollment not ready")
    return invite, user


@router.get("/{token}")
def get_enroll_page(token: str, db: Session = Depends(get_db)):
    invite, user = _invite_user(db, token)
    return {
        "username": user.ad_username,
        "expires_at": invite.expires_at.isoformat(),
        "auth_required": True,
    }


@router.post("/{token}/auth")
def auth_enroll(token: str, body: EnrollAuthIn, db: Session = Depends(get_db)):
    invite, user = _invite_user(db, token)
    if not username_matches_invite(user, body.username):
        audit(db, "ENROLL_AUTH_FAIL", user_id=user.id, username=body.username, reason="username_mismatch")
        raise HTTPException(401, "Неверный логин или пароль")
    cfg = ldap_config(db)
    if not authenticate_ldap(body.username.strip(), body.password, cfg):
        audit(db, "ENROLL_AUTH_FAIL", user_id=user.id, username=body.username, reason="ldap_fail")
        raise HTTPException(401, "Неверный логин или пароль")
    from app.crypto import decrypt_secret

    secret = decrypt_secret(user.totp_secret_encrypted)
    payload = _qr_payload(user, secret)
    payload["expires_at"] = invite.expires_at.isoformat()
    payload["enroll_proof"] = create_enroll_proof(token)
    audit(db, "ENROLL_AUTH_OK", user_id=user.id, username=user.ad_username)
    return payload


@router.post("/{token}")
def confirm_enroll(token: str, body: EnrollConfirmIn, db: Session = Depends(get_db)):
    if not verify_enroll_proof(body.enroll_proof, token):
        raise HTTPException(401, "Сначала войдите по логину и паролю")
    invite, user = _invite_user(db, token)
    policy = default_policy(db)
    if not verify_totp(user.totp_secret_encrypted, body.code.strip(), policy.totp_window_steps):
        raise HTTPException(400, "Неверный код TOTP")
    user.totp_confirmed = True
    user.otp_method = "TOTP"
    if body.expressms_id and body.expressms_id.strip():
        user.expressms_id = body.expressms_id.strip()
    if body.telegram_chat_id and body.telegram_chat_id.strip():
        user.telegram_chat_id = body.telegram_chat_id.strip()
    from app.token_service import ensure_token_serial

    ensure_token_serial(user, db)
    consume_invite(invite, db)
    audit(db, "ENROLL_INVITE_OK", user_id=user.id, username=user.ad_username)
    return {"ok": True}
