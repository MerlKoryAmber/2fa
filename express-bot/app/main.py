from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.internal_token import expected_internal_token
from app.handlers import handle_parsed, send_push
from app.incoming import parse_incoming, should_ignore

log = logging.getLogger("express-bot")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def _check_internal(token: str | None) -> None:
    exp = expected_internal_token() or (settings.internal_api_token or "").strip()
    got = (token or "").strip()
    if not exp or got != exp:
        log.warning("internal push reject got_len=%s exp_len=%s", len(got), len(exp))
        raise HTTPException(403, "forbidden")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    log.info(
        "express-bot listen=%s:%s bot_id_set=%s api_host_set=%s",
        settings.bot_listen_host,
        settings.bot_listen_port,
        bool(settings.bot_id),
        bool(settings.botx_api_host),
    )
    yield


app = FastAPI(title="MK 2FA Express bot", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health():
    return {"ok": True, "app": settings.bot_app_id}


@app.get("/status")
@app.post("/status")
def status():
    return {
        "status": "ok",
        "result": {
            "commands": [
                {"body": "/start", "name": "Старт", "description": "Привязка чата"},
                {"body": "/помощь", "name": "Помощь", "description": "Справка"},
            ]
        },
    }


@app.post("/command")
async def command(body: dict, background: BackgroundTasks):
    parsed = parse_incoming(body)
    if not should_ignore(parsed):
        background.add_task(handle_parsed, parsed)
    return {"status": "ok"}


@app.post("/notification/callback")
def notification_callback(body: dict | None = None):
    if isinstance(body, dict) and body.get("status") == "error":
        log.error("botx delivery error keys=%s", list(body.keys()))
    return {"status": "ok"}


class PushIn(BaseModel):
    state: str
    username: str
    email: str = ""
    chat_id: str = ""
    cts_host: str = ""


@app.post("/internal/push")
async def internal_push(body: PushIn, x_internal_token: str | None = Header(default=None)):
    _check_internal(x_internal_token)
    out = await send_push(
        chat_id=body.chat_id,
        email=body.email,
        state=body.state,
        username=body.username,
        cts_host=body.cts_host,
    )
    if not out.get("ok"):
        raise HTTPException(400, out)
    return out
