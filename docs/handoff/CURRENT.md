# Handoff — текущее состояние

Обновлять **перед каждым `git push`** (и при смене сессии / незавершёнке). Время — **МСК**.

## Срез

| Поле | Значение |
|------|----------|
| Дата | 2026-08-31 ~13:40 МСК |
| GitHub | `main` (fix INTERNAL_API_TOKEN для push) |
| Локальный workspace | `/root/2fa` |
| Alembic head | **010** |
| Вход панели | `admin` / `admin`, форма пустая |

## Что вошло (код)

- **Push 403:** API и express-bot читают `INTERNAL_API_TOKEN` из `host.env` (как radius); compose mount для express-bot
- Ранее: `express_channel_enabled`, UI политик, URL бота без `/command`

## Хвосты

- **Выкат:** `cd /opt/2fa && sudo ./scripts/update.sh` (rebuild api + express-bot)
- После выката: VPN U1807 — push должен уйти дальше 403; если 400 `no_chat` — email/`/start`
- `BOTX_API_HOST`, URL бота в Express, push-тест end-to-end
- Настройки бота в панели — после успешного push

## Не делать без команды Merl

- Force-push; `compose down -v`
- Коммит `.env`
- Ручной alembic вместо `update.sh`

## Следующий агент — старт

1. `update.sh` на hmk2fa → повторить VPN push для U1807
2. Логи: api без `403 express-bot`; bot — `botx notify` или `no_chat`
3. Caveman RU; не `git add .`
