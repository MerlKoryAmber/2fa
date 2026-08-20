# CHANGELOG

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
