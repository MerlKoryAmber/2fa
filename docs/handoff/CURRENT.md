# Handoff — текущее состояние

Обновлять **перед каждым `git push`** (и при смене сессии / незавершёнке). Время — **МСК**.

## Срез

| Поле | Значение |
|------|----------|
| Дата | 2026-08-23 ~00:56 МСК |
| GitHub | `main` — после этого push: docs backlog (см. CHANGELOG 2026-08-23) |
| Фича HEAD кода | otp_only + policy scope + SMTP + dashboard MVP (**код не менялся** 23.08) |
| Локальный workspace | `/root/2fa` (lab) |
| Сервер | CentOS Stream 9, **`/opt/2fa`** |
| Alembic head | **007** |
| LinOTP → тест | **все пользователи/токены импортированы** (подтверждено Merl 21.08) |
| Вход панели | `admin` / `admin`, форма пустая |
| Push | только по команде Merl; **не** `git add .` |

## Живой стенд — ПРИНЯТО (21.08 ~20:49 МСК)

Цепочка: **HCPGW-CL** (`172.22.1.167`) → **NPS proxy** (`172.22.10.231`, policy `u1807`) → **MK 2FA** (`172.22.10.140`).

- Политика **otp_only**; пользователь **U1807** + TOTP из LinOTP (пилот); **полный импорт LinOTP — да**
- **Верный OTP** → пускает (Accept)
- **Неверный OTP** → отбивает (Reject), без NPS **117**

Грабли по пути (уже в коде): ACL `parse_allowed_clients`; Message-Authenticator; `network_mode: host`; эхо **Proxy-State** + MA первым attr.

## Что вошло (сессия 22–23.08) — только docs

Исследование / backlog (реализации нет):

| Файл | О чём |
|------|--------|
| `docs/backlog/EXPRESS_INTEGRATION.md` | eXpress BotX; кнопки; push; изоляция TOTP; фазы; CP/UAG fallback → **гибкие политики после** push MVP |
| `docs/backlog/EXTERNAL_INTEGRATION_API.md` | Invite API: ключ+IP; логин+email; ldap/sync; контейнер `integration` |
| `docs/backlog/PROD_SAFE_DEPLOY.md` | TOTP invariant; клон prod редко (другая команда) |
| `docs/backlog/RADIUS_POLICY_SOURCE_IP.md` | **Вариант 1 отложено**: прокси + политика по `NAS-IP-Address` (CP otp_only, UAG challenge, failover 2FA) |

Код/стенд VPN — без изменений относительно `059ec66` / приёмки 21.08.

## Ключевые файлы

| Зачем | Где |
|-------|-----|
| otp_only | `api/app/radius_flow.py`, ADR `docs/adr/0001-radius-otp-only.md` |
| Policy per NAS | `api/app/policy_resolve.py`, ADR `docs/adr/0002-policy-per-radius-client.md` |
| Backlog отложенки | `docs/backlog/*.md` |
| Сводка | `api/app/dashboard.py` |

## Хвосты

- **Express/BotX (отложено):** `EXPRESS_INTEGRATION.md` — ждать доку готовых решений; порядок: push MVP → гибкие политики; TOTP не ломать
- **RADIUS policy IP (отложено):** вариант **1** — `RADIUS_POLICY_SOURCE_IP.md`
- **Внешний API invite (отложено):** `EXTERNAL_INTEGRATION_API.md`
- **Prod-safe deploy:** `PROD_SAFE_DEPLOY.md`
- Backlog: Telegram `/start`, Discovery NAS, policy OU
- Cutover LinOTP — по команде Merl

**Уже на стенде:** `allowed_clients` заполнен; полный импорт LinOTP; VPN otp_only принят.

## Не делать без команды Merl

- Force-push; `compose down -v` на не-lab
- Apply миграции токенов / коммит `.env` / дампа LinOTP
- Менять git config
- **Клон prod VM** — только по согласованию; `PROD_SAFE_DEPLOY.md`
- Реализация Express / integration API / NAS-IP policy — только по явной задаче

## Следующий агент — старт

1. `git pull --ff-only`
2. Handoff + CHANGELOG верх + `docs/backlog/`
3. Стенд VPN U1807 зелёный — не чинить RADIUS «с нуля»
4. Caveman RU; не `git add .`
