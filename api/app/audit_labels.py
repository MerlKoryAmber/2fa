EVENT_LABELS: dict[str, str] = {
    "PANEL_USER_CREATE": "Создание пользователя панели",
    "PANEL_USER_PATCH": "Изменение пользователя панели",
    "PANEL_LOGIN_AD": "Вход в панель через AD",
    "POLICY_CREATE": "Создание политики",
    "POLICY_PATCH": "Изменение политики",
    "POLICY_DELETE": "Удаление политики",
    "USER_PATCH": "Изменение пользователя",
    "TOTP_ISSUE": "Выпуск TOTP",
    "TOTP_ENROLL_OK": "TOTP подтверждён",
    "TOKEN_REVOKE": "Отзыв токена",
    "TOKEN_PATCH": "Изменение токена",
    "SETTINGS_PATCH": "Изменение настроек",
    "TLS_WEB_UPLOAD": "Загрузка HTTPS-сертификата",
    "TLS_ROOT_CA_UPLOAD": "Загрузка корневого CA",
    "LDAP_SYNC": "Синхронизация LDAP",
    "LDAP_SYNC_AUTO": "Авто-синхронизация LDAP",
    "ENROLL_INVITE_LINK": "Ссылка приглашения",
    "ENROLL_INVITE": "Отправка приглашения",
    "ENROLL_AUTH_FAIL": "Ошибка входа по приглашению",
    "ENROLL_AUTH_OK": "Вход по приглашению",
    "ENROLL_INVITE_OK": "2FA настроена по приглашению",
    "LDAP_FAIL": "Ошибка LDAP",
    "LDAP_OK": "Успешный LDAP",
    "RADIUS_ACCEPT": "RADIUS: доступ разрешён",
    "RADIUS_REJECT": "RADIUS: доступ запрещён",
    "RADIUS_CHALLENGE": "RADIUS: запрос 2FA",
    "RADIUS_NAS_DENIED": "RADIUS: NAS не в списке",
    "RADIUS_BAD_PACKET": "RADIUS: битый пакет / неверный secret",
    "RADIUS_ERROR": "RADIUS: внутренняя ошибка",
    "SEND_EXPRESSMS": "OTP отправлен в ExpressMS",
    "EXPRESS_PUSH_SEND": "Push Express отправлен",
    "EXPRESS_PUSH_HOLD": "Ожидание Approve в Express (hold RADIUS)",
    "EXPRESS_PUSH_REUSE": "Push Express: повторный RADIUS (тот же state)",
    "EXPRESS_PUSH_FALLBACK_TOTP": "Push Express: переход на TOTP",
    "SEND_TELEGRAM": "OTP отправлен в Telegram",
    "OTP_OK": "OTP принят",
    "OTP_FAIL": "OTP отклонён",
}

META_KEY_LABELS: dict[str, str] = {
    "by": "Администратор",
    "reason": "Причина",
    "method": "Метод 2FA",
    "serial": "Serial токена",
    "created": "Создано пользователей",
    "total": "Всего в LDAP",
    "email": "Email",
    "dry_run": "Dry-run",
    "active": "Токен активен",
    "nas_ip": "NAS",
    "keys": "Изменённые поля",
}

REASON_LABELS: dict[str, str] = {
    "username_mismatch": "логин не совпадает с приглашением",
    "ldap_fail": "неверный пароль LDAP",
    "invalid_credentials": "неверный логин/пароль AD",
    "allowlist": "IP NAS нет в списке разрешённых",
    "decode": "не разобрать пакет (secret?)",
    "api": "gateway не достучался до API",
    "timeout": "API не ответил вовремя (часто LDAP/DC недоступен из контейнера)",
    "connect": "radius не соединился с API",
    "rate_limit": "слишком много попыток",
    "http_403": "API отклонил токен (403)",
    "http_429": "лимит запросов (429)",
    "http_500": "ошибка API (500)",
    "internal": "ошибка обработки",
    "2fa_disabled": "2FA отключена в политике",
    "otp_only": "только OTP, LDAP на NAS",
    "unknown_user": "пользователь не найден в MK 2FA",
    "token_inactive": "токен отключён",
    "otp_only_needs_totp": "режим «только OTP» требует подтверждённый TOTP",
    "unknown_state": "неизвестный state",
    "replay": "повтор state",
    "expired": "истёк срок",
    "user_mismatch": "другой пользователь",
    "attempts": "исчерпаны попытки",
    "otp_ttl": "истёк OTP",
}

METHOD_LABELS: dict[str, str] = {
    "TOTP": "TOTP",
    "EXPRESSMS": "ExpressMS",
    "TELEGRAM": "Telegram",
    "NONE": "Не настроен",
}

SETTINGS_KEY_LABELS: dict[str, str] = {
    "ldap_use_ssl": "LDAPS",
    "ldap_base_dn": "Base DN",
    "ldap_user_attr": "Атрибут логина",
    "ldap_bind_user": "Учётная запись bind",
    "ldap_bind_password": "Пароль bind",
    "ldap_sync_ou": "OU для загрузки",
    "ldap_sync_group": "Группа AD для загрузки",
    "panel_operator_group": "Группа AD операторов панели",
    "panel_auditor_group": "Группа AD аудиторов панели",
    "radius_shared_secret": "RADIUS secret",
    "radius_port": "RADIUS порт",
    "radius_allowed_clients": "Разрешённые NAS",
    "expressms_dry_run": "ExpressMS dry-run",
    "expressms_api_url": "ExpressMS URL",
    "expressms_token": "ExpressMS token",
    "telegram_dry_run": "Telegram dry-run",
    "telegram_bot_token": "Telegram bot token",
    "public_base_url": "Public base URL",
    "smtp_dry_run": "SMTP dry-run",
    "smtp_host": "SMTP хост",
    "smtp_port": "SMTP порт",
    "smtp_use_ssl": "SMTP SSL",
    "smtp_from": "SMTP from",
    "smtp_username": "SMTP логин",
    "smtp_password": "SMTP пароль",
    "smtp_invite_subject": "Тема приглашения",
    "smtp_invite_body_template": "Шаблон приглашения",
}


def audit_event_label(event_type: str) -> str:
    return EVENT_LABELS.get(event_type, event_type.replace("_", " ").capitalize())


def _format_value(key: str, value) -> str:
    if value is None:
        return "—"
    if key == "reason" and isinstance(value, str):
        return REASON_LABELS.get(value, value)
    if key == "method" and isinstance(value, str):
        return METHOD_LABELS.get(value.upper(), value)
    if key == "dry_run":
        return "да" if value else "нет"
    if key == "active":
        return "да" if value else "нет"
    if key == "keys" and isinstance(value, list):
        labels = [SETTINGS_KEY_LABELS.get(k, k) for k in value]
        return ", ".join(labels) if labels else "—"
    if isinstance(value, bool):
        return "да" if value else "нет"
    return str(value)


def format_audit_meta(meta: dict | None) -> str:
    if not meta:
        return "—"
    parts: list[str] = []
    for key, value in meta.items():
        label = META_KEY_LABELS.get(key, key)
        parts.append(f"{label}: {_format_value(key, value)}")
    return "; ".join(parts) if parts else "—"
