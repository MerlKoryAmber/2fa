from app.botx import _audience, make_token, push_bubble
from app.config import settings
from app.incoming import CHAT_CREATED, parse_incoming, should_ignore


def test_parse_command_and_button():
    parsed = parse_incoming(
        {
            "command": {"body": "/2fa_approve", "data": {"state": "abc"}},
            "from": {
                "user_huid": "h-1",
                "group_chat_id": "c-1",
                "host": "hbotx.example",
                "email": "u@corp.local",
                "username": "Ivan",
            },
        }
    )
    assert parsed["cmd_body"] == "/2fa_approve"
    assert parsed["cmd_data"]["state"] == "abc"
    assert parsed["chat_id"] == "c-1"
    assert parsed["user_email"] == "u@corp.local"
    assert not should_ignore(parsed)


def test_ignore_system_except_chat_created():
    assert should_ignore(parse_incoming({"command": {"body": "system:ping"}, "from": {"user_huid": "h"}}))
    p = parse_incoming(
        {"command": {"body": CHAT_CREATED}, "from": {"user_huid": "h", "group_chat_id": "c"}}
    )
    assert not should_ignore(p)


def test_jwt_audience_and_iss(monkeypatch):
    monkeypatch.setattr(settings, "bot_id", "74633ae5-c392-5718-bebb-f3768fa953c7")
    monkeypatch.setattr(settings, "bot_secret_key", "secret")
    token = make_token("http://cts.example:9000/path")
    import jwt

    data = jwt.decode(token, "secret", algorithms=["HS256"], audience="cts.example")
    assert data["iss"] == "74633ae5-c392-5718-bebb-f3768fa953c7"
    assert data["version"] == 2
    assert _audience("https://exb.example") == "exb.example"


def test_bubble_silent_commands():
    n = push_bubble("st1", "jdoe")
    row = n["bubble"][0]
    assert {b["command"] for b in row} == {"/2fa_approve", "/2fa_deny"}
    assert all(b["opts"]["silent"] is True for b in row)
    assert all(b["data"]["state"] == "st1" for b in row)
