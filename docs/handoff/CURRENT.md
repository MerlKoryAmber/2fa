# Handoff — текущее состояние

Обновлять **перед каждым `git push`** (и при смене сессии / незавершёнке). Время — **МСК**.

## Срез

| Поле | Значение |
|------|----------|
| Дата | 2026-08-25 ~11:32 МСК |
| GitHub | `main` (после этого push — Express-бот + install) |
| Локальный workspace | `/root/2fa` |
| Сервер | CentOS Stream 9; канон `/opt/2fa`; бот на **том же хосте**, что API (`:8030`) |
| Alembic head | **008** (`policies.expressms_mode`) |
| Вход панели | `admin` / `admin`, форма пустая |
| Push | только по команде Merl; **не** `git add .` |

## Что вошло (код, 24–25.08)

- `express-bot/`: webhook `/command` (сразу 200), JWT + `notifications/direct/sync`, Approve/Deny, `/start` bind chat
- API: `/internal/express/bind`, `/internal/express/decision`; Redis hold для RADIUS push
- Политика `expressms_mode=otp\|push` (default **otp**). TOTP `otp_only` не трогать
- Compose: сервис `express-bot`, порт **8030**
- `install.sh` / `update.sh`: спрашивают `BOTX_API_HOST`, `BOT_ID`, `BOT_SECRET_KEY`; `compose build express-bot`; firewall 8030/tcp; `--skip-express`
- UI политики: radio ExpressMS otp/push

`BOTX_API_HOST` = CTS/API **отправки**, не listener 8030. «Адрес бота» в Express = `https://<хост-2fa>:8030/command`.

Секреты: `.env` / `.env.express-bot` (gitignore). Не коммитить.

## Живой стенд VPN — ПРИНЯТО (21.08)

HCPGW-CL → NPS proxy → MK 2FA. Политика **otp_only**, U1807. Не ломать RADIUS «с нуля».

## Хвосты

- Заполнить **реальный** `BOTX_API_HOST` на стенде (не путать с `:8030`)
- Alembic **008** + `compose up express-bot` на hmk2fa
- Express «Адрес бота» → этот хост `:8030/command`
- Пользователи: `/start`; политика push только EXPRESSMS
- **RADIUS policy IP** / invite API / prod clone — отложено, `docs/backlog/`
- Cutover LinOTP — по команде Merl

## Не делать без команды Merl

- Force-push; `compose down -v` на не-lab
- `update.sh` на живом стенде без явной просьбы (полный rebuild)
- Коммит `.env` / секретов бота
- Менять git config

## Следующий агент — старт

1. `git pull --ff-only`
2. Handoff + CHANGELOG верх + alembic **008**
3. VPN otp_only зелёный — не чинить RADIUS с нуля
4. Caveman RU; не `git add .`
