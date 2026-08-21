import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client(fake_redis, monkeypatch):
    class _FakeSession:
        def execute(self, *_args, **_kwargs):
            return None

        def close(self):
            return None

    def fake_ping():
        yield _FakeSession()

    monkeypatch.setattr("app.main.ping_redis", lambda: True)
    monkeypatch.setattr("app.main.get_db_ping", fake_ping)
    return TestClient(app)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["db"] is True
    assert body["redis"] is True


def test_internal_radius_config_403_without_token(client):
    r = client.get("/internal/radius/config")
    assert r.status_code == 403


def test_internal_radius_config_403_wrong_token(client):
    r = client.get("/internal/radius/config", headers={"X-Internal-Token": "nope"})
    assert r.status_code == 403
