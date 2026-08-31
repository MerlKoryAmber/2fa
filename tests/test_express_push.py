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
        User(
            ad_username="ems",
            otp_method="NONE",
            express_channel_enabled=True,
            expressms_id="chat-1",
            ldap_email="ems@corp.local",
        )
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
            express_channel_enabled=True,
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


def test_otp_only_express_push_timeout_falls_back_totp_challenge(db_session, fake_redis):
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
            ad_username="ems3b",
            otp_method="NONE",
            express_channel_enabled=True,
            ldap_email="e3b@corp.local",
            totp_secret_encrypted=encrypt_totp_secret(secret),
            totp_confirmed=True,
        )
    )
    db_session.commit()

    with patch("app.express_push.request_bot_push", return_value=True), patch(
        "app.express_push.wait_decision", return_value="timeout"
    ):
        out = handle_access_request(db_session, "ems3b", "", None)
    assert out["decision"] == "challenge"
    assert out.get("state")


def test_otp_only_express_push_retry_totp_after_fallback_flag(db_session, fake_redis):
    secret = "JBSWY3DPEHPK3PXP"
    db_session.add(
        Policy(
            radius_scheme_preference="otp_only",
            mfa_scenario="express_push_then_totp",
            expressms_mode="push",
        )
    )
    user = User(
        ad_username="ems3c",
        otp_method="NONE",
        express_channel_enabled=True,
        ldap_email="e3c@corp.local",
        totp_secret_encrypted=encrypt_totp_secret(secret),
        totp_confirmed=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    from app.express_push import mark_push_fallback

    mark_push_fallback(user.id, 120)
    code = pyotp.TOTP(secret).now()
    out = handle_access_request(db_session, "ems3c", code, None)
    assert out["decision"] == "accept"


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
            express_channel_enabled=True,
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
    db_session.add(
        User(
            ad_username="ems4",
            otp_method="NONE",
            express_channel_enabled=True,
            ldap_email="e4@corp.local",
        )
    )
    db_session.commit()

    with patch("app.express_push.request_bot_push", return_value=True), patch(
        "app.express_push.wait_decision", return_value="approve"
    ):
        out = handle_access_request(db_session, "ems4", "", None)
    assert out["decision"] == "accept"


def test_express_push_disabled_without_flag(db_session, fake_redis):
    db_session.add(Policy(radius_scheme_preference="otp_only", mfa_scenario="express_push"))
    db_session.add(User(ad_username="ems5", otp_method="NONE", ldap_email="e5@corp.local"))
    db_session.commit()

    with patch("app.express_push.request_bot_push", return_value=True) as push:
        out = handle_access_request(db_session, "ems5", "", None)
    assert out["decision"] == "reject"
    push.assert_not_called()


def test_express_push_scenario_falls_back_to_totp_when_channel_off(db_session, fake_redis):
    secret = "JBSWY3DPEHPK3PXP"
    db_session.add(Policy(radius_scheme_preference="otp_only", mfa_scenario="express_push"))
    db_session.add(
        User(
            ad_username="ems6",
            otp_method="NONE",
            ldap_email="e6@corp.local",
            express_channel_enabled=False,
            totp_secret_encrypted=encrypt_totp_secret(secret),
            totp_confirmed=True,
        )
    )
    db_session.commit()
    code = pyotp.TOTP(secret).now()

    with patch("app.express_push.request_bot_push", return_value=True) as push:
        out = handle_access_request(db_session, "ems6", code, None)
    assert out["decision"] == "accept"
    push.assert_not_called()


def test_otp_only_express_push_ignores_totp_in_password(db_session, fake_redis):
    """express_push: даже если CP прислал TOTP в User-Password — проверяем только push."""
    secret = "JBSWY3DPEHPK3PXP"
    db_session.add(
        Policy(radius_scheme_preference="otp_only", mfa_scenario="express_push", expressms_mode="push")
    )
    db_session.add(
        User(
            ad_username="ems7",
            otp_method="NONE",
            express_channel_enabled=True,
            ldap_email="e7@corp.local",
            totp_secret_encrypted=encrypt_totp_secret(secret),
            totp_confirmed=True,
        )
    )
    db_session.commit()
    code = pyotp.TOTP(secret).now()

    with patch("app.express_push.request_bot_push", return_value=True) as push, patch(
        "app.express_push.wait_decision", return_value="approve"
    ):
        out = handle_access_request(db_session, "ems7", code, None)
    assert out["decision"] == "accept"
    push.assert_called_once()


def test_express_push_reuses_active_session(db_session, fake_redis):
    from app.express_push import set_active_push_state
    from app.models import OtpChallenge
    from app.otp import challenge_expiry

    db_session.add(Policy(radius_scheme_preference="otp_only", mfa_scenario="express_push", expressms_mode="push"))
    user = User(
        ad_username="ems8",
        otp_method="NONE",
        express_channel_enabled=True,
        ldap_email="e8@corp.local",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    state = "reuse-state-token-abc"
    db_session.add(
        OtpChallenge(
            state_token=state,
            user_id=user.id,
            method_used="EXPRESSMS",
            otp_hash=None,
            expires_at=challenge_expiry(120),
        )
    )
    db_session.commit()
    set_active_push_state(user.id, state, 120)

    with patch("app.express_push.request_bot_push", return_value=True) as push, patch(
        "app.express_push.wait_decision", return_value="approve"
    ):
        out = handle_access_request(db_session, "ems8", "", None)
    assert out["decision"] == "accept"
    push.assert_not_called()


def test_express_push_reuses_active_session(db_session, fake_redis):
    from app.express_push import set_active_push_state
    from app.models import OtpChallenge
    from app.otp import challenge_expiry

    db_session.add(Policy(radius_scheme_preference="otp_only", mfa_scenario="express_push", expressms_mode="push"))
    user = User(
        ad_username="ems8",
        otp_method="NONE",
        express_channel_enabled=True,
        ldap_email="e8@corp.local",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    state = "reuse-state-token-abc"
    db_session.add(
        OtpChallenge(
            state_token=state,
            user_id=user.id,
            method_used="EXPRESSMS",
            otp_hash=None,
            expires_at=challenge_expiry(120),
        )
    )
    db_session.commit()
    set_active_push_state(user.id, state, 120)

    with patch("app.express_push.request_bot_push", return_value=True) as push, patch(
        "app.express_push.wait_decision", return_value="approve"
    ):
        out = handle_access_request(db_session, "ems8", "", None)
    assert out["decision"] == "accept"
    push.assert_not_called()
