from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import Admin, utcnow
from app.rate_limit import enforce_rate_limit
from app.rbac import ALL_ROLES, ROLE_ADMIN, ROLE_LABELS

router = APIRouter(prefix="/api", tags=["auth"])
pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer = HTTPBearer(auto_error=False)


class LoginIn(BaseModel):
    username: str
    password: str


class PasswordChangeIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


class PanelUserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=8)
    role: str


class PanelUserPatch(BaseModel):
    role: str | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=8)


def hash_password(password: str) -> str:
    return pwd.hash(password)


def create_token(username: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    return jwt.encode({"sub": username, "exp": exp}, settings.jwt_secret, algorithm="HS256")


def current_admin(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> Admin:
    if not creds:
        raise HTTPException(401, "Not authenticated")
    try:
        payload = jwt.decode(creds.credentials, settings.jwt_secret, algorithms=["HS256"])
        username = payload.get("sub")
    except JWTError:
        raise HTTPException(401, "Invalid token")
    admin = db.query(Admin).filter(Admin.username == username).first()
    if not admin or not admin.is_active:
        raise HTTPException(401, "Invalid token")
    return admin


def require_roles(*roles: str):
    allowed = frozenset(roles)

    def _check(admin: Admin = Depends(current_admin)) -> Admin:
        if admin.role not in allowed:
            raise HTTPException(403, "Недостаточно прав")
        return admin

    return _check


def _admin_public(a: Admin) -> dict:
    return {
        "id": a.id,
        "username": a.username,
        "role": a.role,
        "role_label": ROLE_LABELS.get(a.role, a.role),
        "is_active": a.is_active,
        "auth_source": getattr(a, "auth_source", None) or "local",
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


@router.post("/login")
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else "unknown"
    enforce_rate_limit("login", f"{body.username}:{ip}", settings.rate_limit_login_per_minute, 60)
    username = (body.username or "").strip()
    password = body.password or ""
    if not username or not password:
        raise HTTPException(401, "Invalid username or password")

    from app.panel_auth import (
        AUTH_LDAP,
        AUTH_LOCAL,
        resolve_ad_panel_role,
        upsert_ldap_panel_user,
        _sam_from_login,
    )

    sam = _sam_from_login(username)
    local = (
        db.query(Admin)
        .filter(Admin.username.in_([username, sam]))
        .filter(Admin.auth_source == AUTH_LOCAL)
        .first()
    )
    if local:
        if not local.is_active:
            raise HTTPException(401, "Invalid username or password")
        if not local.password_hash or not pwd.verify(password, local.password_hash):
            raise HTTPException(401, "Invalid username or password")
        return {
            "token": create_token(local.username),
            "username": local.username,
            "role": local.role,
            "role_label": ROLE_LABELS.get(local.role, local.role),
            "auth_source": AUTH_LOCAL,
        }

    # AD: operator / auditor по группам
    try:
        resolved = resolve_ad_panel_role(db, username, password)
    except Exception:
        resolved = None
    if not resolved:
        raise HTTPException(401, "Invalid username or password")
    ad_user, role = resolved
    existing = db.query(Admin).filter(Admin.username == ad_user).first()
    if existing and existing.auth_source == AUTH_LOCAL:
        raise HTTPException(401, "Invalid username or password")
    if existing and not existing.is_active:
        raise HTTPException(401, "Invalid username or password")
    try:
        admin = upsert_ldap_panel_user(db, ad_user, role)
    except ValueError as exc:
        raise HTTPException(401, "Invalid username or password") from exc
    from app.audit import audit

    audit(db, "PANEL_LOGIN_AD", username=admin.username, role=role)
    return {
        "token": create_token(admin.username),
        "username": admin.username,
        "role": admin.role,
        "role_label": ROLE_LABELS.get(admin.role, admin.role),
        "auth_source": AUTH_LDAP,
    }


@router.get("/me")
def me(admin: Admin = Depends(current_admin)):
    return {
        "username": admin.username,
        "role": admin.role,
        "role_label": ROLE_LABELS.get(admin.role, admin.role),
        "id": admin.id,
        "auth_source": getattr(admin, "auth_source", None) or "local",
    }


@router.post("/me/password")
def change_my_password(
    body: PasswordChangeIn,
    db: Session = Depends(get_db),
    admin: Admin = Depends(current_admin),
):
    if getattr(admin, "auth_source", "local") != "local" or not admin.password_hash:
        raise HTTPException(400, "Пароль AD меняется в Active Directory")
    if not pwd.verify(body.current_password, admin.password_hash):
        raise HTTPException(400, "Неверный текущий пароль")
    admin.password_hash = hash_password(body.new_password)
    admin.updated_at = utcnow()
    db.commit()
    return {"ok": True}


@router.get("/panel-users")
def list_panel_users(
    db: Session = Depends(get_db),
    _: Admin = Depends(require_roles(ROLE_ADMIN)),
):
    rows = db.query(Admin).order_by(Admin.username).all()
    return [_admin_public(a) for a in rows]


@router.post("/panel-users")
def create_panel_user(
    body: PanelUserCreate,
    db: Session = Depends(get_db),
    actor: Admin = Depends(require_roles(ROLE_ADMIN)),
):
    username = body.username.strip()
    if not username:
        raise HTTPException(400, "Нужен логин")
    if body.role not in ALL_ROLES:
        raise HTTPException(400, "Неизвестная роль")
    if db.query(Admin).filter(Admin.username == username).first():
        raise HTTPException(400, "Пользователь уже существует")
    row = Admin(
        username=username,
        password_hash=hash_password(body.password),
        role=body.role,
        is_active=True,
        auth_source="local",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    from app.audit import audit

    audit(db, "PANEL_USER_CREATE", username=username, by=actor.username, role=body.role)
    return _admin_public(row)


@router.patch("/panel-users/{user_id}")
def patch_panel_user(
    user_id: int,
    body: PanelUserPatch,
    db: Session = Depends(get_db),
    actor: Admin = Depends(require_roles(ROLE_ADMIN)),
):
    row = db.query(Admin).filter(Admin.id == user_id).first()
    if not row:
        raise HTTPException(404, "Не найден")
    if body.role is not None:
        if getattr(row, "auth_source", "local") == "ldap":
            raise HTTPException(400, "Роль AD-пользователя задаётся группой AD при входе")
        if body.role not in ALL_ROLES:
            raise HTTPException(400, "Неизвестная роль")
        if row.role == ROLE_ADMIN and body.role != ROLE_ADMIN:
            admins_left = (
                db.query(Admin)
                .filter(Admin.role == ROLE_ADMIN, Admin.is_active.is_(True), Admin.id != row.id)
                .count()
            )
            if admins_left < 1:
                raise HTTPException(400, "Нельзя снять роль с последнего администратора")
        row.role = body.role
    if body.is_active is not None:
        if row.id == actor.id and not body.is_active:
            raise HTTPException(400, "Нельзя отключить свою учётную запись")
        if row.role == ROLE_ADMIN and not body.is_active:
            admins_left = (
                db.query(Admin)
                .filter(Admin.role == ROLE_ADMIN, Admin.is_active.is_(True), Admin.id != row.id)
                .count()
            )
            if admins_left < 1:
                raise HTTPException(400, "Нельзя отключить последнего администратора")
        row.is_active = body.is_active
    if body.password:
        if getattr(row, "auth_source", "local") == "ldap":
            raise HTTPException(400, "Пароль AD меняется в Active Directory")
        row.password_hash = hash_password(body.password)
    row.updated_at = utcnow()
    db.commit()
    from app.audit import audit

    audit(db, "PANEL_USER_PATCH", username=row.username, by=actor.username)
    return _admin_public(row)
