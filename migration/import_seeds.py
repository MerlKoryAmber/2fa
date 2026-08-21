#!/usr/bin/env python3
"""Импорт TOTP seed в MK 2FA по sAMAccountName (= users.ad_username).

На ТЕСТ-хосте (есть доступ к Postgres MK 2FA + APP_ENCRYPTION_KEY):

  # сначала dry-run (ничего не пишет)
  DATABASE_URL=... APP_ENCRYPTION_KEY=... \\
    python3 migration/import_seeds.py /path/to/seeds_export.csv

  # запись
  DATABASE_URL=... APP_ENCRYPTION_KEY=... \\
    python3 migration/import_seeds.py /path/to/seeds_export.csv --apply

На хосте EL9 пакеты python обычно нет — гонять через контейнер api:

  sudo ./scripts/import_linotp_seeds.sh /path/to/seeds_export.csv
  sudo ./scripts/import_linotp_seeds.sh /path/to/seeds_export.csv --apply

Политика по умолчанию:
  - match: ad_username == sam_account_name (case-insensitive)
  - нет пользователя → skip (или --create-missing)
  - уже есть confirmed TOTP → skip (или --overwrite)
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from cryptography.fernet import Fernet
from sqlalchemy import Boolean, DateTime, Integer, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ad_username: Mapped[str] = mapped_column(String(256), unique=True)
    otp_method: Mapped[str] = mapped_column(String(32), default="NONE")
    totp_secret_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    totp_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    token_serial: Mapped[str | None] = mapped_column(String(32), unique=True, nullable=True)
    token_active: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def encrypt_totp_secret(fernet: Fernet, secret_b32: str) -> str:
    return fernet.encrypt(secret_b32.encode()).decode()


def load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip().strip("'").strip('"')
        os.environ.setdefault(k, v)


def main() -> int:
    ap = argparse.ArgumentParser(description="Import TOTP seeds into MK 2FA by sAMAccountName")
    ap.add_argument("csv_path", type=Path, help="seeds_export.csv from export_seeds.py")
    ap.add_argument("--apply", action="store_true", help="писать в БД (без флага — только dry-run)")
    ap.add_argument("--create-missing", action="store_true", help="создать user если нет в БД")
    ap.add_argument("--overwrite", action="store_true", help="перезаписать существующий confirmed TOTP")
    ap.add_argument("--env-file", type=Path, default=Path(".env"))
    args = ap.parse_args()

    load_dotenv(args.env_file)
    db_url = os.environ.get("DATABASE_URL")
    enc_key = os.environ.get("APP_ENCRYPTION_KEY")
    if not db_url or not enc_key:
        print("нужны DATABASE_URL и APP_ENCRYPTION_KEY (env или --env-file .env)", file=sys.stderr)
        return 1
    if not args.csv_path.is_file():
        print(f"нет файла: {args.csv_path}", file=sys.stderr)
        return 1

    fernet = Fernet(enc_key.encode())
    engine = create_engine(db_url)

    rows = list(csv.DictReader(args.csv_path.open(encoding="utf-8-sig")))
    if not rows:
        print("CSV пуст", file=sys.stderr)
        return 1

    stats = {
        "would_update": 0,
        "would_create": 0,
        "skip_missing": 0,
        "skip_existing": 0,
        "skip_serial_clash": 0,
        "error": 0,
    }

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"# {mode} rows={len(rows)}", file=sys.stderr)

    with Session(engine) as db:
        for r in rows:
            sam = (r.get("sam_account_name") or "").strip()
            serial = (r.get("token_serial") or "").strip()
            seed = (r.get("seed_base32") or "").strip()
            if not sam or not serial or not seed:
                print(f"ERROR bad row: {r!r}", file=sys.stderr)
                stats["error"] += 1
                continue

            user = db.scalar(select(User).where(User.ad_username.ilike(sam)))
            if user is None:
                if not args.create_missing:
                    print(f"SKIP missing user {sam}", file=sys.stderr)
                    stats["skip_missing"] += 1
                    continue
                action = "CREATE"
                stats["would_create"] += 1
            else:
                if user.totp_confirmed and user.totp_secret_encrypted and not args.overwrite:
                    print(f"SKIP existing TOTP {sam}", file=sys.stderr)
                    stats["skip_existing"] += 1
                    continue
                action = "UPDATE"
                stats["would_update"] += 1

            other = db.scalar(select(User).where(User.token_serial == serial))
            if other is not None and (user is None or other.id != user.id):
                print(
                    f"SKIP serial clash {serial} already on {other.ad_username}",
                    file=sys.stderr,
                )
                stats["skip_serial_clash"] += 1
                if action == "CREATE":
                    stats["would_create"] -= 1
                else:
                    stats["would_update"] -= 1
                continue

            print(f"{action} {sam} serial={serial}", file=sys.stderr)
            if not args.apply:
                continue

            if user is None:
                user = User(
                    ad_username=sam,
                    otp_method="TOTP",
                    totp_confirmed=True,
                    token_active=True,
                    updated_at=utcnow(),
                )
                db.add(user)

            user.otp_method = "TOTP"
            user.totp_secret_encrypted = encrypt_totp_secret(fernet, seed)
            user.totp_confirmed = True
            user.token_serial = serial
            user.token_active = True
            user.updated_at = utcnow()

        if args.apply:
            db.commit()
            print("# committed", file=sys.stderr)
        else:
            db.rollback()
            print("# dry-run — ничего не записано", file=sys.stderr)

    print("# stats", stats, file=sys.stderr)
    return 0 if stats["error"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
