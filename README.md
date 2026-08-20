# Own 2FA

Собственная MFA: **LDAP/AD** (1-й фактор) + **TOTP / ExpressMS / Telegram** (2-й) + **RADIUS Access-Challenge** для любого NAS (не привязка к UAG).

План и статус: [`PLAN_OWN_2FA_SYSTEM_RU.md`](PLAN_OWN_2FA_SYSTEM_RU.md).  
Репозиторий: https://github.com/MerlKoryAmber/2fa

## Состав (Podman Compose)

| Сервис | Порт | Назначение |
|--------|------|------------|
| **web** | 80 → 443 | Админка + `/enroll/{token}`; TLS из volume `ssl_certs` |
| **api** | 8000 | FastAPI |
| **worker** | — | Celery: OTP в ExpressMS / Telegram |
| **beat** | — | Celery Beat: авто LDAP sync каждые **30 мин** |
| **db** | — | PostgreSQL 16 |
| **redis** | — | очередь + rate-limit |
| **radius** | 1812/udp | pyrad gateway → API |

На хосте: **Podman** + `podman-compose` (не Docker Engine). Lab: `/root/2fa`.

## Быстрый старт

```bash
cd /root/2fa
cp .env.example .env   # сменить секреты перед любой не-lab сетью
make up                # podman-compose up --build -d
# миграции на старте api; вручную:
podman exec 2fa_api_1 alembic upgrade head   # head = 005
curl -sk https://127.0.0.1/health
make verify            # тесты в образе api
```

Админка: `https://<IP>/` (self-signed по умолчанию; браузер предупредит).  
HTTP `:80` → HTTPS. API: `http://<IP>:8000/health`.

### Lab credentials (сменить перед prod)

| Что | Значение |
|-----|----------|
| Admin | `admin` / `changeme` |
| Demo LDAP mock | `demo` / `demo` |
| Demo TOTP | `JBSWY3DPEHPK3PXP` |
| RADIUS secret | `testing123` (из панели / `.env`) |

## Админка (что умеет)

Боковая панель: **Сводка → Токены → Пользователи → Политика → Аудит → Настройки**.

- **Настройки:** LDAP (несколько DC, OU/группа sync), RADIUS (secret, allowed NAS), ExpressMS, SMTP (шаблон приглашения), Приложение (`public_base_url`), Telegram, **Сертификаты** (HTTPS cert+key, root CA).
- **Пользователи:** авто-sync 30 мин + «Загрузить из LDAP»; фильтры; имя из AD `displayName`; выпуск TOTP; **копировать ссылку** / **отправить приглашение**; модал «Настроить 2FA».
- **Токены:** enable / disable / revoke (модальное подтверждение).
- **Аудит:** события и подробности на русском.
- **Enroll** `/enroll/{token}`: сначала **логин+пароль LDAP**, затем QR TOTP (+ опционально ExpressMS / Telegram).

Дизайн: [`docs/design/DESIGN.md`](docs/design/DESIGN.md).

## Enrollment

1. Sync пользователей из LDAP (email + displayName).
2. Админ: **Копировать ссылку** или **Отправить приглашение** (SMTP; в lab часто dry-run → лог).
3. Пользователь открывает ссылку → LDAP auth → QR → код из приложения.
4. TTL ссылки: политика `enroll_invite_ttl_seconds` (default 86400).

## RADIUS

```bash
# шаг 1 — пароль AD → Access-Challenge + State
echo User-Name=demo,User-Password=demo | radclient -x 127.0.0.1:1812 auth testing123

# шаг 2 — OTP в User-Password + тот же State
# удобнее:
python3 scripts/radius_demo.py
```

Gateway берёт secret и **allowed_clients** (IP/CIDR) с API `/internal/radius/config` (кэш ~60 с). Пустой список NAS = любой источник.

## LDAP / AD

Через **Настройки** или bootstrap в `.env`:

- несколько DC (host+port), failover;
- bind: `DOMAIN\user`, UPN или короткий логин;
- Base DN, SSL/LDAPS;
- **OU** и/или **группа AD** для sync;
- mock для lab: `LDAP_MOCK=true`.

## ExpressMS / Telegram / SMTP

Вкладки в настройках. Lab: dry-run по умолчанию (код в лог worker, без реальной отправки).

```
EXPRESSMS_DRY_RUN=true
TELEGRAM_DRY_RUN=true
SMTP_DRY_RUN=true
PUBLIC_BASE_URL=https://<IP>
```

Telegram chat_id пока вручную (enroll / модал пользователя). Bot `/start` — backlog.

## TLS

Вкладка **Сертификаты**: загрузка cert+key панели и корневого CA → volume `ssl_certs`, reload nginx. Без upload — self-signed.

## БД (Alembic)

| Rev | Содержание |
|-----|------------|
| 001–003 | схема, settings, telegram, token fields |
| 004 | enrollment_invites, ldap_email, invite TTL |
| **005** | `users.display_name` |

## Деплой после правок кода

Полный цикл (на lab агент делает сам):

```bash
podman build …   # затронутые образы
podman-compose down && podman-compose up -d
podman exec 2fa_api_1 alembic upgrade head
curl -sk https://127.0.0.1/health
```

**Грабля:** `up --force-recreate api` часто **не** подхватывает новый образ → 404. Нужен полный `down` → `up -d`.

`PYTHONPATH=/usr/local/lib/python3.9/site-packages` — для `podman-compose` на CentOS Stream 9 lab.

## Безопасность

- Секреты только в `.env` / панели (не в git). `.env` в `.gitignore`.
- Шифрование чувствительных полей: `APP_ENCRYPTION_KEY`.
- Rate-limit: `RATE_LIMIT_RADIUS_PER_MINUTE`, `RATE_LIMIT_LOGIN_PER_MINUTE`.
- Перед prod: сменить admin/пароли/секреты, заполнить allowed NAS, выключить dry-run где нужно.

## Backlog (кратко)

- `install.sh` (установка с GitHub) — по команде
- Discovery на реальном NAS
- Telegram bot `/start`
- Policy engine по группе/OU AD
- RBAC админов через AD

LinOTP-миграция (отложена): [`LINOTP_MIGRATION_TODO.md`](LINOTP_MIGRATION_TODO.md).

## Метод работы

[`CLAUDE.md`](CLAUDE.md) — роли, пайплайн, коммиты, UX админки.
