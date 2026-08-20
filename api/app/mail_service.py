import logging

import smtplib
from email.message import EmailMessage

from sqlalchemy.orm import Session

from app.invite_mail import render_invite_email
from app.settings_service import smtp_config

log = logging.getLogger(__name__)


def send_mail(db: Session, to_addr: str, subject: str, body: str) -> dict:
    cfg = smtp_config(db)
    if cfg.dry_run or not cfg.host:
        log.info("SMTP dry-run: to=%s subject=%s len=%s", to_addr, subject, len(body))
        return {"ok": True, "dry_run": True}
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = cfg.from_addr or cfg.username
    msg["To"] = to_addr
    msg.set_content(body)
    if cfg.use_ssl:
        with smtplib.SMTP_SSL(cfg.host, cfg.port, timeout=15) as smtp:
            if cfg.username:
                smtp.login(cfg.username, cfg.password)
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(cfg.host, cfg.port, timeout=15) as smtp:
            smtp.ehlo()
            if cfg.use_ssl:
                smtp.starttls()
            if cfg.username:
                smtp.login(cfg.username, cfg.password)
            smtp.send_message(msg)
    return {"ok": True, "dry_run": False}


def send_invite_email(db: Session, to_addr: str, username: str, invite_url: str, expires_at) -> dict:
    subject, body = render_invite_email(db, username, invite_url, expires_at)
    return send_mail(db, to_addr, subject, body)
