from unittest.mock import patch

from app.models import Policy, User
from app.radius_flow import handle_access_request


def test_otp_only_totp_untouched_when_express_push_on_other_users(db_session, seeded_user, fake_redis):
    p = db_session.query(Policy).first()
    p.radius_scheme_preference = "otp_only"
    p.expressms_mode = "push"
    db_session.commit()
    import pyotp

    code = pyotp.TOTP("JBSWY3DPEHPK3PXP").now()
    out = handle_access_request(db_session, "demo", code, None)
    assert out["decision"] == "accept"


def test_otp_only_express_push_approve(db_session, fake_redis):
    db_session.add(Policy(radius_scheme_preference="otp_only", expressms_mode="push"))
    db_session.add(
        User(ad_username="ems", otp_method="EXPRESSMS", expressms_id="chat-1", ldap_email="ems@corp.local")
    )
    db_session.commit()

    with patch("app.express_push.request_bot_push", return_value=True), patch(
        "app.express_push.wait_decision", return_value="approve"
    ):
        out = handle_access_request(db_session, "ems", "", None)
    assert out["decision"] == "accept"


def test_otp_only_express_push_deny(db_session, fake_redis):
    db_session.add(Policy(radius_scheme_preference="otp_only", expressms_mode="push"))
    db_session.add(User(ad_username="ems2", otp_method="EXPRESSMS", expressms_id="chat-2"))
    db_session.commit()

    with patch("app.express_push.request_bot_push", return_value=True), patch(
        "app.express_push.wait_decision", return_value="deny"
    ):
        out = handle_access_request(db_session, "ems2", "", None)
    assert out["decision"] == "reject"
