"""Каналы 2FA у пользователя и сценарий политики (без «активного метода»)."""

from __future__ import annotations

from app.models import Policy, User

MFA_SCENARIOS = frozenset({"totp", "express_push", "express_push_then_totp"})


def user_has_totp(user: User) -> bool:
    return bool(user.totp_secret_encrypted and user.totp_confirmed)


def user_has_express(user: User) -> bool:
    """Push: email из AD (lookup BotX) или кэш chat_id после /start."""
    return bool((user.ldap_email or "").strip() or (user.expressms_id or "").strip())


def user_has_telegram(user: User) -> bool:
    return bool((user.telegram_chat_id or "").strip())


def _method_allowed(policy: Policy, method: str) -> bool:
    allowed = {m.strip().upper() for m in (policy.allowed_second_factors or "").split(",") if m.strip()}
    return method.upper() in allowed


def totp_usable(user: User, policy: Policy) -> bool:
    return user_has_totp(user) and _method_allowed(policy, "TOTP")


def express_usable(user: User, policy: Policy) -> bool:
    return user_has_express(user) and _method_allowed(policy, "EXPRESSMS")


def resolve_mfa_scenario(policy: Policy) -> str:
    raw = (getattr(policy, "mfa_scenario", None) or "").strip().lower()
    if raw in MFA_SCENARIOS:
        return raw
    # совместимость до миграции / старых строк
    mode = (getattr(policy, "expressms_mode", None) or "otp").strip().lower()
    if mode == "push":
        return "express_push"
    return "totp"


def push_wait_seconds(policy: Policy) -> int:
    n = int(getattr(policy, "push_wait_seconds", None) or 0)
    if n <= 0:
        n = int(policy.challenge_ttl_seconds or 60)
    return max(5, min(n, 300))


def sync_otp_method_from_channels(user: User) -> None:
    """Legacy-поле для сериалов/фильтров: предпочитаем TOTP, иначе Express, иначе Telegram."""
    if user_has_totp(user):
        user.otp_method = "TOTP"
    elif user_has_express(user):
        user.otp_method = "EXPRESSMS"
    elif user_has_telegram(user):
        user.otp_method = "TELEGRAM"
    else:
        user.otp_method = "NONE"
