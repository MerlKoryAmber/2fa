#!/usr/bin/env python3
"""Пилот: decrypt + опционально текущий OTP (seed не печатает).

  python3 migration/decrypt_pilot.py
  python3 migration/decrypt_pilot.py --otp
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from linotp_crypto import decrypt_totp_seed, seed_to_base32  # noqa: E402

INCOMING = Path("/root/linotp-migrate/incoming")
DUMP = INCOMING / "linotp.sql"
ENC_KEY_PATH = INCOMING / "encKey"
GUID_MAP = INCOMING / "guid_map.csv"
INV_SCRIPT = Path(__file__).resolve().parent / "inventory_from_dump.py"


def load_inv():
    spec = importlib.util.spec_from_file_location("inv", INV_SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--otp", action="store_true", help="печатать текущий TOTP")
    args = ap.parse_args()

    if not DUMP.is_file() or not ENC_KEY_PATH.is_file() or not GUID_MAP.is_file():
        print("нужны incoming/linotp.sql, encKey, guid_map.csv", file=sys.stderr)
        return 1

    enc_key = ENC_KEY_PATH.read_bytes()
    guid2sam = {
        r["object_guid"].strip().lower(): r["sam_account_name"].strip()
        for r in csv.DictReader(GUID_MAP.open(encoding="utf-8-sig"))
    }
    inv = load_inv()
    text = DUMP.read_text(encoding="utf-8", errors="replace")
    rows = inv.split_sql_values(inv.extract_token_insert(text))

    ok = fail = 0
    print("serial\tsam\tseed_len\tsha256_12\tstatus" + ("\totp" if args.otp else ""))
    for fields in rows:
        d = {c: inv.sql_unquote(v) for c, v in zip(inv.COLS, fields)}
        uid = (d.get("LinOtpUserid") or "").lower()
        if uid not in guid2sam or (d.get("LinOtpTokenType") or "").lower() != "totp":
            continue
        serial = d["LinOtpTokenSerialnumber"]
        sam = guid2sam[uid]
        try:
            seed = decrypt_totp_seed(d["LinOtpKeyEnc"], d["LinOtpKeyIV"], enc_key)
            digest = hashlib.sha256(seed).hexdigest()[:12]
            line = f"{serial}\t{sam}\t{len(seed)}\t{digest}\tOK"
            if args.otp:
                import pyotp

                line += f"\t{pyotp.TOTP(seed_to_base32(seed)).now()}"
            print(line)
            ok += 1
        except Exception as e:
            print(f"{serial}\t{sam}\t-\t-\tFAIL:{e}")
            fail += 1

    print(f"# decrypt OK={ok} FAIL={fail} (mapped={len(guid2sam)})", file=sys.stderr)
    return 0 if fail == 0 and ok > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
