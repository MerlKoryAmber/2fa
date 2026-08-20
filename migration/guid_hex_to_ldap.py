#!/usr/bin/env python3
"""Хелпер для Merl: hex objectGUID (как в LinOTP) → LDAP-фильтр / строка GUID.

Пример:
  python3 migration/guid_hex_to_ldap.py 0a7b4f3aabc8d24e8df3b7a0a75173ce

Вывод:
  hex: ...
  ldap_filter: (objectGUID=\\0a\\7b\\...)
  guid_string: 3a4f7b0a-c8ab-4ed2-8df3-b7a0a75173ce   # если интерпретировать как MS GUID

Сам поиск в AD — на машине Merl (у агента живого LDAP нет).
"""
from __future__ import annotations

import sys


def ms_guid_string(hex32: str) -> str:
    """Microsoft GUID string из 16 байт objectGUID (mixed-endian)."""
    b = bytes.fromhex(hex32)
    if len(b) != 16:
        raise ValueError("нужно 32 hex-символа")
    # DWORD, WORD, WORD little-endian, затем 8 bytes as-is
    d1 = int.from_bytes(b[0:4], "little")
    d2 = int.from_bytes(b[4:6], "little")
    d3 = int.from_bytes(b[6:8], "little")
    rest = b[8:16].hex()
    return f"{d1:08x}-{d2:04x}-{d3:04x}-{rest[:4]}-{rest[4:]}"


def ldap_filter(hex32: str) -> str:
    b = bytes.fromhex(hex32)
    esc = "".join(f"\\{x:02x}" for x in b)
    return f"(objectGUID={esc})"


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    h = sys.argv[1].strip().lower().replace("{", "").replace("}", "").replace("-", "")
    if len(h) != 32:
        print("ожидали 32 hex", file=sys.stderr)
        return 1
    print(f"hex: {h}")
    print(f"ldap_filter: {ldap_filter(h)}")
    print(f"guid_string: {ms_guid_string(h)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
