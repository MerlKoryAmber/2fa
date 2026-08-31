# Handoff — текущее состояние

Обновлять **перед каждым `git push`**. Время — **МСК**.

## Срез

| Поле | Значение |
|------|----------|
| Дата | 2026-08-31 ~15:10 МСК |
| GitHub | `main` (fix парсер Approve BotX) |
| Alembic head | **010** |

## Что вошло (код)

- Approve в Express: парсер webhook (string command, challenge_id); «Вход разрешён» на стенде подтверждён
- Ранее: RADIUS hold 120s, chats/create, trust_env, express_channel_enabled

## Хвосты

- **Выкат:** `update.sh` — express-bot + api (логи decision)
- **Check Point:** VPN Accept только если Approve **до** `express_push_timeout`; CP RADIUS timeout ≥ push_wait
- otp_only: поле OTP пустое на push-попытке или сценарий только push без TOTP в том же окне
- E2E: Approve → `EXPRESS_PUSH_DECISION` + `RADIUS_ACCEPT` в аудите

## Следующий агент

1. После update — VPN U1807, Approve в окне push_wait
2. Если timeout в аудите — CP timeout или Approve поздно
