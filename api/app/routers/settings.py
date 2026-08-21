from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.audit import audit
from app.db import get_db
from app.ldap_auth import run_ldap_test
from app.routers.auth import require_roles
from app.rbac import ROLE_ADMIN
from app.mail_service import run_smtp_test
from app.settings_service import (
    apply_ldap_servers,
    apply_settings_patch,
    ldap_config,
    ldap_config_for_test,
    radius_config,
    settings_public_full,
    smtp_config_for_test,
)
from app.tls_service import save_root_ca, save_web_tls

router = APIRouter(prefix="/api/settings", tags=["settings"], dependencies=[Depends(require_roles(ROLE_ADMIN))])


class LdapServerIn(BaseModel):
    host: str
    port: int | None = None


class SettingsPatch(BaseModel):
    ldap_servers: list[LdapServerIn] | None = None
    ldap_use_ssl: bool | None = None
    ldap_base_dn: str | None = None
    ldap_user_attr: str | None = None
    ldap_bind_user: str | None = None
    ldap_bind_password: str | None = None
    ldap_sync_ou: str | None = None
    ldap_sync_group: str | None = None
    radius_shared_secret: str | None = None
    radius_port: int | None = None
    radius_allowed_clients: str | None = None
    expressms_dry_run: bool | None = None
    expressms_api_url: str | None = None
    expressms_token: str | None = None
    telegram_dry_run: bool | None = None
    telegram_bot_token: str | None = None
    public_base_url: str | None = None
    smtp_dry_run: bool | None = None
    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_use_ssl: bool | None = None
    smtp_from: str | None = None
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_invite_subject: str | None = None
    smtp_invite_body_template: str | None = None
    panel_operator_group: str | None = None
    panel_auditor_group: str | None = None


class TestLdapIn(BaseModel):
    username: str | None = None
    password: str | None = None
    ldap_servers: list[LdapServerIn] | None = None
    ldap_use_ssl: bool | None = None
    ldap_base_dn: str | None = None
    ldap_user_attr: str | None = None
    ldap_bind_user: str | None = None
    ldap_bind_password: str | None = None
    ldap_bind_use_stored: bool | None = None


class TestSmtpIn(BaseModel):
    to_addr: str
    smtp_dry_run: bool | None = None
    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_use_ssl: bool | None = None
    smtp_from: str | None = None
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_password_use_stored: bool | None = None


class TlsWebIn(BaseModel):
    cert_pem: str
    key_pem: str


class TlsRootCaIn(BaseModel):
    ca_pem: str


@router.get("")
def get_settings(db: Session = Depends(get_db)):
    return settings_public_full(db)


@router.patch("")
def patch_settings(body: SettingsPatch, db: Session = Depends(get_db), admin=Depends(require_roles(ROLE_ADMIN))):
    data = body.model_dump(exclude_unset=True)
    servers = data.pop("ldap_servers", None)
    if "radius_port" in data and data["radius_port"] is not None:
        data["radius_port"] = str(data["radius_port"])
    if "smtp_port" in data and data["smtp_port"] is not None:
        data["smtp_port"] = str(data["smtp_port"])
    apply_settings_patch(db, data)
    if servers is not None:
        apply_ldap_servers(db, servers, ldap_config(db).use_ssl)
    audit(db, "SETTINGS_PATCH", username=admin.username, keys=list(body.model_dump(exclude_unset=True).keys()))
    return {"ok": True}


@router.post("/test-ldap")
def test_ldap(body: TestLdapIn, db: Session = Depends(get_db)):
    overrides = body.model_dump(exclude_unset=True, exclude={"username", "password"})
    if body.ldap_servers is not None:
        overrides["ldap_servers"] = [s.model_dump() for s in body.ldap_servers]
    cfg = ldap_config_for_test(db, overrides)
    return run_ldap_test(cfg, body.username, body.password, overrides)


@router.post("/test-smtp")
def test_smtp(body: TestSmtpIn, db: Session = Depends(get_db)):
    overrides = body.model_dump(exclude_unset=True, exclude={"to_addr"})
    cfg = smtp_config_for_test(db, overrides)
    return run_smtp_test(cfg, body.to_addr)


@router.get("/radius-preview")
def radius_preview(db: Session = Depends(get_db)):
    cfg = radius_config(db)
    return {"port": cfg.port, "shared_secret_set": bool(cfg.shared_secret)}


@router.post("/tls/web")
def upload_web_tls(body: TlsWebIn, db: Session = Depends(get_db), admin=Depends(require_roles(ROLE_ADMIN))):
    try:
        save_web_tls(db, body.cert_pem, body.key_pem)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    audit(db, "TLS_WEB_UPLOAD", username=admin.username)
    return {"ok": True}


@router.post("/tls/root-ca")
def upload_root_ca(body: TlsRootCaIn, db: Session = Depends(get_db), admin=Depends(require_roles(ROLE_ADMIN))):
    try:
        save_root_ca(db, body.ca_pem)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    audit(db, "TLS_ROOT_CA_UPLOAD", username=admin.username)
    return {"ok": True}
