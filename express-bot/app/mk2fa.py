from __future__ import annotations

import logging

import httpx

from app.config import settings
from app.internal_token import expected_internal_token

log = logging.getLogger("express-bot")


def _headers() -> dict[str, str]:
    token = expected_internal_token() or (settings.internal_api_token or "").strip()
    return {"X-Internal-Token": token, "Content-Type": "application/json"}


def _base() -> str:
    return (settings.mk2fa_api_url or "").strip().rstrip("/")


async def bind_user(*, email: str, huid: str, chat_id: str, name: str) -> dict:
    base = _base()
    if not base:
        return {"ok": False, "error": "mk2fa_url_empty"}
    async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
        r = await client.post(
            f"{base}/internal/express/bind",
            headers=_headers(),
            json={"email": email, "user_huid": huid, "chat_id": chat_id, "name": name},
        )
    if r.status_code >= 400:
        log.warning("mk2fa bind status=%s body=%s", r.status_code, r.text[:200])
        return {"ok": False, "error": f"http_{r.status_code}"}
    return r.json() if r.content else {"ok": True}


async def submit_decision(*, state: str, decision: str, huid: str) -> dict:
    base = _base()
    if not base:
        return {"ok": False, "error": "mk2fa_url_empty"}
    async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
        r = await client.post(
            f"{base}/internal/express/decision",
            headers=_headers(),
            json={"state": state, "decision": decision, "user_huid": huid},
        )
    if r.status_code >= 400:
        log.warning("mk2fa decision status=%s body=%s", r.status_code, r.text[:200])
        return {"ok": False, "error": f"http_{r.status_code}"}
    return r.json() if r.content else {"ok": True}
