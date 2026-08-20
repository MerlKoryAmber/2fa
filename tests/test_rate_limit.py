import pytest
from fastapi import HTTPException

from app.rate_limit import enforce_rate_limit


def test_rate_limit_blocks(fake_redis):
    for _ in range(3):
        enforce_rate_limit("t", "k", 3, 60)
    with pytest.raises(HTTPException) as exc:
        enforce_rate_limit("t", "k", 3, 60)
    assert exc.value.status_code == 429


def test_login_rate_limit_key(fake_redis):
    for i in range(10):
        enforce_rate_limit("login", f"admin:127.0.0.1", 10, 60)
    with pytest.raises(HTTPException):
        enforce_rate_limit("login", f"admin:127.0.0.1", 10, 60)
