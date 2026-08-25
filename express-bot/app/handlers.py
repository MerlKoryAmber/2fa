from __future__ import annotations

import logging

from app.botx import CMD_APPROVE, CMD_DENY, lookup_by_email, push_bubble, send_notification, send_text
from app.incoming import CHAT_CREATED
from app import mk2fa

log = logging.getLogger("express-bot")

HELP = (
    "Бот подтверждения входа VPN (MK 2FA).\n"
    "/start — привязать этот чат к учёте по email из Express.\n"
    "Запросы входа приходят кнопками Approve / Deny."
)


async def handle_parsed(parsed: dict) -> None:
    cmd = parsed["cmd_body"]
    chat_id = parsed["chat_id"]
    cts = parsed["cts_host"]
    huid = parsed["user_huid"]
    email = parsed["user_email"]
    data = parsed["cmd_data"] or {}

    if not chat_id:
        log.warning("no chat_id cmd=%s", cmd)
        return

    if cmd in (CHAT_CREATED, "system:chat_created") or cmd.lower() in (
        "/start",
        "/старт",
        "/помощь",
        "/help",
    ):
        await send_text(chat_id, HELP, cts)
        if huid:
            await mk2fa.bind_user(
                email=email, huid=huid, chat_id=chat_id, name=parsed["user_name"]
            )
        return

    if cmd in (CMD_APPROVE, CMD_DENY):
        state = str(data.get("state") or "").strip()
        decision = "approve" if cmd == CMD_APPROVE else "deny"
        if not state:
            await send_text(chat_id, "Нет идентификатора входа.", cts)
            return
        out = await mk2fa.submit_decision(state=state, decision=decision, huid=huid)
        if out.get("ok"):
            text = "Вход разрешён." if decision == "approve" else "Вход отклонён."
        else:
            text = "Не удалось записать решение (истекло или уже обработано)."
        await send_text(chat_id, text, cts)
        return

    await send_text(chat_id, HELP, cts)


async def send_push(*, chat_id: str, email: str, state: str, username: str, cts_host: str) -> dict:
    target = (chat_id or "").strip()
    if not target and email:
        found = await lookup_by_email(email, cts_host)
        target = str(found.get("chat_id") or "").strip()
    if not target:
        return {"ok": False, "error": "no_chat"}
    await send_notification(target, push_bubble(state, username), cts_host)
    return {"ok": True, "chat_id": target}
