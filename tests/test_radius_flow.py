from unittest.mock import patch

import pyotp

from app.models import Policy, User
from app.radius_flow import handle_access_request
from app.settings_service import LdapConfig


def test_radius_totp_challenge_and_accept(db_session, seeded_user, fake_redis):
    step1 = handle_access_request(db_session, "demo", "demo", None)
    assert step1["decision"] == "challenge"
    state = step1["state"]
    code = pyotp.TOTP("JBSWY3DPEHPK3PXP").now()
    step2 = handle_access_request(db_session, "demo", code, state)
    assert step2["decision"] == "accept"


def test_radius_reject_bad_password(db_session, seeded_user, fake_redis):
    out = handle_access_request(db_session, "demo", "bad", None)
    assert out["decision"] == "reject"


def test_radius_replay_state(db_session, seeded_user, fake_redis):
    step1 = handle_access_request(db_session, "demo", "demo", None)
    state = step1["state"]
    code = pyotp.TOTP("JBSWY3DPEHPK3PXP").now()
    assert handle_access_request(db_session, "demo", code, state)["decision"] == "accept"
    replay = handle_access_request(db_session, "demo", code, state)
    assert replay["decision"] == "reject"


def test_expressms_flow_dry_run(db_session, fake_redis):
    db_session.add(Policy())
    user = User(ad_username="ems", otp_method="EXPRESSMS", expressms_id="u-1")
    db_session.add(user)
    db_session.commit()

    with patch("app.radius_flow.send_expressms_otp.delay") as send:
        step1 = handle_access_request(db_session, "ems", "demo", None)
        assert step1["decision"] == "challenge"
        send.assert_called_once()


def test_telegram_flow_dry_run(db_session, fake_redis):
    db_session.add(Policy())
    user = User(ad_username="tg1", otp_method="TELEGRAM", telegram_chat_id="12345")
    db_session.add(user)
    db_session.commit()

    with patch("app.radius_flow.send_telegram_otp.delay") as send:
        step1 = handle_access_request(db_session, "tg1", "demo", None)
        assert step1["decision"] == "challenge"
        send.assert_called_once_with("12345", send.call_args[0][1])


def test_ldap_config_from_settings(db_session, fake_redis):
    from app.settings_service import ldap_config, set_raw

    set_raw(db_session, "ldap.mock", "true")
    set_raw(db_session, "ldap.mock_password", "secret")
    cfg = ldap_config(db_session)
    assert cfg.mock is True
    assert cfg.mock_password == "secret"
