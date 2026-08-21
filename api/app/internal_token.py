"""Токен radius→api: один источник — смонтированный хостовый .env, иначе os.environ."""

from __future__ import annotations

import os
from pathlib import Path

HOST_ENV = Path("/run/mk2fa/host.env")


def clean_token(raw: str | None) -> str:
    return (raw or "").strip().strip('"').strip("'")


def token_from_host_env_file(path: Path | None = None) -> str:
    p = path or HOST_ENV
    if not p.is_file():
        return ""
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    for line in text.splitlines():
        line = line.strip().lstrip("\ufeff")
        if line.startswith("INTERNAL_API_TOKEN="):
            return clean_token(line.split("=", 1)[1])
    return ""


def expected_internal_token() -> str:
    return token_from_host_env_file() or clean_token(os.environ.get("INTERNAL_API_TOKEN"))


def got_internal_token(request) -> str:
    got = clean_token(request.headers.get("x-internal-token"))
    if got:
        return got
    auth = request.headers.get("authorization") or ""
    if auth.lower().startswith("bearer "):
        return clean_token(auth[7:])
    return ""
