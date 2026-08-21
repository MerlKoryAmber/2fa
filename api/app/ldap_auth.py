import logging
import os
import ssl
from pathlib import Path

from ldap3 import NTLM, NONE, Connection, Server, Tls
from ldap3.core.exceptions import LDAPException

from app.hashlib_md4 import ensure_md4
from app.ldap_util import (
    build_sync_user_filter,
    is_group_dn,
    bind_uses_ntlm,
    domain_suffix_from_base_dn,
    ldap_entry_attr,
    normalize_bind_user,
    server_urls,
)
from app.settings_service import LdapConfig

ensure_md4()
log = logging.getLogger(__name__)

LDAP_CONNECT_TIMEOUT = 4
LDAP_RECEIVE_TIMEOUT = 5


def _ldap_tls() -> Tls:
    """LDAPS: корневой CA из панели, иначе без проверки (корпоративный AD часто с внутренним CA)."""
    ca = Path(os.environ.get("SSL_DATA_DIR", "/data/ssl")) / "root-ca.crt"
    if ca.is_file() and ca.stat().st_size > 0:
        return Tls(validate=ssl.CERT_REQUIRED, ca_certs_file=str(ca))
    return Tls(validate=ssl.CERT_NONE)


def _ldap_server(url: str, use_ssl: bool) -> Server:
    # get_info=NONE: schema ALL на каждый RADIUS-вход вешает NAS (таймаут «сервер не ответил»).
    return Server(
        url,
        use_ssl=use_ssl,
        get_info=NONE,
        tls=_ldap_tls() if use_ssl else None,
        connect_timeout=LDAP_CONNECT_TIMEOUT,
    )


def authenticate_ldap(username: str, password: str, cfg: LdapConfig) -> bool:
    if not username or not password:
        return False
    return _bind_ad(username, password, cfg)


def _bind_password_source(overrides: dict, cfg: LdapConfig) -> str:
    if overrides.get("ldap_bind_password"):
        return "из формы проверки"
    if overrides.get("ldap_bind_use_stored"):
        return "сохранённый в системе"
    if cfg.bind_password:
        return "сохранённый в системе"
    return "не задан"


def _bind_attempts(raw_bind_user: str, base_dn: str) -> list[tuple[str, object | None, str]]:
    raw = (raw_bind_user or "").strip()
    if not raw:
        return []
    seen: set[tuple[str, object | None]] = set()
    attempts: list[tuple[str, object | None, str]] = []

    def add(identity: str, auth, label: str) -> None:
        key = (identity, auth)
        if key in seen:
            return
        seen.add(key)
        attempts.append((identity, auth, label))

    if "\\" in raw:
        local, domain = raw.split("\\", 1)
        local = local.strip()
        domain = domain.strip()
        suffix = domain_suffix_from_base_dn(base_dn)
        if suffix:
            add(f"{local}@{suffix}", None, f"UPN {local}@{suffix}")
            if suffix.lower() != suffix:
                add(f"{local}@{suffix.lower()}", None, f"UPN {local}@{suffix.lower()}")
        add(raw, NTLM, f"NTLM {raw}")
        if domain and domain.upper() != domain:
            add(f"{domain.upper()}\\{local}", NTLM, f"NTLM {domain.upper()}\\{local}")
    elif "@" in raw or raw.upper().startswith("CN="):
        add(raw, None, f"UPN {raw}")
    else:
        suffix = domain_suffix_from_base_dn(base_dn)
        if suffix:
            add(f"{raw}@{suffix}", None, f"UPN {raw}@{suffix}")
        add(raw, None, f"SIMPLE {raw}")
    return attempts


def _service_bind_with_log(cfg: LdapConfig, log: list[str], overrides: dict | None = None) -> tuple[bool, str]:
    overrides = overrides or {}
    pwd_src = _bind_password_source(overrides, cfg)
    log.append(f"Пароль bind: {pwd_src}")
    if not cfg.bind_password:
        log.append("✗ Пароль bind пустой — введите в «Пароль для проверки» или «Пароль bind» и сохраните")
        return False, "пароль bind не задан"

    attempts = _bind_attempts(cfg.bind_user, cfg.base_dn)
    if not attempts:
        log.append("✗ Bind user не задан")
        return False, "bind user не задан"

    errors: list[str] = []
    for url in server_urls(cfg.servers, cfg.use_ssl):
        for identity, auth, label in attempts:
            log.append(f"Service bind → {url} как {label}…")
            try:
                conn = _open_connection(url, cfg.use_ssl, identity, cfg.bind_password, auth)
                conn.unbind()
                log.append(f"✓ Service bind успешен ({label}, {url})")
                return True, f"service bind ok ({label}, {url})"
            except LDAPException as exc:
                errors.append(f"{url} [{label}]: {exc}")
                log.append(f"✗ {label}: {exc}")
            except Exception as exc:
                errors.append(f"{url} [{label}]: {exc}")
                log.append(f"✗ {label}: {type(exc).__name__}: {exc}")
    message = "; ".join(errors) if errors else "bind failed"
    return False, message


def test_service_bind(cfg: LdapConfig) -> tuple[bool, str]:
    result = run_ldap_test(cfg)
    return result["ok"], result["message"]


def run_ldap_test(
    cfg: LdapConfig,
    username: str | None = None,
    password: str | None = None,
    overrides: dict | None = None,
) -> dict:
    log: list[str] = []

    urls = server_urls(cfg.servers, cfg.use_ssl)
    log.append(f"Режим: AD/LDAP, SSL={'да' if cfg.use_ssl else 'нет'}")
    log.append(f"Контроллеры: {', '.join(urls) if urls else '(не заданы)'}")
    log.append(f"Base DN: {cfg.base_dn or '(не задан)'}")
    log.append(f"Bind user: {cfg.bind_user or '(не задан)'}")

    if not cfg.servers:
        log.append("✗ Нужен хотя бы один DC")
        return {"ok": False, "mode": "bind", "message": "нужен хотя бы один DC", "log": log}

    if username and password:
        log.append(f"Проверка входа пользователя «{username}»…")
        ok = authenticate_ldap(username, password, cfg)
        log.append("✓ Аутентификация успешна" if ok else "✗ Аутентификация не удалась")
        return {
            "ok": ok,
            "mode": "auth",
            "message": "auth ok" if ok else "auth failed",
            "log": log,
        }

    if not cfg.bind_user:
        log.append("✗ Нужен bind user (короткий логин или user@Домен)")
        return {"ok": False, "mode": "bind", "message": "нужен bind user (короткий логин или user@Домен)", "log": log}

    ok, message = _service_bind_with_log(cfg, log, overrides or {})
    return {"ok": ok, "mode": "bind", "message": message, "log": log}


def _open_connection(
    url: str,
    use_ssl: bool,
    bind_user: str,
    bind_password: str,
    authentication=None,
) -> Connection:
    server = _ldap_server(url, use_ssl)
    auth = authentication if authentication is not None else (NTLM if bind_uses_ntlm(bind_user) else None)
    return Connection(
        server,
        user=bind_user,
        password=bind_password,
        authentication=auth,
        auto_bind=True,
        receive_timeout=LDAP_RECEIVE_TIMEOUT,
    )


def _user_connection(url: str, use_ssl: bool, user: str, password: str) -> Connection:
    server = _ldap_server(url, use_ssl)
    auth = NTLM if bind_uses_ntlm(user) else None
    return Connection(
        server,
        user=user,
        password=password,
        authentication=auth,
        auto_bind=True,
        receive_timeout=LDAP_RECEIVE_TIMEOUT,
    )


def _bind_ad(username: str, password: str, cfg: LdapConfig) -> bool:
    if not cfg.servers:
        return False
    identity = normalize_bind_user(cfg.bind_user, cfg.base_dn)
    for url in server_urls(cfg.servers, cfg.use_ssl):
        try:
            if identity:
                svc = _open_connection(url, cfg.use_ssl, identity, cfg.bind_password)
                attr = cfg.user_attr
                if not svc.search(cfg.base_dn, f"({attr}={_escape(username)})", attributes=["distinguishedName"]):
                    svc.unbind()
                    continue
                dn = svc.entries[0].entry_dn
                svc.unbind()
            else:
                dn = normalize_bind_user(username, cfg.base_dn)
                if "\\" in username or "@" in username:
                    dn = username
            user_conn = _user_connection(url, cfg.use_ssl, dn, password)
            user_conn.unbind()
            return True
        except LDAPException:
            log.debug("LDAP bind failed on %s for user=%s", url, username, exc_info=True)
            continue
    log.warning("LDAP auth failed for user=%s on all DC", username)
    return False


def _escape(value: str) -> str:
    return (
        value.replace("\\", "\\5c")
        .replace("*", "\\2a")
        .replace("(", "\\28")
        .replace(")", "\\29")
        .replace("\x00", "\\00")
    )


def _resolve_group_dn(conn, group_spec: str, base_dn: str) -> str | None:
    spec = (group_spec or "").strip()
    if not spec:
        return None
    if is_group_dn(spec):
        return spec
    from ldap3.utils.conv import escape_filter_chars

    esc = escape_filter_chars(spec)
    filt = f"(&(objectClass=group)(|(sAMAccountName={esc})(cn={esc})))"
    if conn.search(base_dn, filt, attributes=["distinguishedName"], size_limit=1):
        return conn.entries[0].entry_dn
    return None


def list_ldap_users(cfg: LdapConfig, limit: int = 500) -> tuple[list[dict], str | None]:
    if not cfg.servers or not cfg.bind_user or not cfg.base_dn:
        return [], "нужны DC, bind user и base DN"
    search_base = (cfg.sync_ou or cfg.base_dn).strip()
    if not search_base:
        return [], "нужен Base DN или OU для загрузки"
    identity = normalize_bind_user(cfg.bind_user, cfg.base_dn)
    errors: list[str] = []
    for url in server_urls(cfg.servers, cfg.use_ssl):
        try:
            conn = _open_connection(url, cfg.use_ssl, identity, cfg.bind_password)
            group_dn = None
            if cfg.sync_group:
                group_dn = _resolve_group_dn(conn, cfg.sync_group, cfg.base_dn)
                if not group_dn:
                    conn.unbind()
                    return [], f"группа AD не найдена: {cfg.sync_group}"
            filt = build_sync_user_filter(group_dn)
            if not conn.search(
                search_base,
                filt,
                attributes=[cfg.user_attr, "mail", "displayName", "userPrincipalName"],
                size_limit=limit,
            ):
                conn.unbind()
                continue
            out: list[dict] = []
            for entry in conn.entries:
                uname = ldap_entry_attr(entry, cfg.user_attr)
                if not uname:
                    continue
                email = ldap_entry_attr(entry, "mail") or None
                display_name = ldap_entry_attr(entry, "displayName") or None
                out.append({"username": uname, "email": email, "display_name": display_name})
            conn.unbind()
            return out, None
        except LDAPException as exc:
            errors.append(f"{url}: {exc}")
        except Exception as exc:
            errors.append(f"{url}: {type(exc).__name__}: {exc}")
    return [], "; ".join(errors) if errors else "LDAP search failed"
