#!/usr/bin/env python3
"""Экспорт TOTP seed в файл для переноса на тест MK 2FA.

На lab (есть linotp.sql + encKey + guid_map.csv):

  python3 migration/export_seeds.py
  python3 migration/export_seeds.py -o /root/linotp-migrate/work/seeds.csv

Файл содержит seed_base32 — СЕКРЕТ. Не в git. chmod 600.
Перенеси сам на тест (scp/usb), там — import_seeds.py.
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
import os
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from linotp_crypto import decrypt_totp_seed, seed_to_base32

INCOMING = Path("/root/linotp-migrate/incoming")
DUMP = INCOMING / "linotp.sql"
ENC_KEY_PATH = INCOMING / "encKey"
GUID_MAP = INCOMING / "guid_map.csv"
DEFAULT_OUT = Path("/root/linotp-migrate/work/seeds_export.csv")
INV_SCRIPT = Path(__file__).resolve().parent / "inventory_from_dump.py"


def load_inv():
    spec = importlib.util.spec_from_file_location("inv", INV_SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def parse_creation(s: str | None) -> datetime | None:
    s = (s or "").strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:19], fmt)
        except ValueError:
            continue
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="Export decrypted TOTP seeds for MK 2FA import")
    ap.add_argument("-o", "--output", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--guid-map", type=Path, default=GUID_MAP)
    ap.add_argument("--dump", type=Path, default=DUMP)
    ap.add_argument("--enc-key", type=Path, default=ENC_KEY_PATH)
    args = ap.parse_args()

    for p, name in ((args.dump, "dump"), (args.enc_key, "encKey"), (args.guid_map, "guid_map")):
        if not p.is_file():
            print(f"нет файла ({name}): {p}", file=sys.stderr)
            return 1

    guid2sam = {
        r["object_guid"].strip().lower(): r["sam_account_name"].strip()
        for r in csv.DictReader(args.guid_map.open(encoding="utf-8-sig"))
    }
    if not guid2sam:
        print("guid_map пуст", file=sys.stderr)
        return 1

    enc_key = args.enc_key.read_bytes()
    inv = load_inv()
    text = args.dump.read_text(encoding="utf-8", errors="replace")
    raw_rows = inv.split_sql_values(inv.extract_token_insert(text))

    # sam -> list of candidate rows (для выбора одного при дублях)
    by_sam: dict[str, list[dict]] = defaultdict(list)
    decrypt_fail = 0
    skip_unmapped = 0

    for fields in raw_rows:
        d = {c: inv.sql_unquote(v) for c, v in zip(inv.COLS, fields)}
        if (d.get("LinOtpTokenType") or "").lower() != "totp":
            continue
        if str(d.get("LinOtpIsactive")) not in ("1", "true", "True"):
            continue
        uid = (d.get("LinOtpUserid") or "").strip().lower()
        if not uid or uid not in guid2sam:
            skip_unmapped += 1
            continue
        created = parse_creation(d.get("LinOtpCreationDate"))
        try:
            seed = decrypt_totp_seed(d["LinOtpKeyEnc"], d["LinOtpKeyIV"], enc_key)
            b32 = seed_to_base32(seed)
        except Exception as e:
            print(f"FAIL decrypt {d.get('LinOtpTokenSerialnumber')}: {e}", file=sys.stderr)
            decrypt_fail += 1
            continue
        by_sam[guid2sam[uid]].append(
            {
                "sam_account_name": guid2sam[uid],
                "token_serial": d["LinOtpTokenSerialnumber"],
                "seed_base32": b32,
                "linotp_created": d.get("LinOtpCreationDate") or "",
                "object_guid": uid,
                "_created": created or datetime.min,
            }
        )

    # один seed на sam: самый новый по creation
    out_rows = []
    collisions = 0
    for sam, items in sorted(by_sam.items()):
        items.sort(key=lambda x: x["_created"], reverse=True)
        if len(items) > 1:
            collisions += 1
            print(
                f"WARN {sam}: {len(items)} totp → берём {items[0]['token_serial']} "
                f"(created {items[0]['linotp_created']})",
                file=sys.stderr,
            )
        chosen = items[0]
        out_rows.append(
            {
                "sam_account_name": chosen["sam_account_name"],
                "token_serial": chosen["token_serial"],
                "seed_base32": chosen["seed_base32"],
                "linotp_created": chosen["linotp_created"],
                "object_guid": chosen["object_guid"],
            }
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "sam_account_name",
                "token_serial",
                "seed_base32",
                "linotp_created",
                "object_guid",
            ],
        )
        w.writeheader()
        w.writerows(out_rows)
    os.chmod(args.output, 0o600)

    print(
        f"exported={len(out_rows)} decrypt_fail={decrypt_fail} "
        f"unmapped_active_totp_rows≈{skip_unmapped} sam_collisions={collisions}",
        file=sys.stderr,
    )
    print(args.output)
    return 0 if decrypt_fail == 0 and out_rows else 1


if __name__ == "__main__":
    # чтобы import linotp_crypto работал при запуске по пути
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    raise SystemExit(main())
