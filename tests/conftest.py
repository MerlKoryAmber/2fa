import os
import sys
from datetime import datetime, timezone

import fakeredis
import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

ROOT = os.path.dirname(os.path.dirname(__file__))
API = os.path.join(ROOT, "api")
if API not in sys.path:
    sys.path.insert(0, API)

os.environ.setdefault("APP_ENCRYPTION_KEY", Fernet.generate_key().decode())
os.environ.setdefault("JWT_SECRET", "test-jwt")
os.environ.setdefault("INTERNAL_API_TOKEN", "test-internal")
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("SEED_ON_STARTUP", "false")
os.environ.setdefault("ADMIN_USERNAME", "admin")
os.environ.setdefault("ADMIN_PASSWORD", "changeme")
os.environ.setdefault("DEMO_USERNAME", "demo")
os.environ.setdefault("DEMO_PASSWORD", "demo")
os.environ.setdefault("DEMO_TOTP_SECRET", "JBSWY3DPEHPK3PXP")

from app.db import Base  # noqa: E402
from app import models  # noqa: F401,E402


@pytest.fixture()
def fake_redis(monkeypatch):
    server = fakeredis.FakeStrictRedis(decode_responses=True)
    monkeypatch.setattr("app.rate_limit._client", server)
    return server


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def seeded_user(db_session):
    from app.models import Policy, User
    from app.otp import encrypt_totp_secret

    db_session.add(Policy())
    user = User(
        ad_username="demo",
        otp_method="TOTP",
        totp_secret_encrypted=encrypt_totp_secret("JBSWY3DPEHPK3PXP"),
        totp_confirmed=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def ldap_ok(monkeypatch):
    monkeypatch.setattr("app.radius_flow.authenticate_ldap", lambda *a, **k: True)
    monkeypatch.setattr("app.ldap_auth.authenticate_ldap", lambda *a, **k: True)
