# Handoff — текущее состояние

Обновлять **перед каждым `git push`** (и при смене сессии / незавершёнке). Время — **МСК**.

## Срез

| Поле | Значение |
|------|----------|
| Дата | 2026-08-21 ~01:25 МСК |
| Ветка / коммит | `main` @ `dfdebb6` (UI MK 2FA + worker-otp) |
| Lab | `/root/2fa`, podman-compose |
| Alembic head | **007** |
| UI | **MK 2FA**: navy/gold, Cinzel + Inter локально, topbar = brand height |

## Что сделано

- **worker-otp**: очередь `otp` (ExpressMS/Telegram); `worker` — только `default` (LDAP)
- UI: Interros look, бренд MK 2FA, выравнивание brand/topbar
- LinOTP export без фильтра даты; инструменты в `migration/`

## Хвосты

- Полный `guid_map.csv` → export → import на тест
- Fail теста: `test_normalize_bind_user_domain_backslash`
- Backlog: Telegram `/start`, Discovery NAS, policy OU; вариант B (отдельные worker на канал) — не делали

## Не делать без команды Merl

- Force-push; `compose down -v` на не-lab
- Apply миграции токенов в prod
- Коммит секретов / `.env` / дампа LinOTP

## Следующий агент — старт

1. Handoff + CHANGELOG верх
2. `podman ps` — есть `worker` и `worker-otp`
3. Не `git add .`
