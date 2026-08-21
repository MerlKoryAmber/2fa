from dataclasses import dataclass, replace

from app.ldap_util import (
    LdapServer,
    parse_legacy_url,
    parse_servers_raw,
    serialize_servers,
    server_from_dict,
)
from app.radius_acl import parse_allowed_clients

from sqlalchemy.orm import Session

from app.config import settings as env
from app.crypto import decrypt_secret, encrypt_secret
from app.models import SystemSetting

SECRET_KEYS = frozenset(
    {
        "ldap.bind_password",
        "expressms.token",
        "telegram.bot_token",
        "radius.shared_secret",
        "smtp.password",
        "tls.web_key_pem",
    }
)

ENV_DEFAULTS: dict[str, str] = {
    "ldap.servers": lambda: env.ldap_servers,
    "ldap.url": lambda: env.ldap_url,
    "ldap.use_ssl": lambda: str(env.ldap_use_ssl).lower(),
    "ldap.base_dn": lambda: env.ldap_base_dn,
    "ldap.user_attr": lambda: env.ldap_user_attr or "sAMAccountName",
    "ldap.bind_user": lambda: env.ldap_bind_user or env.ldap_bind_dn,
    "ldap.bind_password": lambda: env.ldap_bind_password,
    "ldap.sync_ou": lambda: env.ldap_sync_ou,
    "ldap.sync_group": lambda: env.ldap_sync_group,
    "panel.operator_group": lambda: env.panel_operator_group,
    "panel.auditor_group": lambda: env.panel_auditor_group,
    "radius.shared_secret": lambda: env.radius_secret,
    "radius.port": lambda: "1812",
    "radius.allowed_clients": lambda: env.radius_allowed_clients,
    "expressms.dry_run": lambda: str(env.expressms_dry_run).lower(),
    "expressms.api_url": lambda: env.expressms_api_url,
    "expressms.token": lambda: env.expressms_token,
    "telegram.dry_run": lambda: str(env.telegram_dry_run).lower(),
    "telegram.bot_token": lambda: env.telegram_bot_token,
    "app.public_base_url": lambda: env.public_base_url,
    "smtp.dry_run": lambda: str(env.smtp_dry_run).lower(),
    "smtp.host": lambda: env.smtp_host,
    "smtp.port": lambda: str(env.smtp_port),
    "smtp.use_ssl": lambda: str(env.smtp_use_ssl).lower(),
    "smtp.from_addr": lambda: env.smtp_from,
    "smtp.username": lambda: env.smtp_username,
    "smtp.password": lambda: env.smtp_password,
    "smtp.invite_subject": lambda: env.smtp_invite_subject,
    "smtp.invite_body_template": lambda: env.smtp_invite_body_template,
}


def _default(key: str) -> str:
    fn = ENV_DEFAULTS.get(key)
    return fn() if fn else ""


def _as_bool(val: str) -> bool:
    return str(val).lower() in ("1", "true", "yes", "on")


def get_raw(db: Session, key: str) -> str:
    row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if row is not None:
        val = row.value or ""
        if key in SECRET_KEYS and val:
            try:
                return decrypt_secret(val)
            except Exception:
                return val
        return val
    return _default(key)


def set_raw(db: Session, key: str, value: str) -> None:
    stored = value
    if key in SECRET_KEYS and value:
        stored = encrypt_secret(value)
    row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if row:
        row.value = stored
    else:
        db.add(SystemSetting(key=key, value=stored))
    db.commit()


def is_secret_set(db: Session, key: str) -> bool:
    row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if row and row.value:
        return True
    return bool(_default(key))


@dataclass
class LdapConfig:
    servers: list[LdapServer]
    use_ssl: bool
    base_dn: str
    user_attr: str
    bind_user: str
    bind_password: str
    sync_ou: str = ""
    sync_group: str = ""


def _load_ldap_servers(db: Session, use_ssl: bool) -> list[LdapServer]:
    raw = get_raw(db, "ldap.servers")
    servers = parse_servers_raw(raw, use_ssl)
    if servers:
        return servers
    legacy_url = get_raw(db, "ldap.url")
    return parse_legacy_url(legacy_url, use_ssl)


@dataclass
class RadiusConfig:
    shared_secret: str
    port: int
    allowed_clients: str

    def allowed_rules(self) -> list[str]:
        return parse_allowed_clients(self.allowed_clients)


@dataclass
class ExpressmsConfig:
    dry_run: bool
    api_url: str
    token: str


@dataclass
class TelegramConfig:
    dry_run: bool
    bot_token: str


@dataclass
class SmtpConfig:
    dry_run: bool
    host: str
    port: int
    use_ssl: bool
    from_addr: str
    username: str
    password: str


def app_public_base_url(db: Session) -> str:
    return (get_raw(db, "app.public_base_url") or "").rstrip("/")


def smtp_config(db: Session) -> SmtpConfig:
    port_raw = get_raw(db, "smtp.port") or "587"
    return SmtpConfig(
        dry_run=_as_bool(get_raw(db, "smtp.dry_run")),
        host=get_raw(db, "smtp.host"),
        port=int(port_raw) if port_raw.isdigit() else 587,
        use_ssl=_as_bool(get_raw(db, "smtp.use_ssl")),
        from_addr=get_raw(db, "smtp.from_addr"),
        username=get_raw(db, "smtp.username"),
        password=get_raw(db, "smtp.password"),
    )


def ldap_config(db: Session) -> LdapConfig:
    use_ssl = _as_bool(get_raw(db, "ldap.use_ssl"))
    return LdapConfig(
        servers=_load_ldap_servers(db, use_ssl),
        use_ssl=use_ssl,
        base_dn=get_raw(db, "ldap.base_dn"),
        user_attr=get_raw(db, "ldap.user_attr") or "sAMAccountName",
        bind_user=get_raw(db, "ldap.bind_user"),
        bind_password=get_raw(db, "ldap.bind_password"),
        sync_ou=get_raw(db, "ldap.sync_ou"),
        sync_group=get_raw(db, "ldap.sync_group"),
    )


def ldap_config_for_test(db: Session, overrides: dict) -> LdapConfig:
    cfg = ldap_config(db)
    if overrides.get("ldap_use_ssl") is not None:
        cfg = replace(cfg, use_ssl=bool(overrides["ldap_use_ssl"]))
    if overrides.get("ldap_base_dn") is not None:
        cfg = replace(cfg, base_dn=str(overrides["ldap_base_dn"]))
    if overrides.get("ldap_user_attr") is not None:
        cfg = replace(cfg, user_attr=str(overrides["ldap_user_attr"] or "sAMAccountName"))
    if overrides.get("ldap_bind_user") is not None:
        cfg = replace(cfg, bind_user=str(overrides["ldap_bind_user"]))
    if overrides.get("ldap_bind_password"):
        cfg = replace(cfg, bind_password=str(overrides["ldap_bind_password"]))
    elif not overrides.get("ldap_bind_use_stored"):
        if "ldap_bind_password" in overrides and overrides["ldap_bind_password"] == "":
            cfg = replace(cfg, bind_password="")
    servers_in = overrides.get("ldap_servers")
    if servers_in is not None:
        ssl = cfg.use_ssl
        servers: list[LdapServer] = []
        for item in servers_in:
            if isinstance(item, dict):
                srv = server_from_dict(item, ssl)
                if srv:
                    servers.append(srv)
        if servers:
            cfg = replace(cfg, servers=servers)
    return cfg


def radius_config(db: Session) -> RadiusConfig:
    port_raw = get_raw(db, "radius.port")
    return RadiusConfig(
        shared_secret=get_raw(db, "radius.shared_secret") or "testing123",
        port=int(port_raw) if port_raw.isdigit() else 1812,
        allowed_clients=get_raw(db, "radius.allowed_clients"),
    )


def expressms_config(db: Session) -> ExpressmsConfig:
    return ExpressmsConfig(
        dry_run=_as_bool(get_raw(db, "expressms.dry_run")),
        api_url=get_raw(db, "expressms.api_url"),
        token=get_raw(db, "expressms.token"),
    )


def telegram_config(db: Session) -> TelegramConfig:
    return TelegramConfig(
        dry_run=_as_bool(get_raw(db, "telegram.dry_run")),
        bot_token=get_raw(db, "telegram.bot_token"),
    )


def settings_public(db: Session) -> dict:
    return {
        "ldap": {
            "servers": [{"host": s.host, "port": s.port} for s in _load_ldap_servers(db, _as_bool(get_raw(db, "ldap.use_ssl")))],
            "use_ssl": _as_bool(get_raw(db, "ldap.use_ssl")),
            "base_dn": get_raw(db, "ldap.base_dn"),
            "user_attr": get_raw(db, "ldap.user_attr"),
            "bind_user": get_raw(db, "ldap.bind_user"),
            "bind_password_set": is_secret_set(db, "ldap.bind_password"),
            "sync_ou": get_raw(db, "ldap.sync_ou"),
            "sync_group": get_raw(db, "ldap.sync_group"),
        },
        "radius": {
            "shared_secret_set": is_secret_set(db, "radius.shared_secret"),
            "port": int(get_raw(db, "radius.port") or "1812"),
            "allowed_clients": get_raw(db, "radius.allowed_clients"),
        },
        "expressms": {
            "dry_run": _as_bool(get_raw(db, "expressms.dry_run")),
            "api_url": get_raw(db, "expressms.api_url"),
            "token_set": is_secret_set(db, "expressms.token"),
        },
        "telegram": {
            "dry_run": _as_bool(get_raw(db, "telegram.dry_run")),
            "bot_token_set": is_secret_set(db, "telegram.bot_token"),
        },
        "smtp": {
            "dry_run": _as_bool(get_raw(db, "smtp.dry_run")),
            "host": get_raw(db, "smtp.host"),
            "port": int(get_raw(db, "smtp.port") or "587"),
            "use_ssl": _as_bool(get_raw(db, "smtp.use_ssl")),
            "from_addr": get_raw(db, "smtp.from_addr"),
            "username": get_raw(db, "smtp.username"),
            "password_set": is_secret_set(db, "smtp.password"),
            "invite_subject": get_raw(db, "smtp.invite_subject"),
            "invite_body_template": get_raw(db, "smtp.invite_body_template"),
        },
        "app": {
            "public_base_url": get_raw(db, "app.public_base_url"),
            "operator_group": get_raw(db, "panel.operator_group"),
            "auditor_group": get_raw(db, "panel.auditor_group"),
        },
    }


def settings_public_full(db: Session) -> dict:
    from app.tls_service import tls_public

    out = settings_public(db)
    out["tls"] = tls_public(db)
    return out


def apply_ldap_servers(db: Session, servers_in: list, use_ssl: bool | None = None) -> None:
    ssl = use_ssl if use_ssl is not None else _as_bool(get_raw(db, "ldap.use_ssl"))
    servers: list[LdapServer] = []
    for item in servers_in:
        if isinstance(item, dict):
            srv = server_from_dict(item, ssl)
            if srv:
                servers.append(srv)
    set_raw(db, "ldap.servers", serialize_servers(servers))


def apply_settings_patch(db: Session, body: dict) -> None:
    mapping = {
        "ldap_use_ssl": ("ldap.use_ssl", lambda v: str(v).lower()),
        "ldap_base_dn": ("ldap.base_dn", str),
        "ldap_user_attr": ("ldap.user_attr", str),
        "ldap_bind_user": ("ldap.bind_user", str),
        "ldap_bind_password": ("ldap.bind_password", str),
        "ldap_sync_ou": ("ldap.sync_ou", str),
        "ldap_sync_group": ("ldap.sync_group", str),
        "radius_shared_secret": ("radius.shared_secret", str),
        "radius_port": ("radius.port", str),
        "radius_allowed_clients": ("radius.allowed_clients", str),
        "expressms_dry_run": ("expressms.dry_run", lambda v: str(v).lower()),
        "expressms_api_url": ("expressms.api_url", str),
        "expressms_token": ("expressms.token", str),
        "telegram_dry_run": ("telegram.dry_run", lambda v: str(v).lower()),
        "telegram_bot_token": ("telegram.bot_token", str),
        "public_base_url": ("app.public_base_url", str),
        "smtp_dry_run": ("smtp.dry_run", lambda v: str(v).lower()),
        "smtp_host": ("smtp.host", str),
        "smtp_port": ("smtp.port", str),
        "smtp_use_ssl": ("smtp.use_ssl", lambda v: str(v).lower()),
        "smtp_from": ("smtp.from_addr", str),
        "smtp_username": ("smtp.username", str),
        "smtp_password": ("smtp.password", str),
        "smtp_invite_subject": ("smtp.invite_subject", str),
        "smtp_invite_body_template": ("smtp.invite_body_template", str),
        "panel_operator_group": ("panel.operator_group", str),
        "panel_auditor_group": ("panel.auditor_group", str),
    }
    for field, (key, conv) in mapping.items():
        if field not in body:
            continue
        val = body[field]
        if val is None:
            continue
        if field.endswith("_password") or field.endswith("_token") or field.endswith("_secret"):
            if val == "":
                continue
        set_raw(db, key, conv(val))


def seed_from_env(db: Session) -> None:
    if db.query(SystemSetting).first():
        return
    for key in ENV_DEFAULTS:
        set_raw(db, key, _default(key))
