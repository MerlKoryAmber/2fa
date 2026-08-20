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
TOKEN = os.environ["INTERNAL_API_TOKEN"]
FALLBACK_SECRET = os.environ.get("RADIUS_SECRET", "testing123").encode()
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
        with httpx.Client(timeout=5.0) as client:
            r = client.get(
                f"{API}/internal/radius/config",
                headers={"X-Internal-Token": TOKEN},
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


def handle(data: bytes, addr) -> bytes | None:
    secret, allowed = _refresh_runtime()
    if not _is_allowed(addr[0], allowed):
        log.warning("rejected NAS %s (not in allowlist)", addr[0])
        return None
    pkt = AuthPacket(dict=DICT, secret=secret, packet=data)
    username = pkt["User-Name"][0] if "User-Name" in pkt else ""
    if isinstance(username, bytes):
        username = username.decode("utf-8", "replace")
    password = _pw(pkt)
    state = None
    if "State" in pkt:
        st = pkt["State"][0]
        state = st.decode("utf-8", "replace") if isinstance(st, bytes) else str(st)

    payload = {"username": username, "password": password, "state": state, "nas_ip": addr[0]}
    try:
        with httpx.Client(timeout=8.0) as client:
            r = client.post(
                f"{API}/internal/radius/access-request",
                json=payload,
                headers={"X-Internal-Token": TOKEN},
            )
            r.raise_for_status()
            result = r.json()
    except Exception:
        log.exception("API call failed")
        result = {"decision": "reject", "reply_message": "Internal error"}

    reply = pkt.CreateReply()
    decision = result.get("decision")
    msg = result.get("reply_message") or ""
    if msg:
        reply.AddAttribute("Reply-Message", msg.encode())
    if decision == "accept":
        reply.code = AccessAccept
    elif decision == "challenge":
        reply.code = AccessChallenge
        reply.AddAttribute("State", result["state"].encode())
    else:
        reply.code = AccessReject
    log.info("user=%s from=%s decision=%s", username, addr[0], decision)
    return reply.ReplyPacket()


def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((LISTEN, PORT))
    log.info("RADIUS listening on %s:%s", LISTEN, PORT)
    while True:
        data, addr = sock.recvfrom(8192)
        try:
            out = handle(data, addr)
            if out:
                sock.sendto(out, addr)
        except Exception:
            log.exception("packet from %s", addr)


if __name__ == "__main__":
    main()
