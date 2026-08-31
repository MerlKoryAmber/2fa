# Handoff — текущее состояние

Обновлять **перед каждым `git push`**. Время — **МСК**.

## Срез

| Поле | Значение |
|------|----------|
| Дата | 2026-08-31 ~17:30 МСК |
| GitHub `main` | дедуп Express push на ретраях HNPS |
| Alembic head | **010** |
| Lab | `git pull` + `sudo ./scripts/update.sh` (api + radius) |

## Что вошло (код)

- **Дедуп push:** ретраи HNPS → `EXPRESS_PUSH_REUSE`, один state; без второго push
- **radius:** workers=32, лог `recv id=`; diagnose: `scripts/diagnose_radius_push.sh U1807`
- Ранее: otp_only express hold, Approve BotX, RADIUS_API_TIMEOUT=120

## Хвосты

- Lab VPN U1807: один `EXPRESS_PUSH_SEND`, ретраи → `REUSE`, затем `RADIUS_ACCEPT`
- HNPS без 117 при Approve в окне `push_wait_seconds`

## Не делать

- Access-Challenge на CP push
- Новый push на каждый ретрай NPS

## Следующий агент

1. `./scripts/diagnose_radius_push.sh` после попытки VPN
2. Если 117 — сверить `recv id=` в radius с Event Viewer HNPS
