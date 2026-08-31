# Handoff — текущее состояние

Обновлять **перед каждым `git push`**. Время — **МСК**.

## Срез

| Поле | Значение |
|------|----------|
| Дата | 2026-08-31 ~14:50 МСК |
| GitHub | `main` (RADIUS hold 120s для push) |
| Alembic head | **010** |

## Что вошло (код)

- RADIUS→API timeout **120 с** (push hold); fallback TOTP после таймаута push; `EXPRESS_PUSH_LATE`
- Ранее: BotX chats/create, trust_env, INTERNAL_API_TOKEN, express_channel_enabled

## Хвосты

- **Выкат:** `sudo ./scripts/update.sh` на hmk2fa
- **Check Point:** RADIUS timeout на gateway ≥ `push_wait_seconds` + запас (60–120 с)
- Политика CP: сценарий **только push** (без TOTP в том же окне) или `push→TOTP` осознанно
- E2E: VPN → push → Approve **без** ввода TOTP → Accept

## Следующий агент

1. `update.sh` → VPN U1807, Approve в Express
2. Логи radius: `api_timeout=120s`, `decision=accept`
