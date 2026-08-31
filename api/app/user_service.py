from sqlalchemy.orm import Session

from app.ldap_util import decode_ad_display_text
from app.mfa_channels import user_has_express, user_has_telegram, user_has_totp
from app.models import User


def user_row(u: User) -> dict:
    return {
        "id": u.id,
        "ad_username": u.ad_username,
        "display_name": decode_ad_display_text(u.display_name),
        "otp_method": u.otp_method,
        "has_totp": bool(u.totp_secret_encrypted),
        "channel_totp": user_has_totp(u),
        "channel_express": user_has_express(u),
        "express_channel_enabled": bool(u.express_channel_enabled),
        "channel_telegram": user_has_telegram(u),
        "expressms_id": u.expressms_id,
        "telegram_chat_id": u.telegram_chat_id,
        "totp_confirmed": u.totp_confirmed,
        "ldap_email": u.ldap_email,
        "created_at": u.created_at.isoformat() if u.created_at else None,
    }


def list_users(
    db: Session,
    *,
    ad: str | None = None,
    email: str | None = None,
    method: str | None = None,
    totp: str | None = None,
) -> list[dict]:
    rows = db.query(User).order_by(User.ad_username).all()
    out: list[dict] = []
    for u in rows:
        if ad:
            hay_ad = u.ad_username.lower()
            hay_name = (decode_ad_display_text(u.display_name) or "").lower()
            if ad.lower() not in hay_ad and ad.lower() not in hay_name:
                continue
        if email:
            hay = u.ldap_email or ""
            if email.lower() not in hay.lower():
                continue
        if method and method.upper() != u.otp_method.upper():
            continue
        if totp == "yes" and not u.totp_confirmed:
            continue
        if totp == "no" and u.totp_confirmed:
            continue
        out.append(user_row(u))
    return out
