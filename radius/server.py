#!/usr/bin/env python3
import ipaddress
import logging
import os
import socket
import time

import httpx
from pyrad.dictionary import Dictionary
from pyrad.packet import AccessAccept, AccessChallenge, AccessReject, AuthPacket

log = logging.getLogger("radius")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

API = os.environ.get("API_URL", "http://api:8000")
HOST_ENV = "/run/mk2fa/host.env"
# Push hold в API до push_wait_seconds (до 300). 4 с — RADIUS обрывался до Approve.
API_TIMEOUT = float(os.environ.get("RADIUS_API_TIMEOUT", "120"))


def _clean_token(raw: str | None) -> str:
    return (raw or "").strip().strip('"').strip("'")


def _internal_token() -> str:
    if os.path.isfile(HOST_ENV):
        try:
            with open(HOST_ENV, encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    line = line.strip().lstrip("\ufeff")
                    if line.startswith("INTERNAL_API_TOKEN="):
                        t = _clean_token(line.split("=", 1)[1])
                        if t:
                            return t
        except OSError:
            pass
    t = _clean_token(os.environ.get("INTERNAL_API_TOKEN"))
    if not t:
        raise RuntimeError("INTERNAL_API_TOKEN missing (env and /run/mk2fa/host.env)")
    return t


FALLBACK_SECRET = os.environ.get("RADIUS_SECRET", "testing123").strip().encode()
LISTEN = os.environ.get("RADIUS_LISTEN", "0.0.0.0")
PORT = int(os.environ.get("RADIUS_PORT", "1812"))
DICT = Dictionary(os.path.join(os.path.dirname(__file__), "dictionary"))
_RUNTIME = {"secret": FALLBACK_SECRET, "allowed": [], "at": 0.0}


def _parse_allowed(raw: str) -> list[str]:
    if not raw or not str(raw).strip():
        return []
    out: list[str] = []
    for chunk in str(raw).replace(";", "\n").split("\n"):
        for item in chunk.split(","):
            item = item.strip()
            if item:
                out.append(item)
    return out


def _is_allowed(ip: str, rules: list[str]) -> bool:
    if not rules:
        return True
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    for rule in rules:
        try:
            if "/" in rule:
                if addr in ipaddress.ip_network(rule, strict=False):
                    return True
            elif addr == ipaddress.ip_address(rule):
                return True
        except ValueError:
            continue
    return False


def _refresh_runtime() -> tuple[bytes, list[str]]:
    if time.time() - _RUNTIME["at"] < 60:
        return _RUNTIME["secret"], _RUNTIME["allowed"]
    secret = FALLBACK_SECRET
    allowed: list[str] = []
    try:
        with httpx.Client(timeout=5.0, trust_env=False) as client:
            r = client.get(
                f"{API}/internal/radius/config",
                headers={
                    "X-Internal-Token": _internal_token(),
                    "Authorization": f"Bearer {_internal_token()}",
                },
            )
            r.raise_for_status()
            data = r.json()
            secret = data.get("shared_secret", FALLBACK_SECRET.decode()).encode()
            allowed = _parse_allowed(data.get("allowed_clients", ""))
            _RUNTIME["secret"] = secret
            _RUNTIME["allowed"] = allowed
            _RUNTIME["at"] = time.time()
    except Exception:
        log.exception("failed to refresh radius config from api")
    return _RUNTIME["secret"], _RUNTIME["allowed"]


def _pw(pkt: AuthPacket) -> str:
    if "User-Password" not in pkt:
        return ""
    raw = pkt["User-Password"][0]
    if isinstance(raw, str):
        return raw
    try:
        return pkt.PwDecrypt(raw)
    except Exception:
        return raw.decode("utf-8", "replace") if isinstance(raw, bytes) else str(raw)


def _notify_api(event_type: str, nas_ip: str, username: str = "", reason: str = "") -> None:
    try:
        with httpx.Client(timeout=2.0, trust_env=False) as client:
            client.post(
                f"{API}/internal/radius/event",
                json={
                    "event_type": event_type,
                    "username": username or None,
                    "nas_ip": nas_ip,
                    "reason": reason,
                },
                headers={
                    "X-Internal-Token": _internal_token(),
                    "Authorization": f"Bearer {_internal_token()}",
                },
            )
    except Exception:
        log.exception("audit event %s failed", event_type)


def handle(data: bytes, addr) -> bytes | None:
    secret, _allowed = _refresh_runtime()
    try:
        pkt = AuthPacket(dict=DICT, secret=secret, packet=data)
    except Exception:
        log.exception("bad RADIUS packet from %s (часто неверный shared secret)", addr[0])
        _notify_api("RADIUS_BAD_PACKET", addr[0], reason="decode")
        return None

    username = pkt["User-Name"][0] if "User-Name" in pkt else ""
    if isinstance(username, bytes):
        username = username.decode("utf-8", "replace")
    password = _pw(pkt)
    state = None
    if "State" in pkt:
        st = pkt["State"][0]
        state = st.decode("utf-8", "replace") if isinstance(st, bytes) else str(st)

    payload = {"username": username, "password": password, "state": state, "nas_ip": addr[0]}
    result = {"decision": "reject", "reply_message": "Internal error"}
    try:
        with httpx.Client(timeout=API_TIMEOUT, trust_env=False) as client:
            r = client.post(
                f"{API}/internal/radius/access-request",
                json=payload,
                headers={
                    "X-Internal-Token": _internal_token(),
                    "Authorization": f"Bearer {_internal_token()}",
                },
            )
            r.raise_for_status()
            result = r.json()
    except httpx.TimeoutException:
        log.exception("API access-request timeout")
        _notify_api("RADIUS_ERROR", addr[0], username=username, reason="timeout")
    except httpx.HTTPStatusError as exc:
        code = exc.response.status_code if exc.response is not None else 0
        log.exception("API access-request HTTP %s", code)
        _notify_api("RADIUS_ERROR", addr[0], username=username, reason=f"http_{code}")
    except httpx.ConnectError:
        log.exception("API access-request connect")
        _notify_api("RADIUS_ERROR", addr[0], username=username, reason="connect")
    except Exception:
        log.exception("API call failed")
        _notify_api("RADIUS_ERROR", addr[0], username=username, reason="api")

    reply = pkt.CreateReply()
    decision = result.get("decision")
    msg = result.get("reply_message") or ""
    if decision == "accept":
        reply.code = AccessAccept
    elif decision == "challenge":
        reply.code = AccessChallenge
    else:
        reply.code = AccessReject

    # BlastRADIUS / NPS: Message-Authenticator — первый атрибут ответа
    try:
        reply.add_message_authenticator()
    except Exception:
        log.exception("Message-Authenticator skip")

    # NPS как RADIUS Proxy: Proxy-State из запроса MUST вернуться без изменений
    if "Proxy-State" in pkt:
        for ps in pkt["Proxy-State"]:
            try:
                reply.AddAttribute("Proxy-State", ps)
            except Exception:
                log.exception("Proxy-State copy skip")

    if decision == "challenge":
        state_out = result.get("state") or ""
        try:
            reply.AddAttribute(
                "State",
                state_out.encode() if isinstance(state_out, str) else state_out,
            )
        except Exception:
            log.exception("State skip")

    if msg:
        try:
            reply.AddAttribute(
                "Reply-Message",
                msg if isinstance(msg, str) else msg.decode("utf-8", "replace"),
            )
        except Exception:
            log.exception("Reply-Message skip")

    out = reply.ReplyPacket()
    log.info(
        "user=%s from=%s:%s decision=%s reply_len=%s proxy_state=%s",
        username,
        addr[0],
        addr[1],
        decision,
        len(out),
        "Proxy-State" in pkt,
    )
    return out


def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((LISTEN, PORT))
    log.info("RADIUS listening on %s:%s api_timeout=%ss", LISTEN, PORT, API_TIMEOUT)
    while True:
        data, addr = sock.recvfrom(8192)
        try:
            out = handle(data, addr)
            if out:
                sent = sock.sendto(out, addr)
                log.info("sent %s bytes to %s:%s", sent, addr[0], addr[1])
        except Exception:
            log.exception("packet from %s", addr)


if __name__ == "__main__":
    main()
