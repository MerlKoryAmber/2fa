import logging

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal
from app.models import Admin, Policy, User
from app.otp import encrypt_totp_secret
from app.rate_limit import ping_redis
from app.routers import admin, auth, public_enroll, radius
from app.routers import settings as settings_router
from app.routers.auth import hash_password
from app.settings_service import seed_from_env
from app.token_service import ensure_token_serial, user_to_token

log = logging.getLogger("uvicorn.error")

app = FastAPI(title="MK 2FA", version="0.3.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(public_enroll.router)
app.include_router(settings_router.router)
app.include_router(radius.router)


def get_db_ping():
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        yield db
    finally:
        db.close()


@app.get("/health")
def health(db: Session = Depends(get_db_ping)):
    redis_ok = ping_redis()
    return {"ok": redis_ok, "db": True, "redis": redis_ok}


def seed():
    db = SessionLocal()
    try:
        seed_from_env(db)
        if not db.query(Admin).filter(Admin.username == settings.admin_username).first():
            db.add(
                Admin(
                    username=settings.admin_username,
                    password_hash=hash_password(settings.admin_password),
                    role="admin",
                    is_active=True,
                    auth_source="local",
                )
            )
        policy = db.query(Policy).first()
        if not policy:
            db.add(Policy(name="Default", scope="*"))
        else:
            if (policy.name or "").strip() == "default":
                policy.name = "Default"
            if "TELEGRAM" not in policy.allowed_second_factors:
                policy.allowed_second_factors = "TOTP,EXPRESSMS,TELEGRAM"
        for row in db.query(Policy).filter(Policy.name == "default").all():
            row.name = "Default"
        demo = db.query(User).filter(User.ad_username == settings.demo_username).first()
        if not demo:
            demo = User(
                ad_username=settings.demo_username,
                otp_method="TOTP",
                totp_secret_encrypted=encrypt_totp_secret(settings.demo_totp_secret),
                totp_confirmed=True,
            )
            db.add(demo)
            db.flush()
            ensure_token_serial(demo, db)
        elif demo.otp_method != "NONE":
            ensure_token_serial(demo, db)
        db.commit()
        log.info("seed complete demo=%s", settings.demo_username)
    finally:
        db.close()


def backfill_token_serials():
    db = SessionLocal()
    try:
        changed = 0
        for user in db.query(User).all():
            if user_to_token(user) and not user.token_serial:
                ensure_token_serial(user, db)
                changed += 1
        if changed:
            db.commit()
            log.info("backfilled token serials: %s", changed)
    finally:
        db.close()


def rename_policy_default_label():
    """Подпись Default — только UI; выбор политики по scope не зависит от name."""
    db = SessionLocal()
    try:
        changed = 0
        for row in db.query(Policy).filter(Policy.name == "default").all():
            row.name = "Default"
            changed += 1
        if changed:
            db.commit()
            log.info("renamed policy label default→Default: %s", changed)
    finally:
        db.close()


@app.on_event("startup")
def on_startup():
    backfill_token_serials()
    rename_policy_default_label()
    if settings.seed_on_startup:
        seed()
    db = SessionLocal()
    try:
        from app.tls_service import apply_tls_from_db

        apply_tls_from_db(db)
    finally:
        db.close()
