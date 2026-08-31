# Handoff — текущее состояние

Обновлять **перед каждым `git push`**. Время — **МСК**.

## Срез

| Поле | Значение |
|------|----------|
| Дата | 2026-08-31 ~16:00 МСК |
| GitHub `main` | после коммита express push hold / otp_only |
| Alembic head | **010** |
| Lab | `/opt/2fa` — `update.sh` после pull |

## Что вошло (код)

- Express push `otp_only`: CP проверяет 1-й фактор; MK2FA — только push (hold, без Challenge)
- Аудит `EXPRESS_PUSH_HOLD` (wait_Ns); poll Approve 0.25 с
- Тест: TOTP в `User-Password` не принимается при сценарии `express_push`
- Ранее: парсер Approve BotX, RADIUS hold 120s, express_channel_enabled

## Хвосты

- **Lab:** `git pull` + `sudo ./scripts/update.sh` (api)
- **HNPS:** Remote RADIUS timeout ≥ `push_wait_seconds` + запас (иначе reject на CP, Accept в аудите поздно)
- E2E U1807: пароль → hold (как Kontur) → Approve → VPN без TOTP при `express_push`

## Не делать

- Двухфазный Access-Challenge для CP push — рисует поле OTP
- Коммит без CHANGELOG/handoff

## Следующий агент

1. Lab VPN U1807 + таймстемпы аудита vs HNPS
2. Если timeout — поднять таймаут RADIUS на HNPS, не менять схему на Challenge
