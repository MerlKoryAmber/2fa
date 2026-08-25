from __future__ import annotations

import logging
import time
import uuid
from urllib.parse import urlparse

import httpx
import jwt

from app.config import botx_base, settings

log = logging.getLogger("express-bot")

CMD_APPROVE = "/2fa_approve"
CMD_DENY = "/2fa_deny"


def _audience(host: str) -> str:
    raw = (host or "").strip()
    if not raw:
        return ""
    if "://" not in raw:
        raw = "https://" + raw
    return urlparse(raw).hostname or raw.split("/")[0]


def make_token(api_host: str) -> str:
    if not settings.bot_id or not settings.bot_secret_key:
        raise RuntimeError("BOT_ID and BOT_SECRET_KEY are required")
    now = int(time.time())
    payload = {
        "iss": settings.bot_id,
        "aud": _audience(api_host),
        "exp": now + 60,
        "nbf": now,
        "iat": now,
        "jti": uuid.uuid4().hex,
        "version": 2,
    }
    return jwt.encode(payload, settings.bot_secret_key, algorithm="HS256")


def _headers(api_host: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {make_token(api_host)}",
        "Content-Type": "application/json",
    }


def api_host_for(cts_host: str) -> str:
    return botx_base() or (cts_host or "").rstrip("/")


async def send_notification(group_chat_id: str, notification: dict, cts_host: str = "") -> dict:
    host = api_host_for(cts_host)
    if not host:
        raise RuntimeError("BOTX_API_HOST is empty")
    url = f"{host}/api/v4/botx/notifications/direct/sync"
    payload = {"group_chat_id": group_chat_id, "notification": notification}
    async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
        r = await client.post(url, headers=_headers(host), json=payload)
    log.info("botx notify status=%s chat=%s", r.status_code, group_chat_id)
    if r.status_code not in (200, 202, 204) and r.status_code >= 300:
        raise RuntimeError(f"BotX send failed: {r.status_code} {r.text[:300]}")
    return r.json() if r.content else {}


async def send_text(chat_id: str, body: str, cts_host: str = "") -> dict:
    return await send_notification(chat_id, {"status": "ok", "body": body}, cts_host)


def push_bubble(state: str, username: str) -> dict:
    data = {"state": state, "username": username}
    return {
        "status": "ok",
        "body": f"Вход в VPN ({username}). Подтвердите вход.",
        "bubble": [
            [
                {
                    "command": CMD_APPROVE,
                    "label": "Approve",
                    "data": data,
                    "opts": {"silent": True},
                },
                {
                    "command": CMD_DENY,
                    "label": "Deny",
                    "data": data,
                    "opts": {"silent": True},
                },
            ]
        ],
    }


def _pick_huid(data: dict) -> str:
    result = data.get("result") if isinstance(data.get("result"), dict) else data
    if not isinstance(result, dict):
        return ""
    return str(
        result.get("user_huid")
        or result.get("huid")
        or (result.get("user") or {}).get("user_huid")
        or ""
    ).strip()


def _pick_chat(data: dict) -> str:
    result = data.get("result") if isinstance(data.get("result"), dict) else data
    if not isinstance(result, dict):
        return ""
    return str(
        result.get("group_chat_id")
        or result.get("chat_id")
        or (result.get("chat") or {}).get("group_chat_id")
        or ""
    ).strip()


async def lookup_by_email(email: str, cts_host: str = "") -> dict:
    """Ищем huid/chat в BotX. Формат ответа на on-prem разный — парсим мягко."""
    host = api_host_for(cts_host)
    if not host or not email:
        return {}
    headers = _headers(host)
    async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
        r = await client.get(
            f"{host}/api/v3/botx/users/by_email",
            headers=headers,
            params={"email": email},
        )
        if r.status_code >= 400:
            r = await client.get(
                f"{host}/api/v4/botx/users/by_email",
                headers=headers,
                params={"email": email},
            )
        if r.status_code >= 400:
            log.warning("botx by_email status=%s email=%s", r.status_code, email)
            return {}
        data = r.json() if r.content else {}
        huid = _pick_huid(data)
        chat_id = _pick_chat(data)
        if huid and not chat_id:
            cr = await client.get(
                f"{host}/api/v3/botx/chats/personal",
                headers=headers,
                params={"user_huid": huid},
            )
            if cr.status_code < 400 and cr.content:
                chat_id = _pick_chat(cr.json())
        return {"user_huid": huid, "chat_id": chat_id}
