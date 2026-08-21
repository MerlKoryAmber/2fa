# MK 2FA

MFA: **LDAP/AD** (1-й фактор) + **TOTP / ExpressMS / Telegram** (2-й) + **RADIUS Access-Challenge** для любого NAS (не привязка к UAG).

План и статус: [`PLAN_MK_2FA_SYSTEM_RU.md`](PLAN_MK_2FA_SYSTEM_RU.md).  
Репозиторий: https://github.com/MerlKoryAmber/2fa

## Состав (Podman Compose)

| Сервис | Порт | Назначение |
|--------|------|------------|
| **web** | 80 → 443 | Админка + `/enroll/{token}`; TLS из volume `ssl_certs` |
| **api** | 8000 | FastAPI |
| **worker** | — | Celery: LDAP sync (очередь `default`) |
| **worker-otp** | — | Celery: ExpressMS / Telegram OTP (очередь `otp`) |
| **beat** | — | Celery Beat: авто LDAP sync каждые **30 мин** |
| **db** | — | PostgreSQL 16 |
| **redis** | — | очередь + rate-limit |
| **radius** | 1812/udp | pyrad gateway → API |

На хосте: **Podman** + `podman-compose` (не Docker Engine). Lab: `/root/2fa`.

## Установка на чистый Linux

Скрипты ставят зависимости хоста (curl, git, openssl, python3, **Podman**, **podman-compose**; при отсутствии podman — Docker Compose v2), создают `.env` с секретами, поднимают стек.

Поддержка пакетных менеджеров: **apt** (Debian/Ubuntu), **dnf/yum** (RHEL/CentOS/Rocky/Alma/Fedora), **zypper**, **pacman**, **apk**.

```bash
# уже есть клон репозитория
cd /path/to/2fa
sudo ./scripts/install.sh

# или clone в /opt/mk2fa с GitHub
sudo ./scripts/install.sh --dir /opt/mk2fa

# пакеты уже стоят — только .env + compose
sudo ./scripts/install.sh --skip-pkgs
```

| Скрипт | Назначение |
|--------|------------|
| `scripts/install.sh` | пакеты + `.env` + `compose up --build` + health |
| `scripts/update.sh` | `git pull --ff-only` + полный rebuild + alembic + health |
| `scripts/uninstall.sh` | `compose down`; `--purge` удаляет volumes; `--purge --remove-dir` — и каталог |

Сгенерированные пароли (если `.env` создавался впервые): `.install-credentials.txt` (в `.gitignore`).

### Lab / уже развёрнуто

```bash
cd /root/2fa
cp .env.example .env   # сменить секреты перед любой не-lab сетью
make up                # podman-compose up --build -d
podman exec 2fa_api_1 alembic upgrade head   # head = 007
curl -sk https://127.0.0.1/health
make verify
```

Админка: `https://<IP>/` (self-signed по умолчанию; браузер предупредит).  
HTTP `:80` → HTTPS. API: `http://<IP>:8000/health`.

### Lab credentials (сменить перед prod)

| Что | Значение |
|-----|----------|
| Admin | `admin` / `admin` — сразу после install; смените в панели |
| Demo seed | user `demo` + TOTP `JBSWY3DPEHPK3PXP` (нужен тот же user в AD для RADIUS) |
| RADIUS secret | `testing123` (из панели / `.env`) |

## Админка (что умеет)

Админка в UI: бренд **MK 2FA** (локальные шрифты/логотип в `web/assets/`).  
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
- **OU** и/или **группа AD** для sync.

Mock LDAP **удалён** — только реальный AD.

## Доступ к панели (роли)

Вкладка **Настройки → Доступ**.

| Роль | Как входит | Права |
|------|------------|--------|
| **Администратор** | локальный логин/пароль панели | полный доступ |
| **Оператор** | **логин/пароль AD**, группа операторов | приглашения + просмотр токенов |
| **Аудитор** | **логин/пароль AD**, группа аудиторов | токены + аудит |

Группы AD задаются в «Доступ» (DN или короткое имя; вложенные учитываются). Обе группы → роль оператор.  
Смена пароля в сайдбаре — только для локальных учёток.

## ExpressMS / Telegram / SMTP

Вкладки в настройках. Lab: dry-run по умолчанию (код в лог **worker-otp**, без реальной отправки).
Обновление каналов OTP: пересобрать/recreate только `worker-otp` — api/radius/web/LDAP-worker не трогать.

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
| 005 | `users.display_name` |
| 006 | роли админов панели (`admin` / `operator` / `auditor`) |
| **007** | `admins.auth_source` (local / ad), группы AD для операторов/аудиторов |

## Деплой после правок кода

Полный цикл (на lab агент делает сам):

```bash
podman build …   # затронутые образы
podman-compose down && podman-compose up -d
podman exec 2fa_api_1 alembic upgrade head
curl -sk https://127.0.0.1/health
```

**Грабля:** `up --force-recreate api` часто **не** подхватывает новый образ → 404. Нужен полный `down` → `up -d`.  
Образы: `api`/`worker`/`worker-otp`/`beat` — один `localhost/mk2fa-api:latest` (сборка только у сервиса `api`).

`PYTHONPATH=/usr/local/lib/python3.9/site-packages` — для `podman-compose` на CentOS Stream 9 lab.  
На EL9 `sudo` часто без `/usr/local/bin`: `install.sh` сам ищет pip-бинарь или `python3 -m podman_compose`.

## Безопасность

- Секреты только в `.env` / панели (не в git). `.env` в `.gitignore`.
- Шифрование чувствительных полей: `APP_ENCRYPTION_KEY`.
- Rate-limit: `RATE_LIMIT_RADIUS_PER_MINUTE`, `RATE_LIMIT_LOGIN_PER_MINUTE`.
- Перед prod: сменить admin/пароли/секреты, заполнить allowed NAS, выключить dry-run где нужно.

## Backlog (кратко)

- Discovery на реальном NAS
- Telegram bot `/start`
- Policy engine по группе/OU AD

LinOTP-миграция (в работе, инструменты в [`migration/`](migration/)): [`LINOTP_MIGRATION_TODO.md`](LINOTP_MIGRATION_TODO.md).

## Метод работы

[`CLAUDE.md`](CLAUDE.md) — роли, пайплайн, коммиты, UX админки.
