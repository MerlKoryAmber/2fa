# Handoff — текущее состояние

Обновлять **перед каждым `git push`**. Время — **МСК**.

## Срез

| Поле | Значение |
|------|----------|
| Дата | 2026-08-31 ~16:50 МСК |
| GitHub `main` | fix radius workers (NPS 117 на push) |
| Alembic head | **010** |
| Lab | `/opt/2fa` — pull + `update.sh` (пересборка **radius**) |

## Что вошло (код)

- **radius:** пул потоков на UDP — hold Express push не блокирует ретраи HNPS (reason 117 при рабочем TOTP)
- Ранее: express push otp_only hold, Approve BotX, `EXPRESS_PUSH_HOLD`, RADIUS_API_TIMEOUT=120

## Хвосты

- **Lab:** `git pull` → `sudo ./scripts/update.sh` → VPN U1807 + Approve
- В логе radius: `workers=32`, на push `api_s=…`
- E2E: без 117 на HNPS при `express_push`

## Не делать

- Двухфазный Access-Challenge для CP push — поле OTP
- Откат radius в однопоток

## Следующий агент

1. Приёмка push VPN после rebuild radius
2. Если 117 остаётся — таймстемпы NPS vs `api_s` в radius log
