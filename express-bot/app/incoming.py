CHAT_CREATED = "system:chat_created"


def _first(*vals: object) -> str:
    for v in vals:
        s = str(v or "").strip()
        if s:
            return s
    return ""


def _cmd_base(cmd: str) -> str:
    """/2fa_approve@bot → /2fa_approve"""
    c = (cmd or "").strip()
    if "@" in c:
        c = c.split("@", 1)[0].strip()
    return c


def parse_incoming(body: dict) -> dict:
    """BotX: command — dict {body,data} или строка; data иногда на верхнем уровне."""
    raw_cmd = body.get("command")
    frm = body.get("from") or {}
    cmd_data: dict = {}

    if isinstance(raw_cmd, dict):
        frm = frm or raw_cmd.get("from") or {}
        cmd_body = _first(raw_cmd.get("body"), body.get("body"))
        if isinstance(raw_cmd.get("data"), dict):
            cmd_data = dict(raw_cmd["data"])
    elif isinstance(raw_cmd, str):
        cmd_body = raw_cmd
    else:
        cmd_body = _first(body.get("body"))

    if not cmd_data and isinstance(body.get("data"), dict):
        cmd_data = dict(body["data"])

    cmd_body = _cmd_base(str(cmd_body or ""))

    user_name = _first(
        frm.get("user_name"),
        frm.get("username"),
        frm.get("name"),
        frm.get("display_name"),
        frm.get("full_name"),
        " ".join(
            p for p in (frm.get("last_name"), frm.get("first_name"), frm.get("middle_name")) if p
        ),
    )
    return {
        "cmd_body": cmd_body,
        "cmd_data": cmd_data,
        "user_huid": _first(frm.get("user_huid"), frm.get("huid")),
        "user_name": user_name,
        "user_email": _first(frm.get("email"), frm.get("user_email"), frm.get("mail"), frm.get("ad_login")),
        "chat_id": _first(frm.get("group_chat_id"), frm.get("chat_id")),
        "cts_host": _first(frm.get("host")),
    }


def should_ignore(parsed: dict) -> bool:
    cmd = parsed["cmd_body"]
    if not cmd:
        return True
    if cmd in (CHAT_CREATED, "system:chat_created"):
        return False
    if cmd.startswith("system:") and cmd not in (CHAT_CREATED, "system:chat_created"):
        return True
    if not parsed["user_huid"] and not parsed["user_name"] and not parsed["user_email"]:
        return True
    return False
