import logging
import os
import re
from pathlib import Path

from sqlalchemy.orm import Session

from app.settings_service import get_raw, is_secret_set, set_raw

log = logging.getLogger(__name__)

SSL_DIR = Path(os.environ.get("SSL_DATA_DIR", "/data/ssl"))
CERT_FILE = "cert.pem"
KEY_FILE = "key.pem"
ROOT_CA_FILE = "root-ca.crt"
RELOAD_FLAG = "reload.request"

_PEM_BLOCK = re.compile(r"-----BEGIN [^-]+-----.*?-----END [^-]+-----", re.DOTALL)


def _ensure_ssl_dir() -> None:
    SSL_DIR.mkdir(parents=True, exist_ok=True)


def _normalize_pem(text: str) -> str:
    blocks = _PEM_BLOCK.findall(text or "")
    if not blocks:
        raise ValueError("Не найден PEM-блок (-----BEGIN ... -----)")
    return "\n".join(b.strip() for b in blocks) + "\n"


def tls_public(db: Session) -> dict:
    cert_path = SSL_DIR / CERT_FILE
    key_path = SSL_DIR / KEY_FILE
    ca_path = SSL_DIR / ROOT_CA_FILE
    return {
        "web_cert_set": is_secret_set(db, "tls.web_cert_pem") or cert_path.is_file(),
        "web_key_set": is_secret_set(db, "tls.web_key_pem") or key_path.is_file(),
        "root_ca_set": is_secret_set(db, "tls.root_ca_pem") or ca_path.is_file(),
        "using_custom_web_tls": cert_path.is_file() and key_path.is_file(),
    }


def _write_file(name: str, content: str) -> None:
    _ensure_ssl_dir()
    path = SSL_DIR / name
    path.write_text(content, encoding="utf-8")
    try:
        path.chmod(0o644)
    except OSError:
        pass


def _request_nginx_reload() -> None:
    _ensure_ssl_dir()
    flag = SSL_DIR / RELOAD_FLAG
    flag.write_text("1", encoding="utf-8")


def apply_tls_from_db(db: Session) -> None:
    cert = get_raw(db, "tls.web_cert_pem")
    key = get_raw(db, "tls.web_key_pem")
    ca = get_raw(db, "tls.root_ca_pem")
    if cert and key:
        _write_file(CERT_FILE, cert)
        _write_file(KEY_FILE, key)
        try:
            KEY_PATH = SSL_DIR / KEY_FILE
            KEY_PATH.chmod(0o600)
        except OSError:
            pass
        _request_nginx_reload()
        log.info("TLS web cert/key applied to %s", SSL_DIR)
    if ca:
        _write_file(ROOT_CA_FILE, ca)
        _request_nginx_reload()
        log.info("TLS root CA applied to %s", SSL_DIR)


def save_web_tls(db: Session, cert_pem: str, key_pem: str) -> None:
    cert = _normalize_pem(cert_pem)
    key = _normalize_pem(key_pem)
    set_raw(db, "tls.web_cert_pem", cert)
    set_raw(db, "tls.web_key_pem", key)
    apply_tls_from_db(db)


def save_root_ca(db: Session, ca_pem: str) -> None:
    ca = _normalize_pem(ca_pem)
    set_raw(db, "tls.root_ca_pem", ca)
    apply_tls_from_db(db)
