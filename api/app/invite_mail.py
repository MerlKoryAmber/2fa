from sqlalchemy.orm import Session

from app.settings_service import get_raw

DEFAULT_INVITE_SUBJECT = "Приглашение на настройку 2FA"
DEFAULT_INVITE_BODY = """Здравствуйте, {username}.

Для настройки второго фактора (2FA) перейдите по ссылке:
{invite_url}

Ссылка действует до {expires_at}.

— Own 2FA"""


def invite_email_templates(db: Session) -> tuple[str, str]:
    subject = (get_raw(db, "smtp.invite_subject") or "").strip() or DEFAULT_INVITE_SUBJECT
    body = (get_raw(db, "smtp.invite_body_template") or "").strip() or DEFAULT_INVITE_BODY
    return subject, body


def render_invite_email(db: Session, username: str, invite_url: str, expires_at) -> tuple[str, str]:
    subject, template = invite_email_templates(db)
    exp = expires_at.strftime("%Y-%m-%d %H:%M UTC")
    ctx = {"username": username, "invite_url": invite_url, "expires_at": exp}
    body = template
    for key, val in ctx.items():
        body = body.replace("{" + key + "}", val)
    for key, val in ctx.items():
        subject = subject.replace("{" + key + "}", val)
    return subject, body
