import ipaddress


def parse_allowed_clients(raw: str) -> list[str]:
    if not raw or not str(raw).strip():
        return []
    parts: list[str] = []
    for chunk in str(raw).replace(";", "\n").split("\n"):
        for item in chunk.split(","):
            item = item.strip()
            if item:
                parts.append(item)
    return parts


def is_client_allowed(ip: str, rules: list[str]) -> bool:
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
