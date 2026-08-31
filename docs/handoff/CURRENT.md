# Handoff — текущее состояние

Обновлять **перед каждым `git push`** (и при смене сессии / незавершёнке). Время — **МСК**.

## Срез

| Поле | Значение |
|------|----------|
| Дата | 2026-08-31 ~13:50 МСК |
| GitHub | `main` (push trust_env + логи + smoke) |
| Локальный workspace | `/root/2fa` |
| Alembic head | **010** |
| Вход панели | `admin` / `admin`, форма пустая |

## Что вошло (код)

- **Push 403 (прокси):** `express_push` `trust_env=False`, `NO_PROXY` в compose — как фикс radius→api
- Логи api/express-bot с **временем**; smoke API→express-bot после update (400/200 ок, 403 стоп)
- Ранее: `INTERNAL_API_TOKEN` из host.env, `express_channel_enabled`

## Хвосты

- **Выкат:** `sudo ./scripts/update.sh` на hmk2fa — smoke express push должен быть зелёным
- VPN U1807: после 403 — если 400 `no_chat` → `/start` или email; если `botx notify` — `BOTX_API_HOST`
- Настройки бота в панели — после end-to-end push

## Не делать без команды Merl

- Force-push; `compose down -v`; коммит `.env`

## Следующий агент — старт

1. `update.sh` на стенде; смотреть smoke express push в конце
2. Caveman RU; не `git add .`
