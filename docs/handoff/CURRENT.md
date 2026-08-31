# Handoff — текущее состояние

Обновлять **перед каждым `git push`** (и при смене сессии / незавершёнке). Время — **МСК**.

## Срез

| Поле | Значение |
|------|----------|
| Дата | 2026-08-31 ~14:00 МСК |
| GitHub | `main` (BotX chats/create при personal 404) |
| Alembic head | **010** |
| Вход панели | `admin` / `admin` |

## Что вошло (код)

- Push по email: если `chats/personal` 404 — `chats/create` (нужен `allow_chat_creating` у бота)
- Ранее: trust_env, INTERNAL_API_TOKEN, express_channel_enabled

## Хвосты

- **Выкат:** `sudo ./scripts/update.sh` на hmk2fa
- Express: `allow_chat_creating=true` у бота; VPN U1807 — смотреть `botx chats/create` / `notify` в логах
- End-to-end push Approve → RADIUS Accept

## Следующий агент

1. `update.sh` → VPN push U1807
2. Логи express-bot: `chats/create status=200`, `botx notify status=200`
