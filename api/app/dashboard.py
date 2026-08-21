"""Сводка панели: метрики без стендовых адресов."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.audit_labels import audit_event_label, format_audit_meta
from app.models import AuditEvent, User
from app.otp import utcnow
from app.rate_limit import ping_redis
from app.settings_service import ldap_config

RADIUS_24H_TYPES = (
    "RADIUS_ACCEPT",
    "RADIUS_REJECT",
    "RADIUS_CHALLENGE",
    "RADIUS_NAS_DENIED",
    "RADIUS_ERROR",
    "OTP_FAIL",
    "OTP_OK",
)

RECENT_TYPES = (
    "RADIUS_ACCEPT",
    "RADIUS_REJECT",
    "RADIUS_CHALLENGE",
    "RADIUS_NAS_DENIED",
    "RADIUS_ERROR",
    "OTP_OK",
    "OTP_FAIL",
    "LDAP_FAIL",
    "LDAP_OK",
)


def _count_events(db: Session, since, types: tuple[str, ...]) -> dict[str, int]:
    rows = (
        db.query(AuditEvent.event_type, func.count(AuditEvent.id))
        .filter(AuditEvent.timestamp >= since, AuditEvent.event_type.in_(types))
        .group_by(AuditEvent.event_type)
        .all()
    )
    return {t: 0 for t in types} | {k: int(v) for k, v in rows}


def build_dashboard(db: Session) -> dict:
    now = utcnow()
    since_24h = now - timedelta(hours=24)
    since_1h = now - timedelta(hours=1)

    users = db.query(User).count()
    enrolled = db.query(User).filter(User.otp_method != "NONE").count()
    without_2fa = db.query(User).filter(User.otp_method == "NONE").count()
    totp_pending = (
        db.query(User)
        .filter(
            User.otp_method == "TOTP",
            User.totp_secret_encrypted.isnot(None),
            User.totp_confirmed.is_(False),
        )
        .count()
    )

    counts_24h = _count_events(db, since_24h, RADIUS_24H_TYPES)
    radius_1h_total = (
        db.query(func.count(AuditEvent.id))
        .filter(AuditEvent.timestamp >= since_1h, AuditEvent.event_type.in_(RECENT_TYPES))
        .scalar()
        or 0
    )

    recent_rows = (
        db.query(AuditEvent)
        .filter(AuditEvent.event_type.in_(RECENT_TYPES))
        .order_by(AuditEvent.timestamp.desc(), AuditEvent.id.desc())
        .limit(12)
        .all()
    )
    recent = [
        {
            "id": e.id,
            "timestamp": e.timestamp.isoformat() if e.timestamp else None,
            "event_type": e.event_type,
            "event_label": audit_event_label(e.event_type),
            "username": e.username,
            "meta_text": format_audit_meta(e.meta),
        }
        for e in recent_rows
    ]

    redis_ok = False
    try:
        redis_ok = bool(ping_redis())
    except Exception:
        redis_ok = False

    return {
        "users": users,
        "enrolled": enrolled,
        "without_2fa": without_2fa,
        "totp_pending": totp_pending,
        "ldap_configured": bool(ldap_config(db).servers),
        "health": {
            "db": True,
            "redis": redis_ok,
            "radius_events_1h": int(radius_1h_total),
        },
        "radius_24h": {
            "accept": counts_24h.get("RADIUS_ACCEPT", 0),
            "reject": counts_24h.get("RADIUS_REJECT", 0),
            "challenge": counts_24h.get("RADIUS_CHALLENGE", 0),
            "otp_fail": counts_24h.get("OTP_FAIL", 0),
            "otp_ok": counts_24h.get("OTP_OK", 0),
            "nas_denied": counts_24h.get("RADIUS_NAS_DENIED", 0),
            "error": counts_24h.get("RADIUS_ERROR", 0),
        },
        "recent": recent,
        "generated_at": now.isoformat(),
    }
