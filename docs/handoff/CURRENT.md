# Handoff — текущее состояние

Обновлять **перед каждым `git push`** (и при смене сессии / незавершёнке). Время — **МСК**.

## Срез

| Поле | Значение |
|------|----------|
| Дата | 2026-08-25 ~15:40 МСК |
| GitHub | `main` (после push — mfa_scenario 009) |
| Локальный workspace | `/root/2fa` |
| Alembic head | **009** (`mfa_scenario`, `push_wait_seconds`) |
| Вход панели | `admin` / `admin`, форма пустая |

## Что вошло (код)

- Юзер: **каналы** (TOTP / Express по email±chat), без UI «активный метод»
- Политика: `mfa_scenario` = totp \| express_push \| express_push_then_totp; `push_wait_seconds`
- RADIUS: push Approve→Accept; **Deny→Reject**; timeout→TOTP только при then_totp
- Express доступен при `ldap_email` или `expressms_id` (не обязателен otp_method=EXPRESSMS)
- Telegram — **не** в сценариях
- Модалка «Выпустить код»

## Хвосты

- **Выкат на тест:** `cd /opt/2fa && sudo ./scripts/update.sh` (сам pull + rebuild + alembic **009** + Express). Не `podman exec alembic` руками.
- Настройки бота в панели — **после успешного теста** push
- Telegram — отложено
- RADIUS policy IP / invite API — отложено

## Не делать без команды Merl

- Force-push; `compose down -v`
- Коммит `.env`
- Ручной alembic / точечный `podman exec` вместо `update.sh`/`install.sh`

## Следующий агент — старт

1. `git pull --ff-only` (или сразу `update.sh`)
2. На стенде: **`sudo ./scripts/update.sh`** — не руками alembic/compose
3. Caveman RU; не `git add .`
