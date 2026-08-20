from app.panel_auth import _sam_from_login, upsert_ldap_panel_user
from app.rbac import ROLE_OPERATOR
from app.models import Admin


def test_sam_from_login():
    assert _sam_from_login("Merl\\alice") == "alice"
    assert _sam_from_login("alice@Merl.loc") == "alice"
    assert _sam_from_login("alice") == "alice"


def test_upsert_ldap_panel_user(db_session):
    row = upsert_ldap_panel_user(db_session, "alice", ROLE_OPERATOR)
    assert row.auth_source == "ldap"
    assert row.role == ROLE_OPERATOR
    assert row.password_hash is None
    row2 = upsert_ldap_panel_user(db_session, "alice", ROLE_OPERATOR)
    assert row2.id == row.id


def test_ad_login_sets_operator(db_session, fake_redis, monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.db import get_db
    from app.routers.auth import hash_password
    from app.rbac import ROLE_ADMIN

    db_session.add(
        Admin(
            username="admin",
            password_hash=hash_password("changeme12"),
            role=ROLE_ADMIN,
            is_active=True,
            auth_source="local",
        )
    )
    db_session.commit()

    monkeypatch.setattr(
        "app.panel_auth.resolve_ad_panel_role",
        lambda db, u, p: ("alice", ROLE_OPERATOR),
    )

    def _override():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override
    try:
        client = TestClient(app)
        r = client.post("/api/login", json={"username": "alice", "password": "AdPass1!"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["role"] == ROLE_OPERATOR
        assert body["auth_source"] == "ldap"
        assert body["username"] == "alice"
    finally:
        app.dependency_overrides.clear()
