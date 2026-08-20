# Handoff — текущее состояние

Обновлять **перед каждым `git push`** (и при смене сессии / незавершёнке). Время — **МСК**.

## Срез

| Поле | Значение |
|------|----------|
| Дата | 2026-08-21 ~01:40 МСК |
| Ветка / коммит | `main` — MK 2FA rename + F5-tab (после push) |
| Lab | `/root/2fa`, podman-compose |
| Alembic head | **007** |
| UI | **MK 2FA**; hash-вкладки; крупное меню сайдбара |

## Что сделано

- Own → **MK 2FA** (README, API, issuer, scripts, `PLAN_MK_2FA_SYSTEM_RU.md`)
- F5: вкладка не сбрасывается; нет flash чужих секций; меню крупнее
- **worker-otp**; UI Interros

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
