"""Вход в панель через AD: группы → роли operator / auditor."""

from __future__ import annotations

import logging

from ldap3.core.exceptions import LDAPException
from ldap3.utils.conv import escape_filter_chars
from sqlalchemy.orm import Session

from app.ldap_auth import _open_connection, _resolve_group_dn, authenticate_ldap
from app.ldap_util import LDAP_MATCHING_RULE_IN_CHAIN, normalize_bind_user, server_urls
from app.models import Admin, utcnow
from app.rbac import ROLE_AUDITOR, ROLE_OPERATOR
from app.settings_service import get_raw, ldap_config

log = logging.getLogger(__name__)

AUTH_LOCAL = "local"
AUTH_LDAP = "ldap"


def _sam_from_login(username: str) -> str:
    raw = (username or "").strip()
    if "\\" in raw:
        return raw.split("\\", 1)[-1].strip()
    if "@" in raw:
        return raw.split("@", 1)[0].strip()
    return raw


def user_in_ad_group(cfg, username: str, group_spec: str) -> bool:
    """Проверка memberOf (с вложенностью) через service bind."""
    spec = (group_spec or "").strip()
    if not spec or not cfg.servers or not cfg.bind_user or not cfg.base_dn:
        return False
    identity = normalize_bind_user(cfg.bind_user, cfg.base_dn)
    attr = cfg.user_attr or "sAMAccountName"
    sam = _sam_from_login(username)
    for url in server_urls(cfg.servers, cfg.use_ssl):
        try:
            conn = _open_connection(url, cfg.use_ssl, identity, cfg.bind_password)
            group_dn = _resolve_group_dn(conn, spec, cfg.base_dn)
            if not group_dn:
                conn.unbind()
                continue
            filt = (
                f"(&({attr}={escape_filter_chars(sam)})"
                f"(memberOf:{LDAP_MATCHING_RULE_IN_CHAIN}:={escape_filter_chars(group_dn)}))"
            )
            ok = bool(conn.search(cfg.base_dn, filt, attributes=[attr], size_limit=1))
            conn.unbind()
            if ok:
                return True
        except LDAPException:
            log.debug("panel group check failed on %s", url, exc_info=True)
            continue
        except Exception:
            log.debug("panel group check error on %s", url, exc_info=True)
            continue
    return False


def resolve_ad_panel_role(db: Session, username: str, password: str) -> tuple[str, str] | None:
    """
    LDAP bind + группы панели.
    Возвращает (sAMAccountName, role) или None.
    При членстве в обеих группах — operator (шире права).
    """
    cfg = ldap_config(db)
    if not authenticate_ldap(username, password, cfg):
        return None
    sam = _sam_from_login(username)
    op_group = get_raw(db, "panel.operator_group")
    aud_group = get_raw(db, "panel.auditor_group")
    if not op_group and not aud_group:
        return None
    is_op = bool(op_group) and user_in_ad_group(cfg, sam, op_group)
    is_aud = bool(aud_group) and user_in_ad_group(cfg, sam, aud_group)
    if is_op:
        return sam, ROLE_OPERATOR
    if is_aud:
        return sam, ROLE_AUDITOR
    return None


def upsert_ldap_panel_user(db: Session, username: str, role: str) -> Admin:
    row = db.query(Admin).filter(Admin.username == username).first()
    if row:
        if row.auth_source == AUTH_LOCAL:
            # локальный admin с тем же логином — не перезаписываем
            raise ValueError("local_account_exists")
        row.role = role
        row.auth_source = AUTH_LDAP
        row.password_hash = None
        row.updated_at = utcnow()
        if not row.is_active:
            raise ValueError("disabled")
    else:
        row = Admin(
            username=username,
            password_hash=None,
            role=role,
            is_active=True,
            auth_source=AUTH_LDAP,
        )
        db.add(row)
    db.commit()
    db.refresh(row)
    return row
