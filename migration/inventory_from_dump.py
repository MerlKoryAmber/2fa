#!/usr/bin/env python3
"""Inventory LinOTP Token из mysqldump — без KeyEnc/KeyIV в отчётах.

Вход:  /root/linotp-migrate/incoming/linotp.sql
Выход: /root/linotp-migrate/reports/inventory_<stamp>.{txt,csv}
"""
from __future__ import annotations

import csv
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

INCOMING = Path("/root/linotp-migrate/incoming/linotp.sql")
REPORTS = Path("/root/linotp-migrate/reports")
MSK = timezone(timedelta(hours=3))

# Порядок колонок = CREATE TABLE Token в дампе LinOTP 3.2.3
COLS = [
    "LinOtpTokenId",
    "LinOtpTokenDesc",
    "LinOtpTokenSerialnumber",
    "LinOtpTokenType",
    "LinOtpTokenInfo",
    "LinOtpTokenPinUser",
    "LinOtpTokenPinUserIV",
    "LinOtpTokenPinSO",
    "LinOtpTokenPinSOIV",
    "LinOtpIdResolver",
    "LinOtpIdResClass",
    "LinOtpUserid",
    "LinOtpSeed",
    "LinOtpOtpLen",
    "LinOtpPinHash",
    "LinOtpKeyEnc",
    "LinOtpKeyIV",
    "LinOtpMaxFail",
    "LinOtpIsactive",
    "LinOtpFailCount",
    "LinOtpCount",
    "LinOtpCountWindow",
    "LinOtpSyncWindow",
    "LinOtpCreationDate",
    "LinOtpLastAuthSuccess",
    "LinOtpLastAuthMatch",
]

SAFE_CSV_COLS = [
    "LinOtpTokenId",
    "LinOtpTokenSerialnumber",
    "LinOtpTokenType",
    "LinOtpIsactive",
    "LinOtpUserid",
    "LinOtpIdResolver",
    "LinOtpOtpLen",
    "LinOtpCreationDate",
    "LinOtpLastAuthSuccess",
    "has_keyenc",
]

BASELINE = {
    "totp_total": 302,
    "totp_active": 301,
    "hmac_active": 4,
    "users_with_active_totp": 267,
    "active_totp_empty_userid": 6,
}

# Политика переноса (Merl 2026-08-20): старше 2026-01-01 не переносим.
# Сравнение по LinOtpCreationDate (naive, как в дампе).
MIGRATE_FROM = datetime(2026, 1, 1)


def msk_stamp() -> str:
    return datetime.now(MSK).strftime("%Y%m%d-%H%M")


def sql_unquote(s: str) -> str | None:
    if s.upper() == "NULL":
        return None
    if len(s) >= 2 and s[0] == "'" and s[-1] == "'":
        inner = s[1:-1]
        return (
            inner.replace("\\'", "'")
            .replace('\\"', '"')
            .replace("\\\\", "\\")
            .replace("\\n", "\n")
            .replace("\\r", "\r")
            .replace("\\0", "\0")
            .replace("\\Z", "\x1a")
        )
    return s


def split_sql_values(values_blob: str) -> list[list[str]]:
    """Разбор (...),(...),... с учётом строк в кавычках."""
    rows: list[list[str]] = []
    i = 0
    n = len(values_blob)
    while i < n:
        while i < n and values_blob[i] in " \t\r\n,":
            i += 1
        if i >= n:
            break
        if values_blob[i] != "(":
            raise ValueError(f"ожидали '(' at {i}: {values_blob[i : i + 40]!r}")
        i += 1
        fields: list[str] = []
        field_chars: list[str] = []
        in_str = False
        escape = False
        while i < n:
            ch = values_blob[i]
            if in_str:
                field_chars.append(ch)
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == "'":
                    in_str = False
                i += 1
                continue
            if ch == "'":
                in_str = True
                field_chars.append(ch)
                i += 1
                continue
            if ch == ",":
                fields.append("".join(field_chars).strip())
                field_chars = []
                i += 1
                continue
            if ch == ")":
                fields.append("".join(field_chars).strip())
                i += 1
                break
            field_chars.append(ch)
            i += 1
        else:
            raise ValueError("незакрытая строка VALUES")
        rows.append(fields)
    return rows


def extract_token_insert(sql_text: str) -> str:
    m = re.search(
        r"INSERT INTO `Token` VALUES\s*(.+?);\s*\n",
        sql_text,
        flags=re.DOTALL,
    )
    if not m:
        raise SystemExit("INSERT INTO `Token` не найден в дампе")
    return m.group(1)


def rows_to_dicts(raw_rows: list[list[str]]) -> list[dict]:
    out = []
    for fields in raw_rows:
        if len(fields) != len(COLS):
            raise SystemExit(
                f"колонок {len(fields)} != {len(COLS)} (serial={fields[2] if len(fields) > 2 else '?'})"
            )
        d = {c: sql_unquote(v) for c, v in zip(COLS, fields)}
        d["has_keyenc"] = "1" if d.get("LinOtpKeyEnc") else "0"
        # не тащим секреты дальше
        d.pop("LinOtpKeyEnc", None)
        d.pop("LinOtpKeyIV", None)
        d.pop("LinOtpTokenPinUser", None)
        d.pop("LinOtpTokenPinUserIV", None)
        d.pop("LinOtpTokenPinSO", None)
        d.pop("LinOtpTokenPinSOIV", None)
        d.pop("LinOtpPinHash", None)
        out.append(d)
    return out


def is_active(row: dict) -> bool:
    v = row.get("LinOtpIsactive")
    return str(v) in ("1", "true", "True")


def parse_creation(row: dict) -> datetime | None:
    s = (row.get("LinOtpCreationDate") or "").strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:19], fmt)
        except ValueError:
            continue
    return None


def in_migrate_scope(row: dict) -> bool:
    """True = переносим (creation >= MIGRATE_FROM)."""
    dt = parse_creation(row)
    if dt is None:
        return False
    return dt >= MIGRATE_FROM


def summarize(rows: list[dict]) -> str:
    by_type = Counter((r.get("LinOtpTokenType") or "").lower() for r in rows)
    active_by_type = Counter(
        (r.get("LinOtpTokenType") or "").lower() for r in rows if is_active(r)
    )
    totp = [r for r in rows if (r.get("LinOtpTokenType") or "").lower() == "totp"]
    totp_a = [r for r in totp if is_active(r)]
    empty_uid = [r for r in totp_a if not (r.get("LinOtpUserid") or "").strip()]
    users = defaultdict(int)
    for r in totp_a:
        uid = (r.get("LinOtpUserid") or "").strip()
        if uid:
            users[uid] += 1
    multi = sum(1 for c in users.values() if c > 1)

    scope_a = [r for r in totp_a if in_migrate_scope(r)]
    skip_a = [r for r in totp_a if not in_migrate_scope(r)]
    scope_users: dict[str, int] = defaultdict(int)
    scope_empty = 0
    for r in scope_a:
        uid = (r.get("LinOtpUserid") or "").strip()
        if not uid:
            scope_empty += 1
        else:
            scope_users[uid] += 1
    scope_multi = sum(1 for c in scope_users.values() if c > 1)

    lines = [
        f"# LinOTP inventory {datetime.now(MSK).strftime('%Y-%m-%d %H:%M')} МСК",
        f"дамп: {INCOMING}",
        f"всего Token: {len(rows)}",
        f"политика переноса: LinOtpCreationDate >= {MIGRATE_FROM.date().isoformat()}",
        "",
        "## по типу (все / active)",
    ]
    for t in sorted(set(by_type) | set(active_by_type)):
        lines.append(f"- {t or '(empty)'}: {by_type[t]} / active {active_by_type[t]}")
    lines += [
        "",
        "## сверка с baseline (ранее на HOTP)",
        f"- totp всего: {len(totp)}  (baseline {BASELINE['totp_total']})  "
        f"{'OK' if len(totp) == BASELINE['totp_total'] else 'DIFF'}",
        f"- totp active: {len(totp_a)}  (baseline {BASELINE['totp_active']})  "
        f"{'OK' if len(totp_a) == BASELINE['totp_active'] else 'DIFF'}",
        f"- hmac active: {active_by_type.get('hmac', 0)}  (baseline {BASELINE['hmac_active']})  "
        f"{'OK' if active_by_type.get('hmac', 0) == BASELINE['hmac_active'] else 'DIFF'}",
        f"- юзеров с ≥1 active totp: {len(users)}  (baseline {BASELINE['users_with_active_totp']})  "
        f"{'OK' if len(users) == BASELINE['users_with_active_totp'] else 'DIFF'}",
        f"- active totp с пустым userid: {len(empty_uid)}  "
        f"(baseline {BASELINE['active_totp_empty_userid']})  "
        f"{'OK' if len(empty_uid) == BASELINE['active_totp_empty_userid'] else 'DIFF'}",
        f"- userid с >1 active totp: {multi}",
        "",
        "## scope миграции B (creation >= 2026-01-01, active totp)",
        f"- in scope: {len(scope_a)}",
        f"- skip (старше / без даты): {len(skip_a)}",
        f"- юзеров (non-empty userid): {len(scope_users)}",
        f"- пустой userid: {scope_empty}",
        f"- userid с >1 totp в scope: {scope_multi}",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    if not INCOMING.is_file():
        print(f"нет дампа: {INCOMING}", file=sys.stderr)
        return 1
    enc = Path("/root/linotp-migrate/incoming/encKey")
    if not enc.is_file() or enc.stat().st_size != 96:
        print(f"предупреждение: encKey отсутствует или размер != 96 ({enc})", file=sys.stderr)

    REPORTS.mkdir(parents=True, exist_ok=True)
    text = INCOMING.read_text(encoding="utf-8", errors="replace")
    blob = extract_token_insert(text)
    raw = split_sql_values(blob)
    rows = rows_to_dicts(raw)

    stamp = msk_stamp()
    summary = summarize(rows)
    txt_path = REPORTS / f"inventory_{stamp}.txt"
    csv_path = REPORTS / f"inventory_{stamp}.csv"
    txt_path.write_text(summary, encoding="utf-8")

    with csv_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=SAFE_CSV_COLS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in SAFE_CSV_COLS})

    scope_a = [
        r
        for r in rows
        if (r.get("LinOtpTokenType") or "").lower() == "totp"
        and is_active(r)
        and in_migrate_scope(r)
    ]
    scope_csv = REPORTS / f"inventory_inscope_{stamp}.csv"
    with scope_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=SAFE_CSV_COLS, extrasaction="ignore")
        w.writeheader()
        for r in scope_a:
            w.writerow({k: r.get(k, "") for k in SAFE_CSV_COLS})

    guids = sorted(
        {
            (r.get("LinOtpUserid") or "").strip()
            for r in scope_a
            if (r.get("LinOtpUserid") or "").strip()
        }
    )
    guid_path = REPORTS / f"active_totp_guids_inscope_{stamp}.txt"
    guid_path.write_text("\n".join(guids) + ("\n" if guids else ""), encoding="utf-8")

    print(summary)
    print(f"CSV all: {csv_path} ({len(rows)} строк, без секретов)")
    print(f"CSV in-scope: {scope_csv} ({len(scope_a)})")
    print(f"GUIDs in-scope: {guid_path} ({len(guids)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
