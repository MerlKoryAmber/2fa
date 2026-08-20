import json
import re
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class LdapServer:
    host: str
    port: int


def default_ldap_port(use_ssl: bool) -> int:
    return 636 if use_ssl else 389


def domain_suffix_from_base_dn(base_dn: str) -> str:
    parts: list[str] = []
    for comp in base_dn.split(","):
        comp = comp.strip()
        if comp.upper().startswith("DC="):
            parts.append(comp[3:])
    return ".".join(parts)


def normalize_bind_user(raw: str, base_dn: str = "") -> str:
    """domain\\user → user@domain (если есть base DN), user@domain, username или legacy DN."""
    val = (raw or "").strip()
    if not val:
        return ""
    if "\\" in val:
        local, _domain = val.split("\\", 1)
        local = local.strip()
        suffix = domain_suffix_from_base_dn(base_dn)
        if suffix:
            return f"{local}@{suffix}"
        return val
    if "@" in val or val.upper().startswith("CN="):
        return val
    suffix = domain_suffix_from_base_dn(base_dn)
    if suffix:
        return f"{val}@{suffix}"
    return val


def bind_uses_ntlm(bind_user: str) -> bool:
    return "\\" in (bind_user or "")


def serialize_servers(servers: list[LdapServer]) -> str:
    return json.dumps([{"host": s.host, "port": s.port} for s in servers], ensure_ascii=False)


def server_from_dict(item: dict, use_ssl: bool) -> LdapServer | None:
    host = str(item.get("host") or "").strip()
    if not host:
        return None
    port_raw = item.get("port")
    if port_raw is None or port_raw == "":
        port = default_ldap_port(use_ssl)
    else:
        port = int(port_raw)
    return LdapServer(host=host, port=port)


def parse_servers_raw(raw: str, use_ssl: bool) -> list[LdapServer]:
    if not raw or not str(raw).strip():
        return []
    text = str(raw).strip()
    if text.startswith("["):
        try:
            data = json.loads(text)
            if isinstance(data, list):
                out: list[LdapServer] = []
                for item in data:
                    if isinstance(item, dict):
                        srv = server_from_dict(item, use_ssl)
                        if srv:
                            out.append(srv)
                return out
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    servers: list[LdapServer] = []
    for line in text.replace(";", "\n").split("\n"):
        line = line.strip()
        if not line:
            continue
        if "://" in line:
            parsed = urlparse(line)
            host = parsed.hostname or ""
            if not host:
                continue
            port = parsed.port or (636 if parsed.scheme == "ldaps" else 389)
            servers.append(LdapServer(host=host, port=port))
            continue
        if re.search(r":\d+\s*$", line):
            host, port_s = line.rsplit(":", 1)
            host = host.strip()
            if host:
                servers.append(LdapServer(host=host, port=int(port_s.strip())))
            continue
        servers.append(LdapServer(line, default_ldap_port(use_ssl)))
    return servers


def parse_legacy_url(url: str, use_ssl: bool) -> list[LdapServer]:
    if not url or not url.strip():
        return []
    parsed = urlparse(url.strip())
    host = parsed.hostname or ""
    if not host:
        return []
    port = parsed.port or default_ldap_port(use_ssl if parsed.scheme != "ldap" else False)
    if parsed.scheme == "ldaps":
        port = parsed.port or 636
    elif parsed.scheme == "ldap":
        port = parsed.port or 389
    return [LdapServer(host=host, port=port)]


def server_urls(servers: list[LdapServer], use_ssl: bool) -> list[str]:
    scheme = "ldaps" if use_ssl else "ldap"
    return [f"{scheme}://{s.host}:{s.port}" for s in servers]


LDAP_MATCHING_RULE_IN_CHAIN = "1.2.840.113556.1.4.1941"


def is_group_dn(value: str) -> bool:
    v = (value or "").strip()
    if not v:
        return False
    upper = v.upper()
    return upper.startswith("CN=") or ",CN=" in upper


def build_sync_user_filter(group_dn: str | None = None) -> str:
    """Фильтр пользователей AD для sync; group_dn — nested memberOf (IN_CHAIN)."""
    parts = ["(&(objectCategory=person)(objectClass=user)"]
    if group_dn:
        from ldap3.utils.conv import escape_filter_chars

        parts.append(f"(memberOf:{LDAP_MATCHING_RULE_IN_CHAIN}:={escape_filter_chars(group_dn)})")
    parts.append(")")
    return "".join(parts)
