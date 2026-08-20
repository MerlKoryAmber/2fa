import logging

import httpx

from app.celery_app import celery_app
from app.db import SessionLocal
from app.settings_service import expressms_config, telegram_config

log = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.sync_ldap_users")
def sync_ldap_users():
    db = SessionLocal()
    try:
        from app.ldap_sync import run_ldap_sync

        out = run_ldap_sync(db, by="system")
        if not out.get("ok"):
            log.warning("LDAP auto-sync failed: %s", out.get("error"))
        else:
            log.info("LDAP auto-sync: total=%s created=%s", out.get("total"), out.get("created"))
        return out
    finally:
        db.close()


@celery_app.task(name="app.tasks.send_expressms_otp", bind=True, max_retries=3, default_retry_delay=5)
def send_expressms_otp(self, expressms_id: str, otp: str):
    db = SessionLocal()
    try:
        cfg = expressms_config(db)
    finally:
        db.close()
    if cfg.dry_run or not cfg.api_url:
        log.info("ExpressMS dry-run: id=%s digits=%s", expressms_id, len(otp))
        return {"ok": True, "dry_run": True}
    try:
        with httpx.Client(timeout=10) as client:
            r = client.post(
                cfg.api_url,
                headers={"Authorization": f"Bearer {cfg.token}"},
                json={"to": expressms_id, "text": f"OTP: {otp}"},
            )
            r.raise_for_status()
        return {"ok": True, "dry_run": False}
    except Exception as exc:
        raise self.retry(exc=exc)


@celery_app.task(name="app.tasks.send_telegram_otp", bind=True, max_retries=3, default_retry_delay=5)
def send_telegram_otp(self, chat_id: str, otp: str):
    db = SessionLocal()
    try:
        cfg = telegram_config(db)
    finally:
        db.close()
    if cfg.dry_run or not cfg.bot_token:
        log.info("Telegram dry-run: chat_id=%s digits=%s", chat_id, len(otp))
        return {"ok": True, "dry_run": True}
    try:
        url = f"https://api.telegram.org/bot{cfg.bot_token}/sendMessage"
        with httpx.Client(timeout=10) as client:
            r = client.post(url, json={"chat_id": chat_id, "text": f"OTP: {otp}"})
            r.raise_for_status()
        return {"ok": True, "dry_run": False}
    except Exception as exc:
        raise self.retry(exc=exc)
