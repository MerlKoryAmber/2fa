# LinOTP → Own 2FA (инструменты миграции)

Только код. **Нет** дампов, encKey, seed CSV — они живут вне git (`/root/linotp-migrate/` на lab).

## Состав

| Файл | Назначение |
|------|------------|
| `export_seeds.py` | lab: decrypt → `seeds_export.csv` |
| `import_seeds.py` | тест: CSV → Postgres Own 2FA по `sAMAccountName` |
| `decrypt_pilot.py` | сверка OTP без записи seed в файл |
| `inventory_from_dump.py` | inventory дампа без секретов |
| `linotp_crypto.py` | AES decrypt LinOTP |
| `guid_hex_to_ldap.py` | hex GUID → LDAP-фильтр |

## Lab → файл

Нужны: `/root/linotp-migrate/incoming/{linotp.sql,encKey,guid_map.csv}`

```bash
python3 migration/export_seeds.py
# → /root/linotp-migrate/work/seeds_export.csv (секрет, chmod 600)
```

## Тест → БД

Скопируй репо (или хотя бы `migration/`) + `seeds_export.csv` на тест:

```bash
cd /path/to/2fa
set -a && source .env && set +a
python3 migration/import_seeds.py /path/to/seeds_export.csv          # dry-run
python3 migration/import_seeds.py /path/to/seeds_export.csv --apply
```

Фильтр: только active TOTP + GUID из `guid_map.csv`.  
Дубль TOTP на один sam → берётся самый новый.
