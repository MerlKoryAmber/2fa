from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.db import get_db
from app.enroll_service import (
    create_invite,
    get_valid_invite,
    new_invite_token,
    username_matches_invite,
    verify_enroll_proof,
    create_enroll_proof,
)
from app.main import app
from app.models import EnrollmentInvite, Policy, User
from app.otp import encrypt_totp_secret, utcnow, verify_totp


def test_create_and_validate_invite(db_session):
    db_session.add(Policy())
    user = User(
        ad_username="alice",
        otp_method="TOTP",
        totp_secret_encrypted=encrypt_totp_secret("JBSWY3DPEHPK3PXP"),
        ldap_email="alice@lab.local",
    )
    db_session.add(user)
    db_session.commit()
    inv = create_invite(db_session, user, "admin", user.ldap_email, 3600)
    db_session.commit()
    assert inv.token
    assert get_valid_invite(db_session, inv.token) is not None


def test_expired_invite(db_session):
    db_session.add(Policy())
    user = User(ad_username="bob", otp_method="NONE")
    db_session.add(user)
    db_session.commit()
    inv = EnrollmentInvite(
        token=new_invite_token(),
        user_id=user.id,
        created_by="admin",
        email_to="b@x.local",
        expires_at=utcnow() - timedelta(seconds=10),
        created_at=utcnow(),
    )
    db_session.add(inv)
    db_session.commit()
    assert get_valid_invite(db_session, inv.token) is None


def test_render_invite_email_default(db_session):
    db_session.add(Policy())
    db_session.commit()
    from app.invite_mail import render_invite_email

    subject, body = render_invite_email(db_session, "alice", "https://2fa/enroll/tok", utcnow())
    assert "alice" in body
    assert "https://2fa/enroll/tok" in body
    assert subject


def test_username_matches_invite(db_session):
    user = User(ad_username="Merl2", otp_method="NONE")
    assert username_matches_invite(user, "Merl2") is True
    assert username_matches_invite(user, "merl2") is True
    assert username_matches_invite(user, "Merl2@Merl.loc") is True
    assert username_matches_invite(user, "MERL\\Merl2") is True
    assert username_matches_invite(user, "other") is False


def test_enroll_proof_roundtrip():
    proof = create_enroll_proof("tok123")
    assert verify_enroll_proof(proof, "tok123") is True
    assert verify_enroll_proof(proof, "other") is False


@pytest.fixture()
def enroll_client(db_session, fake_redis, monkeypatch):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    monkeypatch.setattr("app.main.ping_redis", lambda: True)
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_public_enroll_requires_auth(enroll_client, db_session):
    db_session.add(Policy())
    secret = "JBSWY3DPEHPK3PXP"
    user = User(
        ad_username="demo",
        otp_method="TOTP",
        totp_secret_encrypted=encrypt_totp_secret(secret),
        totp_confirmed=False,
    )
    db_session.add(user)
    db_session.commit()
    inv = create_invite(db_session, user, "admin", "demo@lab.local", 3600)
    db_session.commit()

    r = enroll_client.get(f"/api/public/enroll/{inv.token}")
    assert r.status_code == 200
    body = r.json()
    assert body["username"] == "demo"
    assert body["auth_required"] is True
    assert "qr_png_base64" not in body

    bad = enroll_client.post(
        f"/api/public/enroll/{inv.token}",
        json={"code": "000000", "enroll_proof": "bad"},
    )
    assert bad.status_code == 401

    auth = enroll_client.post(
        f"/api/public/enroll/{inv.token}/auth",
        json={"username": "demo", "password": "demo"},
    )
    assert auth.status_code == 200
    qr = auth.json()
    assert qr["qr_png_base64"]
    assert qr["enroll_proof"]

    import pyotp

    code = pyotp.TOTP(secret).now()
    ok = enroll_client.post(
        f"/api/public/enroll/{inv.token}",
        json={"code": code, "enroll_proof": qr["enroll_proof"]},
    )
    assert ok.status_code == 200
    db_session.refresh(user)
    assert user.totp_confirmed is True
