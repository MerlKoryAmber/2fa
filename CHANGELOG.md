# CHANGELOG

## 2026-08-21 (МСК) — RADIUS: не молчать + ошибки в аудит

- Gateway больше не дропает NAS без ответа (это давало «сервер не ответил»)
- Аудит: `RADIUS_NAS_DENIED`, `RADIUS_BAD_PACKET` (secret), `RADIUS_ERROR`, LDAP_FAIL с NAS
- LDAP timeout 2+3 с, чтобы NAS не ждал дольше своего таймера

## 2026-08-21 (МСК) — RADIUS 403: httpx ходил в HTTP_PROXY

- Токен совпадал (48 / один sha), `host.env` смонтирован — секрет ни при чём
- `httpx` по умолчанию берёт proxy из env; запрос к `http://api:8000` уходит на корпоративный прокси → чужой 403
- radius + smoke: `trust_env=False`; в 403 тело `got_len`/`exp_len`

## 2026-08-21 (МСК) — update: pull не вхолостую + токен из смонтированного .env

- Текст «Лог: podman logs 2fa_radius_1» = **старый** `common.sh`: `source` до `git pull`, ошибки fetch спрятаны; shallow `--depth 1` не видел новые коммиты
- `update.sh`: unshallow + видимый HEAD + `exec --no-pull` после pull
- api и radius монтируют хостовый `.env` в `/run/mk2fa/host.env` — один токен, не compose env_file
- smoke печатает `token_len` / sha256 при 403

## 2026-08-21 (МСК) — RADIUS 403: pydantic dotenv не перебивает compose

- `INTERNAL_API_TOKEN` для `/internal/*` берётся из `os.environ` (как у radius)
- pydantic-settings: **env выше dotenv** — иначе printenv совпадает, settings нет, smoke 403
- `compose()` экспортирует `.env` до interpolate (sudo env_reset)

## 2026-08-21 (МСК) — install/update без ручной добивки RADIUS

- `install.sh` / `update.sh`: CRLF в `.env`, firewall 1812/udp, smoke `GET /internal/radius/config` из контейнера radius (не 403)
- После clone/pull достаточно скрипта — не править compose/токен на каждом сервере

## 2026-08-21 (МСК) — RADIUS 403: токен из .env, не пустой interpolate

- `radius` больше не перебивает `INTERNAL_API_TOKEN`/`RADIUS_SECRET` пустым `${VAR}` с хоста (env_file остаётся источником)
- сравнение токена со `.strip()` — CRLF в .env не даёт 403

## 2026-08-21 (МСК) — RADIUS: LDAP не вешает NAS, firewall 1812/udp

- LDAP bind для RADIUS: `get_info=NONE`, connect/receive timeout; LDAPS без зависания на schema/CA
- `install.sh` сам открывает firewalld/ufw: 80, 443, **1812/udp** (раньше только WARN)

## 2026-08-21 (МСК) — кнопки пользователей в один ряд

- Колонка действий: `nowrap` + ширина по содержимому, не 20% fixed (кнопки больше не столбиком и не оставляют пустоту справа)

## 2026-08-21 (МСК) — имя из AD: кириллица, не \\u041a

- LDAP: брать `.value` атрибута, не `str(Attribute)` (ascii-escape)
- Уже записанные `\\uXXXX` декодируются в API; колонка «Имя» с ellipsis, кнопки не уезжают

## 2026-08-21 (МСК) — импорт LinOTP через контейнер api

- `scripts/import_linotp_seeds.sh`: CSV в контейнер api (cryptography уже в образе)
- С хоста `python3 import_seeds.py` не работает: нет модуля и БД только как `db` в сети compose

## 2026-08-21 (МСК) — вход сразу после install: admin / admin

- Дефолт панели: логин `admin`, пароль `admin` (не случайный, не `changeme`)
- Форма входа пустая — ничего не подставлять
- Правило: `.cursor/rules/install-ready.mdc` — после install не допиливать на сервере

## 2026-08-21 (МСК) — вход: не подставлять changeme

- Форма логина больше не заполняет пароль `changeme` (после install пароль случайный, в `.install-credentials.txt`)
- README и баннер install: явный логин `admin` + путь к файлу учёток

## 2026-08-21 (МСК) — install: PUBLIC_BASE_URL = IP этого хоста

- `.env.example` больше не содержит `192.168.0.178` (домашняя lab)
- При создании `.env` скрипт ставит `https://<hostname -I>`
- Баннер установки не показывает старый lab-IP, если он остался в `.env`

## 2026-08-21 (МСК) — install: один образ api, без HEALTHCHECK в Dockerfile

- `api` / `worker` / `worker-otp` / `beat` делят `localhost/mk2fa-api:latest` — не 4 параллельных `podman build` одного Dockerfile (Prepare images failed)
- HEALTHCHECK убран из `api/Dockerfile` (OCI его игнорирует); проверка — в compose
- `install`/`update`: `compose build` api → radius → web по очереди, затем `up -d`

## 2026-08-21 (МСК) — install: pip podman-compose под sudo

- EL9 `sudo` PATH без `/usr/local/bin`: движок видел `import podman_compose`, а `compose()` падал «podman-compose нет»
- Скрипт ищет бинарь в `/usr/local/bin` или `python3 -m podman_compose`; PYTHONUNBUFFERED на сборке
- `FROM docker.io/library/python:3.12-slim` — без short-name prompt Podman на свежем EL9

## 2026-08-21 (МСК) — панель: вкладка после F5 + меню

- Вкладка и settings-subtab в hash/`sessionStorage`; критичный CSS `.hidden` + `data-tab` — без мелькания чужих секций
- Убрана подсказка Lab/demo seed со Сводки; пункты сайдбара крупнее (`1.05rem`)

## 2026-08-21 (МСК) — переименование Own 2FA → MK 2FA

- Продуктовое имя **MK 2FA** в README, API title, TOTP issuer, скриптах, docs, письмах
- План: `PLAN_MK_2FA_SYSTEM_RU.md` (бывш. `PLAN_OWN_2FA_SYSTEM_RU.md`)

## 2026-08-21 (МСК) — UI Interros / MK 2FA

- Расцветка и экран входа как у Squid Proxy Manager; логотип + Inter локально (`web/assets/`)
- Бренд панели **MK 2FA** (Cinzel локально); сайдбар navy, акцент gold; меню без иконок
- User-menu справа сверху; бренд-полоса и topbar одной высоты (`--topbar-h`) — без «ступеньки»

## 2026-08-21 (МСК) — worker-otp (очереди Celery)

- Очереди: `default` (LDAP sync) и `otp` (ExpressMS / Telegram)
- Сервис **worker-otp** в compose; recreate каналов без остановки api/radius/web

## 2026-08-20 (МСК, вечер) — инструменты миграции LinOTP

- Каталог `migration/`: export/import TOTP seed (lab → CSV → тест MK 2FA)
- Без дампов/encKey/seed в git; только код + README

## 2026-08-20 (МСК) — RBAC панели + AD-вход + install

- Роли админов: `admin` / `operator` / `auditor` (миграция **006**)
- **Настройки → Доступ:** список учёток, группы AD операторов/аудиторов, локальный break-glass
- Вход оператора/аудитора: bind AD + membership; `admins.auth_source` (**007**)
- Mock LDAP удалён — только реальный AD
- Смена пароля в сайдбаре (только local)
- Скрипты хоста: `scripts/install.sh`, `update.sh`, `uninstall.sh`
- UI: легенды секций настроек внутри карточки (не разрез рамкой)

## 2026-08-19 (МСК, поздно) — enroll + приглашения

- **Выпустить код** — TOTP QR/secret без confirm (ручная пересылка)
- **Приглашение** — email со ссылкой `/enroll/{token}`, публичная страница confirm
- **Загрузить из LDAP** — пользователи + email в список
- SMTP + Public URL в настройках; `enroll_invite_ttl_seconds` в политике

## 2026-08-19 (МСК, поздно) — sidebar + токены

- Боковая панель; «Настройки» закреплены снизу
- Раздел **Токены** (serial, тип, user, статус, last used) — по мотивам PrivacyIDEA
- API: `GET/PATCH /api/tokens/{serial}` — enable/disable/revoke
- Миграция `003`: `token_serial`, `token_active`, `last_used_at`

## 2026-08-19 (МСК, поздно) — LDAP UX

- Bind user: `domain\user`, UPN или username (не DN)
- Несколько DC: host + port, failover по списку
- SSL — отдельная галка; legacy `LDAP_URL` читается как один DC

## 2026-08-19 (МСК, поздно) — UI настроек + RADIUS ACL

- Настройки: одна колонка, чекбоксы привязаны к подписи (Linear DESIGN.md)
- `radius.allowed_clients` — IP/CIDR NAS, пусто = любой
- Фикс: снятые чекбоксы теперь сохраняются как false

## 2026-08-19 (МСК, поздно) — settings + Telegram

- `system_settings` в БД: LDAP, RADIUS, ExpressMS, Telegram из панели
- Telegram OTP: worker, enroll `chat_id`, RADIUS flow
- RADIUS gateway читает shared secret из API (кэш 60 с)
- Вкладка «Настройки» + тест LDAP в админке

## 2026-08-19 (МСК, вечер) — план v2

- RADIUS: не UAG-specific, любой NAS с Access-Challenge
- Установка: git/архив + compose; LDAP/RADIUS — в панели (цель)
- 2FA: добавлен **Telegram** наряду с TOTP и ExpressMS

## 2026-08-19 (МСК) — hardening lab

- Alembic миграции вместо `create_all`; `pre_migrate.py` для существующих БД
- Rate-limit login и RADIUS через Redis
- Anti-replay: повтор `State` после успеха → reject + audit `replay`
- `/health` проверяет Postgres + Redis
- HTTPS :443 (self-signed), HTTP → redirect
- Healthchecks в compose для всех сервисов
- Тесты: OTP, LDAP mock, RADIUS flow, rate-limit, API health
- `make verify` — pytest + compileall
