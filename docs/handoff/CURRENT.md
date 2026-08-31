# Handoff — текущее состояние

Обновлять **перед каждым `git push`**. Время — **МСК**.

## Срез

| Поле | Значение |
|------|----------|
| Дата | 2026-08-31 ~17:50 МСК |
| GitHub `main` | docs NPS Connection timeout + diagnose warn |
| Alembic head | **010** |
| Лаба HMK2FA | pull + update; **HNPS timeout** — не код MK2FA |

## Диагноз 117 (лаба, подтверждено)

- MK2FA: `decision=accept`, `api_s≈6` — ответ есть
- HNPS: **117** — таймаут **Remote RADIUS Server Group → Connection timeout** (default **5 с**)
- TOTP < 1 с → ок; push hold > 5 с → 117 до Accept

## Действие на лабе (HNPS)

Remote RADIUS Server Group (MK2FA) → **Connection timeout = 120** (≥ push_wait 60 + запас).  
Док: `docs/backlog/NPS_EXPRESS_PUSH_TIMEOUT.md`

## Код MK2FA (готово)

- workers=32, дедуп push, diagnose, hold otp_only

## tes (удалённая)

Только git после приёмки на лабе.

## Следующий агент

1. После поднятия timeout на HNPS — VPN U1807 + Approve
2. Не копать MK2FA, если `accept` в radius и `api_s` > 5
