from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import Admin
from app.rate_limit import enforce_rate_limit

router = APIRouter(prefix="/api", tags=["auth"])
pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer = HTTPBearer(auto_error=False)


class LoginIn(BaseModel):
    username: str
    password: str


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
    if not admin:
        raise HTTPException(401, "Invalid token")
    return admin


@router.post("/login")
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else "unknown"
    enforce_rate_limit("login", f"{body.username}:{ip}", settings.rate_limit_login_per_minute, 60)
    admin = db.query(Admin).filter(Admin.username == body.username).first()
    if not admin or not pwd.verify(body.password, admin.password_hash):
        raise HTTPException(401, "Invalid username or password")
    return {"token": create_token(admin.username), "username": admin.username}


@router.get("/me")
def me(admin: Admin = Depends(current_admin)):
    return {"username": admin.username}
