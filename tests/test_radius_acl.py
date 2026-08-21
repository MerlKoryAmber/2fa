from app.radius_acl import is_client_allowed, parse_allowed_clients
from app.settings_service import RadiusConfig


def test_parse_allowed_empty():
    assert parse_allowed_clients("") == []
    assert parse_allowed_clients("  \n  ") == []


def test_parse_allowed_multiline():
    assert parse_allowed_clients("10.0.0.1\n192.168.0.0/24, 172.16.1.2") == [
        "10.0.0.1",
        "192.168.0.0/24",
        "172.16.1.2",
    ]


def test_is_client_allowed_open():
    assert is_client_allowed("1.2.3.4", []) is True


def test_is_client_allowed_ip():
    rules = ["192.168.1.10", "10.0.0.0/8"]
    assert is_client_allowed("192.168.1.10", rules) is True
    assert is_client_allowed("10.5.5.5", rules) is True
    assert is_client_allowed("8.8.8.8", rules) is False


def test_radius_config_allowed_rules():
    cfg = RadiusConfig(shared_secret="x", port=1812, allowed_clients="10.0.0.1, 10.0.0.0/8")
    assert cfg.allowed_rules() == ["10.0.0.1", "10.0.0.0/8"]
    assert RadiusConfig(shared_secret="x", port=1812, allowed_clients="").allowed_rules() == []
