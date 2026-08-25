import base64

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.audit import audit
from app.audit_labels import audit_event_label, format_audit_meta
from app.db import get_db
from app.models import Admin, AuditEvent, Policy, User
from app.otp import encrypt_totp_secret, generate_totp_secret, totp_qr_png_bytes, totp_uri, verify_totp
from app.radius_flow import VALID_METHODS, default_policy
from app.policy_resolve import policy_public, resolve_policy
from app.routers.auth import current_admin, require_roles
from app.rbac import ROLE_ADMIN, ROLE_AUDITOR, ROLE_OPERATOR
from app.dashboard import build_dashboard
from app.enroll_service import create_invite, ensure_totp_pending, invite_ttl
from app.ldap_sync import run_ldap_sync
from app.mail_service import send_invite_email
from app.mfa_channels import sync_otp_method_from_channels
from app.settings_service import app_public_base_url
from app.token_service import ensure_token_serial, find_by_serial, list_tokens, revoke_token, set_token_active
from app.user_service import list_users as filter_users

router = APIRouter(prefix="/api", tags=["admin"])


class UserPatch(BaseModel):
    otp_method: str | None = None
    expressms_id: str | None = None
    telegram_chat_id: str | None = None


class PolicyPatch(BaseModel):
    name: str | None = None
    scope: str | None = None
    require_2fa: bool | None = None
    allowed_second_factors: str | None = None
    totp_window_steps: int | None = None
    otp_ttl_seconds: int | None = None
    max_otp_attempts_per_challenge: int | None = None
    challenge_ttl_seconds: int | None = None
    enroll_invite_ttl_seconds: int | None = None
    radius_scheme_preference: str | None = None
    expressms_mode: str | None = None
    mfa_scenario: str | None = None
    push_wait_seconds: int | None = None


class PolicyCreate(BaseModel):
    name: str = "Новая"
    scope: str = "0.0.0.0/32"
    copy_from_default: bool = True
    require_2fa: bool | None = None
    allowed_second_factors: str | None = None
    totp_window_steps: int | None = None
    otp_ttl_seconds: int | None = None
    max_otp_attempts_per_challenge: int | None = None
    challenge_ttl_seconds: int | None = None
    enroll_invite_ttl_seconds: int | None = None
    radius_scheme_preference: str | None = None
    expressms_mode: str | None = None
    mfa_scenario: str | None = None
    push_wait_seconds: int | None = None


class TotpConfirm(BaseModel):
    code: str


class TokenPatch(BaseModel):
    active: bool | None = None
    description: str | None = None
    revoke: bool | None = None


@router.get("/users")
def list_users(
    ad: str | None = None,
    email: str | None = None,
    method: str | None = None,
    totp: str | None = None,
    db: Session = Depends(get_db),
    _: Admin = Depends(require_roles(ROLE_ADMIN, ROLE_OPERATOR)),
):
    return filter_users(db, ad=ad, email=email, method=method, totp=totp)


@router.patch("/users/{user_id}")
def patch_user(
    user_id: int,
    body: UserPatch,
    db: Session = Depends(get_db),
    admin: Admin = Depends(require_roles(ROLE_ADMIN)),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    if body.otp_method is not None:
        if body.otp_method not in VALID_METHODS:
            raise HTTPException(400, "Invalid method")
        user.otp_method = body.otp_method
    if body.expressms_id is not None:
        user.expressms_id = body.expressms_id or None
    if body.telegram_chat_id is not None:
        user.telegram_chat_id = body.telegram_chat_id or None
    # порядок входа задаёт политика; otp_method — legacy-метка по каналам
    if body.otp_method is None:
        sync_otp_method_from_channels(user)
    if user.otp_method and user.otp_method != "NONE":
        ensure_token_serial(user, db)
    db.commit()
    audit(db, "USER_PATCH", user_id=user.id, username=user.ad_username, by=admin.username)
    return {"ok": True}


@router.post("/users/sync-ldap")
def sync_ldap_users(db: Session = Depends(get_db), admin: Admin = Depends(require_roles(ROLE_ADMIN))):
    out = run_ldap_sync(db, by=admin.username)
    if not out.get("ok"):
        raise HTTPException(400, out.get("error", "LDAP sync failed"))
    return {"ok": True, "created": out["created"], "total": out["total"]}


def _totp_issue_payload(user: User, secret: str) -> dict:
    uri = totp_uri(secret, user.ad_username)
    png = totp_qr_png_bytes(uri)
    return {
        "otpauth_uri": uri,
        "secret": secret,
        "qr_png_base64": base64.b64encode(png).decode(),
        "totp_confirmed": user.totp_confirmed,
    }


def _create_enroll_invite(user: User, db: Session, admin: Admin, request: Request):
    ensure_totp_pending(user, db)
    ttl = invite_ttl(db)
    email_to = user.ldap_email or ""
    invite = create_invite(db, user, admin.username, email_to, ttl)
    db.commit()
    base = app_public_base_url(db) or str(request.base_url).rstrip("/")
    invite_url = f"{base}/enroll/{invite.token}"
    return invite, invite_url


@router.post("/users/{user_id}/invite-link")
def create_invite_link(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    admin: Admin = Depends(require_roles(ROLE_ADMIN, ROLE_OPERATOR)),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    invite, invite_url = _create_enroll_invite(user, db, admin, request)
    audit(
        db,
        "ENROLL_INVITE_LINK",
        user_id=user.id,
        username=user.ad_username,
        by=admin.username,
    )
    return {"ok": True, "invite_url": invite_url, "expires_at": invite.expires_at.isoformat()}


@router.post("/users/{user_id}/invite")
def send_invite(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    admin: Admin = Depends(require_roles(ROLE_ADMIN, ROLE_OPERATOR)),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    if not user.ldap_email:
        raise HTTPException(400, "Нет email — загрузите пользователя из LDAP или укажите почту")
    invite, invite_url = _create_enroll_invite(user, db, admin, request)
    mail_result = send_invite_email(db, user.ldap_email, user.ad_username, invite_url, invite.expires_at)
    audit(
        db,
        "ENROLL_INVITE",
        user_id=user.id,
        username=user.ad_username,
        by=admin.username,
        email=user.ldap_email,
        dry_run=mail_result.get("dry_run"),
    )
    return {"ok": True, "invite_url": invite_url, "expires_at": invite.expires_at.isoformat(), "mail": mail_result}


@router.post("/users/{user_id}/totp/issue")
def issue_totp(user_id: int, db: Session = Depends(get_db), admin: Admin = Depends(require_roles(ROLE_ADMIN))):
    """Выпустить TOTP без confirm — для ручной пересылки пользователю."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    secret = ensure_totp_pending(user, db)
    db.commit()
    audit(db, "TOTP_ISSUE", user_id=user.id, username=user.ad_username, by=admin.username)
    return _totp_issue_payload(user, secret)


@router.post("/users/{user_id}/totp/enroll")
def enroll_totp(user_id: int, db: Session = Depends(get_db), _: Admin = Depends(require_roles(ROLE_ADMIN))):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    secret = generate_totp_secret()
    user.totp_secret_encrypted = encrypt_totp_secret(secret)
    user.totp_confirmed = False
    user.otp_method = "TOTP"
    ensure_token_serial(user, db)
    db.commit()
    uri = totp_uri(secret, user.ad_username)
    png = totp_qr_png_bytes(uri)
    return {
        "otpauth_uri": uri,
        "secret": secret,
        "qr_png_base64": base64.b64encode(png).decode(),
    }


@router.post("/users/{user_id}/totp/confirm")
def confirm_totp(
    user_id: int,
    body: TotpConfirm,
    db: Session = Depends(get_db),
    _: Admin = Depends(require_roles(ROLE_ADMIN)),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.totp_secret_encrypted:
        raise HTTPException(404, "Enrollment not started")
    policy = default_policy(db)
    if not verify_totp(user.totp_secret_encrypted, body.code.strip(), policy.totp_window_steps):
        raise HTTPException(400, "Invalid TOTP")
    user.totp_confirmed = True
    ensure_token_serial(user, db)
    db.commit()
    audit(db, "TOTP_ENROLL_OK", user_id=user.id, username=user.ad_username)
    return {"ok": True}


@router.get("/policies")
def get_policies(db: Session = Depends(get_db), _: Admin = Depends(require_roles(ROLE_ADMIN))):
    rows = db.query(Policy).order_by(Policy.id.asc()).all()
    if not rows:
        rows = [default_policy(db)]
    default = default_policy(db)
    return {
        "items": [policy_public(p) for p in rows],
        "default_id": default.id,
    }


@router.post("/policies")
def create_policy(
    body: PolicyCreate,
    db: Session = Depends(get_db),
    admin: Admin = Depends(require_roles(ROLE_ADMIN)),
):
    scope = (body.scope or "").strip() or "0.0.0.0/32"
    if scope == "*":
        raise HTTPException(400, "Новая политика не может иметь область «все клиенты» (*). Измените существующую или укажите IP/CIDR.")
    base = default_policy(db) if body.copy_from_default else None
    row = Policy(
        name=(body.name or "Новая").strip() or "Новая",
        scope=scope,
        require_2fa=body.require_2fa if body.require_2fa is not None else (base.require_2fa if base else True),
        allowed_second_factors=body.allowed_second_factors
        if body.allowed_second_factors is not None
        else (base.allowed_second_factors if base else "TOTP,EXPRESSMS,TELEGRAM"),
        totp_window_steps=body.totp_window_steps
        if body.totp_window_steps is not None
        else (base.totp_window_steps if base else 1),
        otp_ttl_seconds=body.otp_ttl_seconds if body.otp_ttl_seconds is not None else (base.otp_ttl_seconds if base else 60),
        max_otp_attempts_per_challenge=body.max_otp_attempts_per_challenge
        if body.max_otp_attempts_per_challenge is not None
        else (base.max_otp_attempts_per_challenge if base else 5),
        challenge_ttl_seconds=body.challenge_ttl_seconds
        if body.challenge_ttl_seconds is not None
        else (base.challenge_ttl_seconds if base else 120),
        enroll_invite_ttl_seconds=body.enroll_invite_ttl_seconds
        if body.enroll_invite_ttl_seconds is not None
        else (base.enroll_invite_ttl_seconds if base else 86400),
        radius_scheme_preference=body.radius_scheme_preference
        if body.radius_scheme_preference is not None
        else (base.radius_scheme_preference if base else "challenge"),
        expressms_mode=body.expressms_mode
        if body.expressms_mode is not None
        else (base.expressms_mode if base else "otp"),
        mfa_scenario=body.mfa_scenario
        if body.mfa_scenario is not None
        else (getattr(base, "mfa_scenario", None) if base else None) or "totp",
        push_wait_seconds=body.push_wait_seconds
        if body.push_wait_seconds is not None
        else (getattr(base, "push_wait_seconds", None) if base else None) or 60,
    )
    # синхрон legacy expressms_mode с сценарием
    if row.mfa_scenario in ("express_push", "express_push_then_totp"):
        row.expressms_mode = "push"
    elif body.expressms_mode is None:
        row.expressms_mode = "otp"
    db.add(row)
    db.commit()
    db.refresh(row)
    audit(db, "POLICY_CREATE", username=admin.username, policy_id=row.id, scope=row.scope)
    return policy_public(row)


@router.patch("/policies/{policy_id}")
def patch_policy(
    policy_id: int,
    body: PolicyPatch,
    db: Session = Depends(get_db),
    admin: Admin = Depends(require_roles(ROLE_ADMIN)),
):
    p = db.query(Policy).filter(Policy.id == policy_id).first()
    if not p:
        raise HTTPException(404, "Policy not found")
    data = body.model_dump(exclude_unset=True)
    if "scope" in data and data["scope"] is not None:
        data["scope"] = str(data["scope"]).strip() or "*"
    if "mfa_scenario" in data and data["mfa_scenario"] is not None:
        sc = str(data["mfa_scenario"]).strip().lower()
        if sc not in ("totp", "express_push", "express_push_then_totp"):
            raise HTTPException(400, "Invalid mfa_scenario")
        data["mfa_scenario"] = sc
        if "expressms_mode" not in data:
            data["expressms_mode"] = "push" if sc.startswith("express_push") else "otp"
    if "push_wait_seconds" in data and data["push_wait_seconds"] is not None:
        data["push_wait_seconds"] = max(5, min(int(data["push_wait_seconds"]), 300))
    for field, value in data.items():
        setattr(p, field, value)
    db.commit()
    audit(db, "POLICY_PATCH", username=admin.username, policy_id=p.id, keys=list(data.keys()))
    return {"ok": True, "policy": policy_public(p)}


@router.delete("/policies/{policy_id}")
def delete_policy(
    policy_id: int,
    db: Session = Depends(get_db),
    admin: Admin = Depends(require_roles(ROLE_ADMIN)),
):
    rows = db.query(Policy).order_by(Policy.id.asc()).all()
    if len(rows) <= 1:
        raise HTTPException(400, "Нельзя удалить единственную политику")
    p = next((r for r in rows if r.id == policy_id), None)
    if not p:
        raise HTTPException(404, "Policy not found")
    db.delete(p)
    db.commit()
    audit(db, "POLICY_DELETE", username=admin.username, policy_id=policy_id)
    return {"ok": True}


@router.get("/policies/resolve-preview")
def policies_resolve_preview(
    nas_ip: str,
    db: Session = Depends(get_db),
    _: Admin = Depends(require_roles(ROLE_ADMIN)),
):
    p = resolve_policy(db, nas_ip)
    return {"nas_ip": nas_ip, "policy": policy_public(p)}


@router.get("/audit")
def list_audit(
    limit: int = 200,
    db: Session = Depends(get_db),
    _: Admin = Depends(require_roles(ROLE_ADMIN, ROLE_AUDITOR)),
):
    rows = db.query(AuditEvent).order_by(AuditEvent.id.desc()).limit(min(limit, 500)).all()
    return [
        {
            "id": e.id,
            "timestamp": e.timestamp.isoformat() if e.timestamp else None,
            "event_type": e.event_type,
            "event_label": audit_event_label(e.event_type),
            "user_id": e.user_id,
            "username": e.username,
            "meta": e.meta,
            "meta_text": format_audit_meta(e.meta),
        }
        for e in rows
    ]


@router.get("/tokens")
def get_tokens(
    serial: str | None = None,
    type: str | None = None,
    user: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
    _: Admin = Depends(require_roles(ROLE_ADMIN, ROLE_OPERATOR, ROLE_AUDITOR)),
):
    return list_tokens(db, serial=serial, token_type=type, user=user, status=status)


@router.patch("/tokens/{serial}")
def patch_token(
    serial: str,
    body: TokenPatch,
    db: Session = Depends(get_db),
    admin: Admin = Depends(require_roles(ROLE_ADMIN)),
):
    row = find_by_serial(db, serial)
    if not row:
        raise HTTPException(404, "Token not found")
    if body.revoke:
        revoke_token(db, row)
        db.commit()
        audit(db, "TOKEN_REVOKE", user_id=row.id, username=row.ad_username, by=admin.username, serial=serial)
        return {"ok": True}
    if body.active is not None:
        set_token_active(row, body.active)
    if body.description is not None:
        row.token_description = body.description or None
    db.commit()
    audit(
        db,
        "TOKEN_PATCH",
        user_id=row.id,
        username=row.ad_username,
        by=admin.username,
        serial=serial,
        active=row.token_active,
    )
    return {"ok": True}


@router.get("/stats")
def stats(db: Session = Depends(get_db), _: Admin = Depends(require_roles(ROLE_ADMIN, ROLE_OPERATOR, ROLE_AUDITOR))):
    return build_dashboard(db)
