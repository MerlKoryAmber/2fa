from app.ldap_auth import _parse_mock_users
from app.ldap_sync import run_ldap_sync
from app.models import Policy, User


def test_parse_mock_users_display_name():
    rows = _parse_mock_users("demo:demo@lab.local:Demo User,alice:alice@lab.local")
    assert rows[0]["display_name"] == "Demo User"
    assert rows[1]["display_name"] is None


def test_ldap_sync_display_name(db_session):
    db_session.add(Policy())
    db_session.commit()
    from app.settings_service import set_raw

    set_raw(db_session, "ldap.mock", "true")
    set_raw(db_session, "ldap.mock_users", "bob:bob@lab.local:Bob Test")
    out = run_ldap_sync(db_session, by="test")
    assert out["ok"] is True
    user = db_session.query(User).filter(User.ad_username == "bob").first()
    assert user is not None
    assert user.display_name == "Bob Test"
    assert user.ldap_email == "bob@lab.local"
