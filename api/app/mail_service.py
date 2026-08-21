import logging
import smtplib
from email.message import EmailMessage

from sqlalchemy.orm import Session

from app.invite_mail import render_invite_email
from app.settings_service import SmtpConfig, smtp_config

log = logging.getLogger(__name__)


def send_mail_cfg(cfg: SmtpConfig, to_addr: str, subject: str, body: str) -> dict:
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
            # порт 587 и обычный SMTP: STARTTLS (галка SSL/TLS = SMTP_SSL на 465)
            try:
                smtp.starttls()
                smtp.ehlo()
            except smtplib.SMTPNotSupportedError:
                pass
            if cfg.username:
                smtp.login(cfg.username, cfg.password)
            smtp.send_message(msg)
    return {"ok": True, "dry_run": False}


def send_mail(db: Session, to_addr: str, subject: str, body: str) -> dict:
    return send_mail_cfg(smtp_config(db), to_addr, subject, body)


def send_invite_email(db: Session, to_addr: str, username: str, invite_url: str, expires_at) -> dict:
    subject, body = render_invite_email(db, username, invite_url, expires_at)
    return send_mail(db, to_addr, subject, body)


def run_smtp_test(cfg: SmtpConfig, to_addr: str) -> dict:
    """Проверка по значениям формы (ещё не обязательно сохранённым). Всегда реальная попытка, dry_run игнор."""
    lines: list[str] = []
    to_addr = (to_addr or "").strip()
    lines.append(f"Host: {cfg.host or '(пусто)'}:{cfg.port}")
    lines.append(f"Шифрование: {'SMTP_SSL' if cfg.use_ssl else 'SMTP + STARTTLS (если сервер умеет)'}")
    lines.append(f"From: {cfg.from_addr or cfg.username or '(пусто)'}")
    lines.append(f"Username: {cfg.username or '(без логина)'}")
    lines.append(f"Кому: {to_addr or '(не указан)'}")
    if cfg.dry_run:
        lines.append("В форме включён Dry-run — приглашения пока не уйдут; тест ниже шлёт письмо по-настоящему.")

    if not cfg.host:
        lines.append("✗ Нужен Host")
        return {"ok": False, "message": "нужен SMTP host", "log": lines}
    if not to_addr or "@" not in to_addr:
        lines.append("✗ Укажите email получателя теста")
        return {"ok": False, "message": "нужен email получателя", "log": lines}
    if not (cfg.from_addr or cfg.username):
        lines.append("✗ Нужен From или Username")
        return {"ok": False, "message": "нужен From или Username", "log": lines}

    test_cfg = SmtpConfig(
        dry_run=False,
        host=cfg.host,
        port=cfg.port,
        use_ssl=cfg.use_ssl,
        from_addr=cfg.from_addr,
        username=cfg.username,
        password=cfg.password,
    )
    subject = "MK 2FA — проверка SMTP"
    body = (
        "Это тестовое письмо из панели MK 2FA.\n"
        "Если вы его получили — SMTP настроен верно (можно сохранять настройки).\n"
    )
    try:
        send_mail_cfg(test_cfg, to_addr, subject, body)
        lines.append(f"✓ Письмо отправлено на {to_addr}")
        return {"ok": True, "message": "sent", "log": lines}
    except Exception as exc:
        lines.append(f"✗ Ошибка: {exc}")
        log.exception("SMTP test failed")
        return {"ok": False, "message": str(exc), "log": lines}
