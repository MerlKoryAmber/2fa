from app.models import User
from app.token_service import (
    ensure_token_serial,
    list_tokens,
    new_token_serial,
    revoke_token,
    token_status,
    user_to_token,
)


def test_new_token_serial_prefix():
    s = new_token_serial("TOTP")
    assert s.startswith("TOTP")
    assert len(s) == 12


def test_token_status_pending(db_session):
    u = User(ad_username="u1", otp_method="TOTP", totp_secret_encrypted="x", totp_confirmed=False)
    db_session.add(u)
    db_session.commit()
    assert token_status(u) == "pending"


def test_token_status_active(db_session):
    u = User(
        ad_username="u2",
        otp_method="TOTP",
        totp_secret_encrypted="x",
        totp_confirmed=True,
        token_serial="TOTP12345678",
    )
    db_session.add(u)
    db_session.commit()
    assert token_status(u) == "active"


def test_ensure_token_serial(db_session):
    u = User(ad_username="u3", otp_method="EXPRESSMS", expressms_id="123")
    db_session.add(u)
    db_session.commit()
    ensure_token_serial(u, db_session)
    db_session.commit()
    assert u.token_serial.startswith("EMS")


def test_list_and_revoke(db_session):
    u = User(
        ad_username="u4",
        otp_method="TELEGRAM",
        telegram_chat_id="99",
        token_serial="TGMABCDEF01",
        token_active=True,
    )
    db_session.add(u)
    db_session.commit()
    items = list_tokens(db_session)
    assert any(x["serial"] == "TGMABCDEF01" for x in items)
    revoke_token(db_session, u)
    db_session.commit()
    assert u.otp_method == "NONE"
    assert list_tokens(db_session, serial="TGMABCDEF01") == []
