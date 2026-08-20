# LinOTP → Own 2FA — отложено

_Создано: 20.08.2026, ~12:10 МСК_  
_Статус: **отложено** до отладки процесса установки Own 2FA. Вернуться после `install.sh` / install flow._

Не часть текущего плана продукта (`PLAN_OWN_2FA_SYSTEM_RU.md`). Этот файл — чеклист на потом.

---

## Уже выяснено (сервер HOTP)

| Параметр | Значение |
|----------|----------|
| Версия | LinOTP **3.2.3** (не контейнер, пакет) |
| БД | MariaDB `linotp` @ `localhost:3306` |
| Audit | `AUDIT_DATABASE_URI=SHARED` |
| encKey | `/etc/linotp/encKey` (96 байт), `SECRET_FILE=/etc/linotp/./encKey` |
| TOTP | 302 всего, **301** активных |
| HMAC | 4 активных |
| Юзеров с ≥1 активным TOTP | **267** |
| 1 токен на юзера | **нет** — много с 2–3; 6 активных TOTP с пустым `LinOtpUserid` |
| LDAP URI | `ldap://172.22.10.100:389` |
| Base DN | `DC=hci,DC=interros,DC=ru` |
| Login attr | `sAMAccountName` |
| UIDTYPE | **objectGUID** → в Token поле `LinOtpUserid` (не логин) |
| Realm | `hci.interros.ru` → `resolver1` |
| Bind DN | `CN=LDAP_Search,OU=Service Accounts,OU=IT_Accounts,DC=hci,DC=interros,DC=ru` |

Таблицы: `Config`, `Token`, `TokenRealm`, `Realm`, `audit`, …

Ключевые поля Token: `LinOtpTokenSerialnumber`, `LinOtpTokenType`, `LinOtpIsactive`, `LinOtpUserid`, `LinOtpIdResolver`, `LinOtpKeyEnc` / `LinOtpKeyIV` (секреты).

---

## Порядок работ (когда вернёмся)

### 1. Бэкап HOTP (первым, до любых выгрузок)

```bash
mkdir -p /root/linotp-backup-$(date +%Y%m%d) && cd /root/linotp-backup-$(date +%Y%m%d)
mysqldump -u linotp -p -h 127.0.0.1 --single-transaction --routines linotp > linotp.sql
cp -a /etc/linotp/encKey .
tar czf etc-linotp.tgz /etc/linotp
ls -la
```

### 2. Инвентарь токенов без секретов

Выгрузка: serial, type, active, userid, resolver, realm — **без** `LinOtpKeyEnc`.

### 3. Маппинг userid → sAMAccountName

Через LDAP по `objectGUID` (и/или данные resolver). Без этого импорт в Own 2FA невозможен.

### 4. Решение стратегии

- **A.** Re-enroll (invite / выпуск заново) — проще, пользователи сканируют QR снова.
- **B.** Перенос TOTP-секретов — нужен `encKey` + расшифровка LinOTP `LinOtpKeyEnc`; иначе нельзя.

Учесть: не 1:1 (дубликаты TOTP, пустой userid, 4 HMAC).

### 5. Скрипт/процесс в Own 2FA

Только после рабочего install flow. Dry-run → сверка чисел → apply. Не `git add .`; push по команде Merl.

---

## SQL (шпаргалка, MariaDB)

Тип колонки: `LinOtpTokenType` (не `Tokentype`).  
В интерактивном mysql: `` `Key` `` / `` `Value` `` (обычные backticks).

```sql
SELECT LinOtpTokenType, COUNT(*) c, SUM(LinOtpIsactive) active
FROM Token GROUP BY LinOtpTokenType;

SELECT LinOtpUserid, COUNT(*) c FROM Token
WHERE LinOtpTokenType='totp' AND LinOtpIsactive=1
GROUP BY LinOtpUserid HAVING c>1 LIMIT 20;
```

---

## Не делать сейчас

- Не писать миграцию в `PLAN_OWN_2FA_SYSTEM_RU.md`
- Не трогать prod LinOTP / не менять Token
- Не коммитить дампы, encKey, BINDPW из Config
