# План разработки MK 2FA (AD + RADIUS + Web + Docker)

_Обновлено: 20.08.2026, ~01:55 МСК — синхронизация с lab на `/root/2fa`_

## 0) Исходные требования (зафиксировано)

- **1-й фактор:** AD / LDAP (аутентификация по LDAP bind).
- **2-й фактор — на выбор пользователя или политики:**
  - **TOTP** («как Google Authenticator», RFC-6238).
  - **OTP по сообщению** через **ExpressMS** (корпоративный мессенджер; интеграция по их API).
  - **OTP по сообщению** через **Telegram** (Bot API: chat_id пользователя, отправка кода ботом).
- **Web-управление:** админка; **настройки LDAP, RADIUS, SMTP, ExpressMS, Telegram — в панели**, bootstrap через `.env`.
- **Интеграция с RADIUS:** схема MFA через `Access-Challenge` + `State` (см. §1). **Не привязка к VMware UAG** — любой клиент/NAS с тем же flow.
- **Enrollment:** админ выпускает TOTP вручную, **копирует ссылку** или шлёт **email-приглашение**; пользователь проходит **LDAP auth** на `/enroll/{token}`, затем QR/TOTP.
- **Деплой:** Podman Compose на lab; **агент сам rebuild/deploy/migrate** после изменений (правило `.cursor/rules/deploy-lab.mdc`). **`scripts/install.sh` / `update.sh` / `uninstall.sh`** — установка на Linux.
- **Масштаб:** 100–200 пользователей.

---

## 1) Ключевой RADIUS flow (универсальный challenge-response)

### Шаг 1: `Access-Request` (первичный)

1. NAS отправляет `User-Name`, `User-Password` = пароль LDAP.
2. RADIUS gateway → API `/internal/radius/access-request`:
   - LDAP (параметры из `system_settings`, несколько DC с failover);
   - проверка **allowed_clients** (IP/CIDR NAS; пусто = любой);
   - rate-limit по Redis;
   - при необходимости 2FA — `Access-Challenge` + `State`;
   - ExpressMS / Telegram — OTP через Celery worker (dry-run в lab).

### Шаг 2: `Access-Request` (OTP)

1. `State` + `User-Password` = OTP.
2. Валидация TOTP / hash OTP; anti-replay на consumed `State`; **`Access-Accept`** / **`Access-Reject`**.

### Discovery (перед prod)

- На реальном NAS подтвердить OTP в `User-Password`, сохранение `State`, secret, таймауты.

---

## 2) Высокоуровневая архитектура

### Compose-сервисы (lab)

| Сервис | Порт | Назначение |
|--------|------|------------|
| web | 80→443 | Админка + `/enroll/{token}`; volume `ssl_certs` → nginx TLS |
| api | 8000 | FastAPI; volume `ssl_certs` → `/data/ssl` |
| worker | — | Celery: LDAP sync (очередь `default`) |
| worker-otp | — | Celery: ExpressMS / Telegram OTP (очередь `otp`) |
| **beat** | — | Celery Beat: **авто LDAP sync каждые 30 мин** |
| db | — | PostgreSQL 16 |
| redis | — | Celery + rate-limit |
| radius | 1812/udp | pyrad gateway → API |

### Модули `api` (реализовано)

| Модуль | Статус |
|--------|--------|
| LDAP auth + **только реальный AD** (mock удалён) | ✅ |
| **LDAP sync** (ручной + **авто beat 30 мин**, email, **displayName**) | ✅ |
| **LDAP sync filters** (OU, группа AD) | ✅ |
| Policy (require_2fa, factors, TTL, **enroll_invite_ttl**) | ✅ |
| Enrollment: TOTP, ExpressMS id, Telegram chat_id | ✅ |
| **Public enroll: LDAP auth → enroll_proof JWT → QR** | ✅ |
| **Admin issue TOTP** (без confirm) | ✅ |
| **Invite: ссылка без письма + email + SMTP-шаблон** | ✅ |
| OTP / TOTP / challenge store | ✅ |
| **Tokens registry** (serial, status, revoke) | ✅ |
| Audit + **русские подписи событий и meta** | ✅ |
| **Settings** (LDAP, RADIUS, SMTP, ExpressMS, Telegram, **TLS/CA**, **Доступ**) | ✅ |
| **TLS upload** (cert+key, root CA → volume, nginx reload) | ✅ |
| **RBAC панели** (admin / operator / auditor) + смена пароля | ✅ |
| Policy engine по scope/группе AD | ❌ backlog |

### UI (реализовано)

- **Боковая панель:** Сводка → Токены → Пользователи → Политика → **Аудит** → **Настройки** (внизу nav).
- Дизайн: `docs/design/DESIGN.md` (Linear / awesome-claude-design).
- **Настройки:** вкладки на всю ширину — LDAP, RADIUS, ExpressMS, SMTP, Приложение, Telegram, **Сертификаты**; fieldset + `.field-hint`.
- **LDAP:** несколько DC (host+port), bind `domain\user`, SSL, **OU для загрузки**, **группа AD**.
- **SMTP:** тема и тело письма приглашения с подстановками `{username}`, `{invite_url}`, `{expires_at}`.
- **Сертификаты:** upload HTTPS (cert+key) и корневой CA; статус «загружен / активен».
- **Пользователи:** авто-sync hint; **Загрузить из LDAP**; фильтры (логин/имя, email, метод, TOTP confirm); колонки AD, **Имя (displayName)**, Email, активный метод, **настроенные каналы**; кнопки **Выпустить код**, **Копировать ссылку**, **Отправить приглашение**, **Настроить 2FA** (модал: метод, ExpressMS, Telegram).
- **Токены:** Revoke через **модальное подтверждение** (не `window.confirm`).
- **Аудит:** таблица на ширину экрана; колонки Время, **Событие (RU)**, Пользователь, **Подробности**.
- **Enroll** (`/enroll/{token}`): контейнер **560px**; сначала **логин+пароль LDAP**, затем QR; опционально ExpressMS/Telegram на confirm.

---

## 3) Модель данных

### `users`

| Поле | Описание |
|------|----------|
| ad_username | логин AD |
| **display_name** | **displayName из AD (sync)** |
| ldap_email | из LDAP sync (для приглашений) |
| otp_method | `TOTP` \| `EXPRESSMS` \| `TELEGRAM` \| `NONE` |
| expressms_id, telegram_chat_id | |
| totp_secret_encrypted, totp_confirmed | |
| **token_serial** | `TOTP…` / `EMS…` / `TGM…` |
| **token_active**, **last_used_at**, token_description | реестр токенов |
| created_at, updated_at | |

### `policies`

- require_2fa, allowed_second_factors (`TOTP,EXPRESSMS,TELEGRAM`)
- totp_window_steps, otp_ttl_seconds, max_otp_attempts_per_challenge
- challenge_ttl_seconds
- **enroll_invite_ttl_seconds** (срок ссылки приглашения, default 86400)

### `otp_challenges`

- state_token, user_id, method_used, otp_hash, TTL, consumed, attempts

### `enrollment_invites` (миграция 004)

| Поле | Описание |
|------|----------|
| token | уникальный URL-token |
| user_id | |
| created_by | admin username |
| email_to | |
| expires_at, consumed_at | |

### `system_settings`

| Группа | Ключи (примеры) |
|--------|------------------|
| **LDAP** | mock, mock_password, **servers** (JSON host+port), use_ssl, base_dn, bind_user, bind_password, user_attr, mock_users, **sync_ou**, **sync_group** |
| **RADIUS** | shared_secret, port (info), **allowed_clients** |
| **ExpressMS** | dry_run, api_url, token |
| **Telegram** | dry_run, bot_token |
| **SMTP** | dry_run, host, port, use_ssl, from_addr, username, password, **invite_subject**, **invite_body_template** |
| **App** | public_base_url (база ссылок invite) |
| **TLS** | web_cert_pem, web_key_pem, root_ca_pem (файлы в volume `ssl_certs`) |

Секреты в БД шифруются (`APP_ENCRYPTION_KEY`).

### `audit_events`

- LDAP_OK/FAIL, LDAP_SYNC, **LDAP_SYNC_AUTO**
- TOTP_ISSUE, TOTP_ENROLL_OK
- ENROLL_INVITE, **ENROLL_INVITE_LINK**, **ENROLL_AUTH_OK/FAIL**, ENROLL_INVITE_OK
- OTP_OK/FAIL, RADIUS_*, SEND_EXPRESSMS, SEND_TELEGRAM
- TOKEN_*, SETTINGS_PATCH, **TLS_WEB_UPLOAD**, **TLS_ROOT_CA_UPLOAD**, USER_PATCH

Подписи для UI: `api/app/audit_labels.py` → API отдаёт `event_label`, `meta_text`.

### Alembic

| Rev | Содержание |
|-----|------------|
| 001 | initial schema |
| 002 | system_settings, telegram_chat_id |
| 003 | token_serial, token_active, last_used_at |
| 004 | enrollment_invites, ldap_email, enroll_invite_ttl_seconds |
| **005** | **users.display_name** (из AD) |
| **006** | **admins.role, is_active, updated_at** (RBAC панели) |

---

## 4) Установка и деплой

### Lab (текущее окружение)

- Каталог: `/root/2fa`, Podman Compose, порты 80/443/8000/1812udp.
- Команды: `make up`, `make verify`, `make rebuild`.
- **После изменений api/web/migrations:** агент сам `podman build` → `compose down/up` → `alembic upgrade head` (**005**) → smoke `/health` (см. `.cursor/rules/deploy-lab.mdc`).
- Сервисы: **api, worker, beat, radius, web, db, redis**; volume **ssl_certs** для TLS.

### Bootstrap `.env`

- Секреты: `APP_ENCRYPTION_KEY`, JWT, internal token, Postgres.
- LDAP mock, demo user, RADIUS secret, SMTP dry-run, `PUBLIC_BASE_URL`.

### Установка в чистое окружение

```bash
# вариант A: уже есть клон
cd /path/to/2fa && sudo ./scripts/install.sh

# вариант B: clone в каталог
sudo ./scripts/install.sh --dir /opt/mk2fa \
  --repo https://github.com/MerlKoryAmber/2fa.git

sudo ./scripts/update.sh              # pull + rebuild
sudo ./scripts/uninstall.sh           # down
sudo ./scripts/uninstall.sh --purge   # + volumes
```

Пакеты: apt/dnf/yum/zypper/pacman/apk → podman + podman-compose (или Docker Compose).  
`.env` из `.env.example` + сгенерированные секреты; учётки: `.install-credentials.txt`.

### После установки — настройка в панели

1. **LDAP** — DC (несколько), bind `CORP\svc_mfa`, base DN, тест bind.
2. **RADIUS** — shared secret, **разрешённые NAS (IP/CIDR)**.
3. **SMTP** + **Public base URL** — для приглашений.
4. **2FA каналы** — ExpressMS, Telegram (dry-run → prod).
5. **Пользователи** — sync LDAP → выпуск кода / приглашение.
6. **Политика** — TTL invite, challenge, factors.

---

## 5) Enrollment и токены

### Реестр токенов (PrivacyIDEA-style, упрощённо)

- Один «токен» на enrolled user (serial, type, status: active / pending / disabled).
- Раздел **Токены**: фильтры, Enable / Disable / Revoke.
- API: `GET /api/tokens`, `PATCH /api/tokens/{serial}`.

### Когда выпускается serial

| Событие | confirm нужен? |
|---------|----------------|
| **Выпустить код** (admin) | нет — pending до confirm пользователем |
| TOTP enroll + confirm (admin UI) | да |
| **Приглашение** (email) | confirm на `/enroll/{token}` |
| PATCH user → method ≠ NONE | serial если не был |
| Seed demo | автоматически |

### Приглашение по email / ссылке

1. Admin: sync LDAP → user + email (+ **displayName**).
2. **Копировать ссылку** → `POST /api/users/{id}/invite-link` (без SMTP).
3. **Отправить приглашение** → `POST /api/users/{id}/invite` + письмо (SMTP dry-run → лог); тема/тело из настроек или дефолт.
4. Пользователь: `/enroll/{token}` → **LDAP login** → `enroll_proof` JWT → QR → код TOTP → опционально ExpressMS / Telegram chat_id.
5. TTL: **enroll_invite_ttl_seconds** в политике.

### Публичные API (без auth)

- `GET /api/public/enroll/{token}` — username, expires_at, `auth_required: true`
- `POST /api/public/enroll/{token}/auth` — `{ username, password }` → QR + `enroll_proof`
- `POST /api/public/enroll/{token}` — confirm `{ code, enroll_proof, expressms_id?, telegram_chat_id? }`

---

## 6) Фазы реализации — актуальный статус

| # | Фаза | Статус |
|---|------|--------|
| 1 | Каркас + compose + БД + админка | **✅ lab** |
| 2 | TOTP enroll + validate + RADIUS | **✅** |
| 3 | LDAP mock + **multi-DC + bind user UX** + **sync OU/group + auto beat** | **✅ mock**; **real AD lab: DC 192.168.0.175, Base DN DC=Merl,DC=loc** |
| 4 | ExpressMS dry-run + worker | **✅** |
| 4b | Telegram dry-run + RADIUS flow | **✅**; bot `/start` auto chat_id — **❌** |
| 5 | RADIUS challenge e2e | **✅ lab TOTP**; все 3 канала — частично |
| 6 | **Панель Settings** (LDAP, RADIUS, SMTP, …) + **TLS/CA** | **✅** |
| 6b | **Sidebar + Tokens + enroll/invite + users UX** | **✅** |
| 6c | **Enroll LDAP auth, audit RU, displayName, filters** | **✅** |
| 7 | Hardening (Alembic, rate-limit, HTTPS upload, health, beat) | **✅** |
| 8 | Discovery на реальном NAS | **❌** ждёт окружение |
| 9 | **install / update / uninstall + GitHub** | **✅** скрипты; приёмка на чистой ОС — по Merl |
| 10 | Policy engine по группе/scope AD | **❌** backlog |

---

## 7) API (основное)

### Admin (Bearer JWT)

- `GET/PATCH /api/settings`, `POST /api/settings/test-ldap`
- `POST /api/settings/tls/web`, `POST /api/settings/tls/root-ca`
- `GET /api/users?ad=&email=&method=&totp=`, `POST /api/users/sync-ldap`
- `PATCH /api/users/{id}` — метод 2FA, ExpressMS, Telegram
- `POST /api/users/{id}/totp/issue` — выпуск без confirm
- `POST /api/users/{id}/totp/enroll`, `POST .../confirm`
- `POST /api/users/{id}/invite-link` — ссылка без email
- `POST /api/users/{id}/invite` — email + ссылка
- `GET/PATCH /api/tokens/{serial}`
- `GET/PATCH /api/policies/{id}`, `GET /api/audit` (+ `event_label`, `meta_text`), `GET /api/stats`

### Internal (radius container)

- `GET /internal/radius/config` — secret + allowed_clients
- `POST /internal/radius/access-request`

### Public

- `GET /api/public/enroll/{token}`
- `POST /api/public/enroll/{token}/auth`
- `POST /api/public/enroll/{token}`

---

## 8) Чеклист перед prod

### RADIUS / NAS

- [ ] Discovery OTP в `User-Password`, `State`, таймауты
- [ ] allowed_clients заполнить реальными IP NAS
- [x] shared secret из панели

### LDAP

- [x] Real AD lab (DC `192.168.0.175`, `DC=Merl,DC=loc`)
- [x] UI: несколько DC, `domain\user`, SSL, OU, группа
- [x] sync пользователей + mail + **displayName**
- [x] **авто-sync Celery Beat 30 мин**

### ExpressMS / Telegram

- [ ] Prod API / bot token, dry_run=false
- [ ] Telegram enroll через бота (сейчас chat_id вручную / на enroll-странице / в модале пользователя)

### SMTP

- [ ] Prod SMTP, dry_run=false
- [x] Public base URL в настройках
- [x] **шаблон темы/тела приглашения**

### Security

- [x] секреты не в git, шифрование в БД
- [x] rate-limit, anti-replay State
- [x] **upload TLS cert/key + root CA из панели**
- [ ] RBAC админов через AD-группу
- [ ] retention audit

### Качество

- [x] `make verify` (~42–45 тест; стабильный fail: `test_normalize_bind_user_domain_backslash` — не наш функционал)
- [x] Alembic до **005**
- [ ] UI browser acceptance (§4 CLAUDE.md)
- [x] `scripts/install.sh` / `update.sh` / `uninstall.sh`
- [ ] приёмка install на чистой ОС

---

## 9) Backlog (явный хвост)

1. **Приёмка install** на чистой Debian/RHEL (не lab) — по Merl.
2. **Real AD prod** — RADIUS с живым NAS, не только lab.
3. **Telegram bot `/start`** — автоматический chat_id.
4. **Policy engine** — метод 2FA по группе/OU AD.
5. **Self-service** portal (не только admin enroll).
6. Sync плана/кода → **origin/main** (push по команде Merl).

---

## 10) Ключевые файлы (реализованное)

| Область | Файлы |
|---------|-------|
| LDAP sync + displayName | `api/app/ldap_auth.py`, `api/app/ldap_sync.py`, `api/app/tasks.py`, `api/app/celery_app.py` |
| Enroll auth + proof | `api/app/routers/public_enroll.py`, `web/enroll.js`, `web/enroll.html` |
| Users API/UI | `api/app/user_service.py`, `api/app/routers/admin.py`, `web/app.js`, `web/index.html` |
| Invites + SMTP template | `api/app/enroll_service.py`, `api/app/mail_service.py`, settings keys |
| TLS | `api/app/tls_service.py`, `api/app/routers/settings.py`, volume `ssl_certs` в `docker-compose.yml` |
| Audit RU | `api/app/audit_labels.py`, `tests/test_audit_labels.py` |
| Миграции | `api/alembic/versions/004_*.py`, `005_user_display_name.py` |

---

## 11) Отличия от старой редакции плана

| Было | Стало |
|------|--------|
| UAG-specific | Любой RADIUS challenge-flow |
| LDAP/RADIUS только `.env` | **Панель + system_settings** |
| TOTP + ExpressMS | **+ Telegram** |
| Bind DN, один URL | **bind user**, **несколько DC** |
| Enroll только в админке | **+ issue код, + invite link/email, public enroll + LDAP auth** |
| Нет реестра токенов | **Токены** (PrivacyIDEA-lite) + modal Revoke |
| Top nav | **Sidebar**, настройки после Аудита |
| RADIUS без ACL | **allowed_clients IP/CIDR** |
| Ручной деплой | **Агент деплоит сам** (deploy-lab.mdc) |
| Audit EN | **Аудит RU** + колонка Подробности |
| Нет displayName | **Имя из AD** в таблице пользователей |
| Ручной LDAP sync | **+ Celery Beat 30 мин** + OU/group filters |
| Self-signed only | **Upload TLS + root CA** из панели |
| Один invite flow | **Копировать ссылку** / **Отправить** + SMTP-шаблон |
| Users inline edit | **Модал «Настроить 2FA»** + фильтры таблицы |

---

## 12) Lab credentials (сменить перед prod)

- Admin: `admin` / `admin`
- Demo: user `demo`, LDAP mock pass `demo`, TOTP secret `JBSWY3DPEHPK3PXP`
- RADIUS secret: `testing123` (из настроек)
- URL lab: `https://192.168.0.178/`
- LDAP lab: DC `192.168.0.175`, Base DN `DC=Merl,DC=loc`

### Деплой (грабля lab)

`podman-compose up --force-recreate api` **не** подхватывает новый образ → 404 на новых маршрутах.  
**Fix:** полный `podman-compose down && up -d` → `alembic upgrade head` → `curl -sk https://127.0.0.1/health`.

---

_Источник репозитория:_ https://github.com/MerlKoryAmber/2fa  
_Метод работы:_ `CLAUDE.md`, handoff: `docs/handoff/`, отчёты: `docs/agent_reports/`
