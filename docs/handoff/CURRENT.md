# Handoff — текущее состояние

Обновлять **перед каждым `git push`**. Время — **МСК**.

## Срез

| Поле | Значение |
|------|----------|
| Дата | 2026-08-31 ~18:50 МСК |
| GitHub `main` | `4903e15` (+ этот handoff) |
| Alembic head | **010** |
| Лаба | HMK2FA `/opt/2fa` (локальная сеть); код: `git pull` + `update.sh` |
| tes | удалённая площадка — **только git** после приёмки на лабе |

## Принято на лабе (Express push VPN)

- Политика: `otp_only` + `mfa_scenario=express_push`, `push_wait_seconds=60`
- U1807: `express_channel_enabled`, email `revelis_ea@interros.ru` (chat_id может быть пуст — push по email)
- **HNPS Connection timeout = 30 с** (было 5) → VPN **пускает** после Approve
- Цепочка: CP AD → поле OTP (обязательно) → RADIUS hold → Express Approve → Accept
- MK2FA при `express_push` **не проверяет** `User-Password` (в логах `pwd_len=6` — заглушка клиента)

## UX: поле OTP после пароля

**Не баг MK2FA.** Профиль CP: **локальная проверка AD + RADIUS 2-й фактор** → клиент **всегда** требует непустое поле OTP (до RADIUS).

| Сценарий | Что вводить в OTP | MK2FA |
|----------|-------------------|--------|
| TOTP | настоящий код | `verify_totp` |
| Express push | **заглушка** `000000` (или любые 6 символов) | игнор password → push |

Kontur без поля OTP — **другой метод MFA в SmartConsole**, не «RADIUS OTP». Убрать поле при текущем профиле CP **нельзя кодом MK2FA**.

Док NPS 117: `docs/backlog/NPS_EXPRESS_PUSH_TIMEOUT.md`  
Диагностика: `sudo ./scripts/diagnose_radius_push.sh U1807`

## Код MK2FA (в main)

- Sync hold Express push (`otp_only`), без Access-Challenge на push
- `RADIUS_API_TIMEOUT=120`, radius **workers=32**, дедуп state на ретраях (`EXPRESS_PUSH_REUSE`)
- Аудит: `EXPRESS_PUSH_SEND` / `HOLD` / `REUSE` / `DECISION` / `RADIUS_ACCEPT`
- Approve BotX: парсер webhook; push по email + `chats/create`

## Хвосты / следующий агент

1. **CP Discovery (открыто):** как убрать обязательное OTP-поле при Express — только смена authentication scheme / MFA-профиля на CP (сравнить с Kontur). MK2FA не трогать, пока профиль = AD+RADIUS OTP.
2. Инструкция пользователям Express: OTP=`000000` + Approve (опционально — в README/enroll, по запросу Merl).
3. На tes: `git pull` + `update.sh`; NPS timeout ≥ hold (не меньше ~30 с).
4. Не предлагать Access-Challenge ради UX CP — поле OTP не уберёт.

## Не делать

- Двухфазный Access-Challenge для CP push
- Ломать TOTP `otp_only` path
- scp на tes — только git

## Старт с другого клиента

```bash
cd /opt/2fa   # или clone
git pull --ff-only
git log -1 --oneline   # свежий handoff-коммит
# читать этот файл целиком
sudo ./scripts/diagnose_radius_push.sh U1807
```

Транскрипт сессии (если нужен контекст чата): agent transcript `a3236713-321a-4c1e-a960-cfd1afd6957d`.
