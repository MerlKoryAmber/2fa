"""Express push: бот на сервере 2FA, API пишет Approve/Deny в Redis."""

from __future__ import annotations

import logging
import time
from pathlib import Path

import httpx
import redis

from app.config import settings
from app.internal_token import expected_internal_token
from app.rate_limit import _redis

log = logging.getLogger(__name__)

KEY = "express_push:{state}"
FALLBACK_KEY = "express_push_fallback:{user_id}"
ACTIVE_KEY = "express_push_active:{user_id}"


def push_key(state: str) -> str:
    return KEY.format(state=state)


def fallback_key(user_id: int) -> str:
    return FALLBACK_KEY.format(user_id=user_id)


def mark_push_fallback(user_id: int, ttl: int) -> None:
    _redis().set(fallback_key(user_id), "1", ex=max(ttl, 30))


def clear_push_fallback(user_id: int) -> None:
    _redis().delete(fallback_key(user_id))


def push_fallback_active(user_id: int) -> bool:
    return bool(_redis().get(fallback_key(user_id)))


def active_push_key(user_id: int) -> str:
    return ACTIVE_KEY.format(user_id=user_id)


def get_active_push_state(user_id: int) -> str | None:
    val = _redis().get(active_push_key(user_id))
    return str(val) if val else None


def set_active_push_state(user_id: int, state: str, ttl: int) -> None:
    _redis().set(active_push_key(user_id), state, ex=max(ttl, 30))


def clear_active_push_state(user_id: int) -> None:
    _redis().delete(active_push_key(user_id))


def record_decision(state: str, decision: str, ttl: int) -> None:
    if decision not in ("approve", "deny"):
        raise ValueError("decision")
    _redis().set(push_key(state), decision, ex=max(ttl, 30))


def wait_decision(state: str, ttl: int) -> str:
    r: redis.Redis = _redis()
    deadline = time.time() + max(ttl, 1)
    key = push_key(state)
    while time.time() < deadline:
        val = r.get(key)
        if val in ("approve", "deny"):
            log.info("express push decision=%s state=%s", val, state[:12])
            return str(val)
        time.sleep(0.25)
    log.warning("express push timeout state=%s waited=%ss", state[:12], ttl)
    return "timeout"


def request_bot_push(*, state: str, username: str, email: str, chat_id: str) -> bool:
    base = (settings.express_bot_url or "").strip().rstrip("/")
    token = expected_internal_token() or (settings.internal_api_token or "").strip()
    if not base or not token:
        log.error(
            "express push skipped user=%s base_set=%s token_len=%s host_env=%s",
            username,
            bool(base),
            len(token),
            Path("/run/mk2fa/host.env").is_file(),
        )
        return False
    url = f"{base}/internal/push"
    try:
        # trust_env=False — иначе HTTP_PROXY перехватывает express-bot:8030 → чужой 403
        with httpx.Client(timeout=10.0, trust_env=False) as client:
            r = client.post(
                url,
                headers={"X-Internal-Token": token},
                json={
                    "state": state,
                    "username": username,
                    "email": email or "",
                    "chat_id": chat_id or "",
                },
            )
        r.raise_for_status()
        return True
    except httpx.HTTPStatusError as exc:
        body = (exc.response.text or "")[:300]
        log.error(
            "express bot push HTTP %s user=%s url=%s body=%s sent_token_len=%s host_env=%s",
            exc.response.status_code,
            username,
            url,
            body,
            len(token),
            Path("/run/mk2fa/host.env").is_file(),
        )
        return False
    except Exception:
        log.exception(
            "express bot push failed user=%s url=%s sent_token_len=%s host_env=%s",
            username,
            url,
            len(token),
            Path("/run/mk2fa/host.env").is_file(),
        )
        return False
