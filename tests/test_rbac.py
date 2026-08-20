from app.models import Admin
from app.routers.auth import create_token, hash_password, pwd
from app.rbac import ROLE_ADMIN


def _add_admin(db, username, role, password="password1"):
    row = Admin(username=username, password_hash=hash_password(password), role=role, is_active=True)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_login_returns_role(db_session, fake_redis):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.db import get_db

    _add_admin(db_session, "admin", ROLE_ADMIN, "changeme12")

    def _override():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override
    try:
        client = TestClient(app)
        r = client.post("/api/login", json={"username": "admin", "password": "changeme12"})
        assert r.status_code == 200
        body = r.json()
        assert body["role"] == ROLE_ADMIN
        assert "token" in body
    finally:
        app.dependency_overrides.clear()


def test_change_password(db_session, fake_redis):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.db import get_db

    row = _add_admin(db_session, "admin", ROLE_ADMIN, "oldpass12")

    def _override():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override
    try:
        client = TestClient(app)
        token = create_token("admin")
        r = client.post(
            "/api/me/password",
            headers={"Authorization": f"Bearer {token}"},
            json={"current_password": "oldpass12", "new_password": "newpass99"},
        )
        assert r.status_code == 200
        db_session.refresh(row)
        assert pwd.verify("newpass99", row.password_hash)
    finally:
        app.dependency_overrides.clear()


def test_operator_forbidden_settings(db_session, fake_redis):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.db import get_db
    from app.rbac import ROLE_OPERATOR

    _add_admin(db_session, "op1", ROLE_OPERATOR, "password1")

    def _override():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override
    try:
        client = TestClient(app)
        token = create_token("op1")
        r = client.get("/api/settings", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 403
        r2 = client.get("/api/tokens", headers={"Authorization": f"Bearer {token}"})
        assert r2.status_code == 200
    finally:
        app.dependency_overrides.clear()
