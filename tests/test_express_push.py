from unittest.mock import patch

import pyotp

from app.models import Policy, User
from app.otp import encrypt_totp_secret
from app.radius_flow import handle_access_request


def test_otp_only_totp_untouched_when_express_push_on_other_users(db_session, seeded_user, fake_redis):
    p = db_session.query(Policy).first()
    p.radius_scheme_preference = "otp_only"
    p.mfa_scenario = "express_push"
    p.expressms_mode = "push"
    db_session.commit()

    code = pyotp.TOTP("JBSWY3DPEHPK3PXP").now()
    out = handle_access_request(db_session, "demo", code, None)
    assert out["decision"] == "accept"


def test_otp_only_express_push_approve(db_session, fake_redis):
    db_session.add(Policy(radius_scheme_preference="otp_only", mfa_scenario="express_push", expressms_mode="push"))
    db_session.add(
        User(ad_username="ems", otp_method="NONE", expressms_id="chat-1", ldap_email="ems@corp.local")
    )
    db_session.commit()

    with patch("app.express_push.request_bot_push", return_value=True), patch(
        "app.express_push.wait_decision", return_value="approve"
    ):
        out = handle_access_request(db_session, "ems", "", None)
    assert out["decision"] == "accept"


def test_otp_only_express_push_deny_no_totp_fallback(db_session, fake_redis):
    secret = "JBSWY3DPEHPK3PXP"
    db_session.add(
        Policy(
            radius_scheme_preference="otp_only",
            mfa_scenario="express_push_then_totp",
            expressms_mode="push",
            push_wait_seconds=30,
        )
    )
    db_session.add(
        User(
            ad_username="ems2",
            otp_method="NONE",
            expressms_id="chat-2",
            ldap_email="e2@corp.local",
            totp_secret_encrypted=encrypt_totp_secret(secret),
            totp_confirmed=True,
        )
    )
    db_session.commit()

    with patch("app.express_push.request_bot_push", return_value=True), patch(
        "app.express_push.wait_decision", return_value="deny"
    ):
        out = handle_access_request(db_session, "ems2", pyotp.TOTP(secret).now(), None)
    assert out["decision"] == "reject"


def test_otp_only_express_push_timeout_falls_back_totp(db_session, fake_redis):
    secret = "JBSWY3DPEHPK3PXP"
    db_session.add(
        Policy(
            radius_scheme_preference="otp_only",
            mfa_scenario="express_push_then_totp",
            expressms_mode="push",
            push_wait_seconds=10,
        )
    )
    db_session.add(
        User(
            ad_username="ems3",
            otp_method="NONE",
            ldap_email="e3@corp.local",
            totp_secret_encrypted=encrypt_totp_secret(secret),
            totp_confirmed=True,
        )
    )
    db_session.commit()
    code = pyotp.TOTP(secret).now()

    with patch("app.express_push.request_bot_push", return_value=True), patch(
        "app.express_push.wait_decision", return_value="timeout"
    ):
        out = handle_access_request(db_session, "ems3", code, None)
    assert out["decision"] == "accept"


def test_otp_only_express_by_email_without_chat_id(db_session, fake_redis):
    db_session.add(Policy(radius_scheme_preference="otp_only", mfa_scenario="express_push"))
    db_session.add(User(ad_username="ems4", otp_method="NONE", ldap_email="e4@corp.local"))
    db_session.commit()

    with patch("app.express_push.request_bot_push", return_value=True), patch(
        "app.express_push.wait_decision", return_value="approve"
    ):
        out = handle_access_request(db_session, "ems4", "", None)
    assert out["decision"] == "accept"
