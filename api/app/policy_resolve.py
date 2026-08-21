"""Выбор политики RADIUS по IP клиента (Policy.scope)."""

from __future__ import annotations

import ipaddress

from sqlalchemy.orm import Session

from app.models import Policy


def parse_scope_tokens(raw: str | None) -> list[str]:
    if raw is None or not str(raw).strip():
        return ["*"]
    parts: list[str] = []
    for chunk in str(raw).replace(";", "\n").split("\n"):
        for item in chunk.split(","):
            item = item.strip()
            if item:
                parts.append(item)
    return parts or ["*"]


def scope_token_score(nas_ip: str, token: str) -> int | None:
    """Специфичность совпадения: выше = лучше. None = не совпало. `*` = 0."""
    token = (token or "").strip()
    if not token or token == "*":
        return 0
    try:
        addr = ipaddress.ip_address(nas_ip)
    except ValueError:
        return None
    try:
        if "/" in token:
            net = ipaddress.ip_network(token, strict=False)
            if addr in net:
                return int(net.prefixlen)
            return None
        if addr == ipaddress.ip_address(token):
            return addr.max_prefixlen
        return None
    except ValueError:
        return None


def best_scope_score(nas_ip: str, scope_raw: str | None) -> int | None:
    best: int | None = None
    for token in parse_scope_tokens(scope_raw):
        score = scope_token_score(nas_ip, token)
        if score is None:
            continue
        if best is None or score > best:
            best = score
    return best


def default_policy(db: Session) -> Policy:
    """Глобальная политика (enroll, TTL приглашений): scope `*`, иначе первая по id."""
    rows = db.query(Policy).order_by(Policy.id.asc()).all()
    for row in rows:
        tokens = parse_scope_tokens(row.scope)
        if "*" in tokens:
            return row
    if rows:
        return rows[0]
    row = Policy(name="Default", scope="*")
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def resolve_policy(db: Session, nas_ip: str | None) -> Policy:
    """Политика для Access-Request: самое узкое совпадение scope с nas_ip, иначе default."""
    rows = db.query(Policy).order_by(Policy.id.asc()).all()
    if not rows:
        return default_policy(db)
    if not (nas_ip or "").strip():
        return default_policy(db)

    best_row: Policy | None = None
    best_score = -1
    for row in rows:
        score = best_scope_score(nas_ip.strip(), row.scope)
        if score is None:
            continue
        if score > best_score:
            best_score = score
            best_row = row
    return best_row or default_policy(db)


def policy_public(p: Policy) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "scope": p.scope,
        "require_2fa": p.require_2fa,
        "allowed_second_factors": p.allowed_second_factors,
        "totp_window_steps": p.totp_window_steps,
        "otp_ttl_seconds": p.otp_ttl_seconds,
        "max_otp_attempts_per_challenge": p.max_otp_attempts_per_challenge,
        "challenge_ttl_seconds": p.challenge_ttl_seconds,
        "enroll_invite_ttl_seconds": p.enroll_invite_ttl_seconds,
        "radius_scheme_preference": p.radius_scheme_preference,
    }
