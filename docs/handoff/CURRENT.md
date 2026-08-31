# Handoff — текущее состояние

Обновлять **перед каждым `git push`** (и при смене сессии / незавершёнке). Время — **МСК**.

## Срез

| Поле | Значение |
|------|----------|
| Дата | 2026-08-31 ~12:55 МСК |
| GitHub | `main` (express_channel_enabled + UI политик) |
| Локальный workspace | `/root/2fa` |
| Alembic head | **010** (`users.express_channel_enabled`) |
| Вход панели | `admin` / `admin`, форма пустая |

## Что вошло (код)

- **Express канал:** `express_channel_enabled` — галка в админке и enroll; push только при включении + email/chat
- Миграция 010: у существующих с `expressms_id` канал включён; остальные — выкл. до галки
- Политика UI: сценарии 2/3 описывают fallback на TOTP при выключенном Express у пользователя
- Express-bot: «Адрес бота» в консоли = `https://<хост>:8030` **без** `/command` (иначе 404 `/command/command`)

## Хвосты

- **Выкат на тест:** `cd /opt/2fa && sudo ./scripts/update.sh` (alembic **010** + web/api)
- В консоли Express на стенде: поправить URL бота (убрать `/command` с конца), проверить `BOTX_API_HOST`
- Включить Express галкой у пользователей, кому нужен push (кроме уже привязанных через `/start`)
- Настройки бота в панели — после успешного push-теста
- Telegram — отложено

## Не делать без команды Merl

- Force-push; `compose down -v`
- Коммит `.env`
- Ручной alembic / точечный `podman exec` вместо `update.sh`/`install.sh`

## Следующий агент — старт

1. `git pull --ff-only` → `sudo ./scripts/update.sh` на hmk2fa
2. Express: URL бота без суффикса `/command`; логи `express-bot` при `/помощь`
3. Caveman RU; не `git add .`
