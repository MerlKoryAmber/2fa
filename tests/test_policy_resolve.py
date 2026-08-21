from app.models import Policy
from app.policy_resolve import best_scope_score, default_policy, resolve_policy, scope_token_score
from app.radius_flow import handle_access_request
import pyotp


def test_scope_token_specificity():
    assert scope_token_score("10.1.2.3", "*") == 0
    assert scope_token_score("10.1.2.3", "10.1.2.3") == 32
    assert scope_token_score("10.1.2.3", "10.1.2.0/24") == 24
    assert scope_token_score("10.1.2.3", "10.0.0.0/8") == 8
    assert scope_token_score("10.1.2.3", "192.168.0.1") is None


def test_best_scope_score_list():
    assert best_scope_score("203.0.113.10", "10.0.0.0/8, 203.0.113.10") == 32
    assert best_scope_score("203.0.113.5", "203.0.113.0/24") == 24


def test_resolve_prefers_narrower(db_session):
    wide = Policy(name="Default", scope="*", radius_scheme_preference="challenge")
    narrow = Policy(name="nps", scope="203.0.113.10", radius_scheme_preference="otp_only")
    db_session.add_all([wide, narrow])
    db_session.commit()
    assert resolve_policy(db_session, "203.0.113.10").name == "nps"
    assert resolve_policy(db_session, "10.0.0.1").name == "Default"
    assert resolve_policy(db_session, None).name == "Default"
    assert default_policy(db_session).name == "Default"


def test_cidr_beats_star(db_session):
    star = Policy(name="Default", scope="*", radius_scheme_preference="challenge")
    net = Policy(name="corp", scope="10.0.0.0/8", radius_scheme_preference="otp_only")
    db_session.add_all([star, net])
    db_session.commit()
    assert resolve_policy(db_session, "10.1.2.3").name == "corp"


def test_single_star_policy_unchanged(db_session, seeded_user, fake_redis):
    """Одна политика * + otp_only — как раньше, без nas_ip и с nas_ip."""
    p = db_session.query(Policy).first()
    p.radius_scheme_preference = "otp_only"
    p.scope = "*"
    db_session.commit()
    code = pyotp.TOTP("JBSWY3DPEHPK3PXP").now()
    assert handle_access_request(db_session, "demo", code, None)["decision"] == "accept"
    assert handle_access_request(db_session, "demo", code, None, nas_ip="203.0.113.10")["decision"] == "accept"


def test_per_client_otp_only(db_session, seeded_user, fake_redis, ldap_ok, monkeypatch):
    p = db_session.query(Policy).first()
    p.scope = "*"
    p.radius_scheme_preference = "challenge"
    db_session.add(
        Policy(name="nps", scope="203.0.113.10", radius_scheme_preference="otp_only", require_2fa=True)
    )
    db_session.commit()
    code = pyotp.TOTP("JBSWY3DPEHPK3PXP").now()
    # NPS peer → otp_only, LDAP не трогаем
    monkeypatch.setattr(
        "app.radius_flow.authenticate_ldap",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("LDAP must not run for nps")),
    )
    assert handle_access_request(db_session, "demo", code, None, nas_ip="203.0.113.10")["decision"] == "accept"
    # другой клиент → challenge, нужен LDAP+пароль, не OTP как password
    monkeypatch.setattr("app.radius_flow.authenticate_ldap", lambda *a, **k: True)
    out = handle_access_request(db_session, "demo", "demo-password", None, nas_ip="10.0.0.9")
    assert out["decision"] == "challenge"
