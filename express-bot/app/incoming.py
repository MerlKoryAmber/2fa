CHAT_CREATED = "system:chat_created"


def _first(*vals: object) -> str:
    for v in vals:
        s = str(v or "").strip()
        if s:
            return s
    return ""


def parse_incoming(body: dict) -> dict:
    command = body.get("command") or {}
    frm = body.get("from") or {}
    if isinstance(command, dict) and not frm:
        frm = command.get("from") or {}
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
        "cmd_body": _first(command.get("body"), body.get("body")).strip(),
        "cmd_data": command.get("data") if isinstance(command.get("data"), dict) else {},
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
