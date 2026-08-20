from app.ldap_sync import run_ldap_sync
from app.models import Policy, User


def test_ldap_sync_display_name(db_session, monkeypatch):
    db_session.add(Policy())
    db_session.commit()

    monkeypatch.setattr(
        "app.ldap_sync.list_ldap_users",
        lambda cfg, limit=500: ([{"username": "bob", "email": "bob@lab.local", "display_name": "Bob Test"}], None),
    )
    out = run_ldap_sync(db_session, by="test")
    assert out["ok"] is True
    user = db_session.query(User).filter(User.ad_username == "bob").first()
    assert user is not None
    assert user.display_name == "Bob Test"
    assert user.ldap_email == "bob@lab.local"
