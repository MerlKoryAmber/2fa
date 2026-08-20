import secrets

from sqlalchemy.orm import Session

from app.models import User

SERIAL_PREFIX = {"TOTP": "TOTP", "EXPRESSMS": "EMS", "TELEGRAM": "TGM"}


def new_token_serial(token_type: str) -> str:
    prefix = SERIAL_PREFIX.get(token_type.upper(), "TOK")
    return f"{prefix}{secrets.token_hex(4).upper()}"


def _is_enrolled(user: User) -> bool:
    if user.otp_method == "NONE":
        return False
    if user.otp_method == "TOTP":
        return bool(user.totp_secret_encrypted)
    if user.otp_method == "EXPRESSMS":
        return bool(user.expressms_id)
    if user.otp_method == "TELEGRAM":
        return bool(user.telegram_chat_id)
    return False


def token_status(user: User) -> str:
    if not _is_enrolled(user):
        return "unassigned"
    if not user.token_active:
        return "disabled"
    if user.otp_method == "TOTP" and not user.totp_confirmed:
        return "pending"
    return "active"


def ensure_token_serial(user: User, db: Session) -> None:
    if user.otp_method == "NONE":
        return
    if user.token_serial:
        return
    for _ in range(8):
        serial = new_token_serial(user.otp_method)
        clash = db.query(User).filter(User.token_serial == serial).first()
        if not clash:
            user.token_serial = serial
            user.token_active = True
            return
    raise RuntimeError("failed to allocate token serial")


def touch_last_used(user: User, db: Session) -> None:
    from app.otp import utcnow

    user.last_used_at = utcnow()
    db.commit()


def user_to_token(user: User) -> dict | None:
    if not _is_enrolled(user):
        return None
    serial = user.token_serial or f"LEG-{user.id:06d}"
    return {
        "serial": serial,
        "type": user.otp_method,
        "user_id": user.id,
        "user": user.ad_username,
        "active": user.token_active,
        "status": token_status(user),
        "description": user.token_description or "",
        "enrolled_at": user.updated_at.isoformat() if user.updated_at else None,
        "last_used_at": user.last_used_at.isoformat() if user.last_used_at else None,
        "totp_confirmed": user.totp_confirmed,
    }


def list_tokens(
    db: Session,
    *,
    serial: str | None = None,
    token_type: str | None = None,
    user: str | None = None,
    status: str | None = None,
) -> list[dict]:
    rows = db.query(User).order_by(User.ad_username).all()
    out: list[dict] = []
    for u in rows:
        item = user_to_token(u)
        if not item:
            continue
        if serial and serial.lower() not in item["serial"].lower():
            continue
        if token_type and token_type.upper() not in item["type"].upper():
            continue
        if user and user.lower() not in item["user"].lower():
            continue
        if status and item["status"] != status.lower():
            continue
        out.append(item)
    return out


def find_by_serial(db: Session, serial: str) -> User | None:
    user = db.query(User).filter(User.token_serial == serial).first()
    if user:
        return user
    if serial.startswith("LEG-"):
        try:
            uid = int(serial.split("-", 1)[1])
        except ValueError:
            return None
        return db.query(User).filter(User.id == uid).first()
    return None


def revoke_token(db: Session, user: User) -> None:
    user.otp_method = "NONE"
    user.token_active = False
    user.totp_secret_encrypted = None
    user.totp_confirmed = False
    user.expressms_id = None
    user.telegram_chat_id = None
    user.token_description = None


def set_token_active(user: User, active: bool) -> None:
    user.token_active = active
