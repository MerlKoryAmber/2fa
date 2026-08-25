# Handoff — текущее состояние

Обновлять **перед каждым `git push`** (и при смене сессии / незавершёнке). Время — **МСК**.

## Срез

| Поле | Значение |
|------|----------|
| Дата | 2026-08-25 ~15:15 МСК |
| GitHub | `main` (после push — фикс «Выпустить код» + Express-бот `1402cf0`) |
| Локальный workspace | `/root/2fa` |
| Сервер | CentOS Stream 9; канон `/opt/2fa`; бот на **том же хосте**, что API (`:8030`) |
| Alembic head | **008** (`policies.expressms_mode`) |
| Вход панели | `admin` / `admin`, форма пустая |
| Push | только по команде Merl; **не** `git add .` |

## Что вошло

- Express-бот + install/update (коммит `1402cf0`)
- UI: «Выпустить код» — модалка overlay + ошибки (не панель внизу таблицы)

Согласовано (ещё не в коде): юзер = **каналы** (TOTP секрет+confirm / Express по **email из AD**, `/start` опционален); порядок/fallback — **политика**; Telegram — **отложено**.

## Хвосты

- **Выкат на тест:** pull на `/opt/2fa`, BOT_*, express-bot, alembic 008, сеть 8030, «Адрес бота»
- Docs/ADR: каналы без «активного метода» + push→TOTP (Deny = reject)
- Код модели push→TOTP — после приёмки push на тесте (или по команде)
- Telegram — backlog, не трогать
- RADIUS policy IP / invite API — отложено

## Не делать без команды Merl

- Force-push; `compose down -v` на не-lab; полный `update.sh` без просьбы
- Коммит `.env` / секретов

## Следующий агент — старт

1. `git pull --ff-only`
2. Выкат бота на тест (п. хвосты)
3. Caveman RU; не `git add .`
