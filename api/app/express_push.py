"""Express push: бот на сервере 2FA, API пишет Approve/Deny в Redis."""

from __future__ import annotations

import logging
import time

import httpx
import redis

from app.config import settings
from app.internal_token import expected_internal_token
from app.rate_limit import _redis

log = logging.getLogger(__name__)

KEY = "express_push:{state}"


def push_key(state: str) -> str:
    return KEY.format(state=state)


def record_decision(state: str, decision: str, ttl: int) -> None:
    if decision not in ("approve", "deny"):
        raise ValueError("decision")
    _redis().set(push_key(state), decision, ex=max(ttl, 30))


def wait_decision(state: str, ttl: int) -> str:
    r: redis.Redis = _redis()
    deadline = time.time() + max(ttl, 1)
    while time.time() < deadline:
        val = r.get(push_key(state))
        if val in ("approve", "deny"):
            return str(val)
        time.sleep(0.4)
    return "timeout"


def request_bot_push(*, state: str, username: str, email: str, chat_id: str) -> bool:
    base = (settings.express_bot_url or "").strip().rstrip("/")
    token = expected_internal_token() or (settings.internal_api_token or "").strip()
    if not base or not token:
        log.error("express push skipped: EXPRESS_BOT_URL or INTERNAL_API_TOKEN empty")
        return False
    try:
        r = httpx.post(
            f"{base}/internal/push",
            headers={"X-Internal-Token": token},
            json={
                "state": state,
                "username": username,
                "email": email or "",
                "chat_id": chat_id or "",
            },
            timeout=10.0,
        )
        r.raise_for_status()
        return True
    except Exception:
        log.exception("express bot push failed user=%s", username)
        return False
