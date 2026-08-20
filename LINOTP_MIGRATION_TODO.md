# LinOTP → MK 2FA — стратегия B (перенос секретов)

_Создано: 20.08.2026_  
_Статус: **В РАБОТЕ** (старт 20.08.2026 ~21:30 МСК)_  
_Стратегия: **B** — decrypt `LinOtpKeyEnc` + импорт в MK 2FA_

Не в `PLAN_MK_2FA_SYSTEM_RU.md` как продуктовая фича; процесс миграции.

---

## Разделение ролей

| Кто | Делает |
|-----|--------|
| **Merl** | Бэкап HOTP (`linotp.sql` + `encKey`); живой LDAP / тест MK 2FA; GUID→sAMAccountName CSV; приёмка OTP на тесте |
| **Агент (lab `/root/2fa`)** | Площадка `/root/linotp-migrate/`; inventory / decrypt / dry-run / скрипты; **без** доступа к живому AD |

Секреты и дамп — только `/root/linotp-migrate/` (вне git). В репо — скрипты + отчёты без seed.

---

## Уже выяснено (сервер HOTP)

| Параметр | Значение |
|----------|----------|
| Версия | LinOTP **3.2.3** (не контейнер, пакет) |
| БД | MariaDB `linotp` @ `localhost:3306` |
| encKey | `/etc/linotp/encKey` (96 байт) |
| TOTP | 302 всего, **301** активных |
| HMAC | 4 активных |
| Юзеров с ≥1 активным TOTP | **267** |
| 1 токен на юзера | **нет** (дубликаты; 6 TOTP с пустым userid) |
| LDAP | `ldap://172.22.10.100:389`, `DC=hci,DC=interros,DC=ru` |
| UIDTYPE | **objectGUID** → `LinOtpUserid` |
| Bind DN | `CN=LDAP_Search,OU=Service Accounts,OU=IT_Accounts,DC=hci,DC=interros,DC=ru` |

Поля Token: `LinOtpTokenSerialnumber`, `LinOtpTokenType`, `LinOtpIsactive`, `LinOtpUserid`, `LinOtpIdResolver`, `LinOtpKeyEnc` / `LinOtpKeyIV`.

---

## Чеклист (B)

| # | Шаг | Статус | Где |
|---|-----|--------|-----|
| 0 | Правила: prod read-only; секреты вне git; dry-run до apply | OK | — |
| 1 | Площадка lab + README | OK | `/root/linotp-migrate/` |
| 2 | Бэкап `linotp.sql` + `encKey` → `incoming/` | **OK** | encKey 96 байт; dump ~47.6 MB |
| 3 | Inventory без секретов, сверка чисел | **OK** | totp active 302; +фильтр даты |
| 3b | Политика: не переносить `creation < 2026-01-01` | **OK** | in scope **78** TOTP / **75** GUID; skip 224 |
| 4 | `guid_map.csv` (GUID→sAMAccountName) | **частично** | 4 логина в `incoming/guid_map.csv` (пилот); нужно добить до 75 |
| 5 | Пилот decrypt + сверка OTP | **OK** | U2008 код совпал |
| 5b | Инструменты export→файл→import | **OK** | каталог `migration/` |
| 6 | Политика коллизий | OK в export | дубль → newest by creation |
| 7 | Dry-run / apply на тесте | **Merl** | полный guid_map → export → scp → import --apply |
| 5 | Пилот decrypt 1–3 токена | после 2 | агент |
| 6 | Политика коллизий (дубли TOTP → один seed) | после 3 | согласовать |
| 7 | Dry-run импорта (числа) | после 4–6 | агент |
| 8 | Apply на **тест** MK 2FA | Merl / по договорённости | тест-хост |
| 9 | Приёмка OTP (RADIUS/API) | Merl | тест |
| 10 | CHANGELOG + handoff + ADR | перед push | агент |

---

## П.2 — бэкап (команды для Merl)

На HOTP:

```bash
STAMP=$(date +%Y%m%d-%H%M)
DIR=/root/linotp-backup-$STAMP
mkdir -p "$DIR" && cd "$DIR"
mysqldump -u linotp -p -h 127.0.0.1 --single-transaction --routines linotp > linotp.sql
cp -a /etc/linotp/encKey .
ls -la
sha256sum linotp.sql encKey
```

На lab:

```text
/root/linotp-migrate/incoming/linotp.sql
/root/linotp-migrate/incoming/encKey
```

Инструкция: `/root/linotp-migrate/README.md`.

---

## SQL (шпаргалка)

```sql
SELECT LinOtpTokenType, COUNT(*) c, SUM(LinOtpIsactive) active
FROM Token GROUP BY LinOtpTokenType;
```

---

## Не делать

- Не трогать prod Token (UPDATE/DELETE)
- Не коммитить дампы, encKey, BINDPW, CSV с seed
- Не apply в prod MK 2FA без явной команды
