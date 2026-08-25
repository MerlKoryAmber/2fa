# Express-бот MK 2FA — сборка и доставка

Бот ставится **на свой сервер 2FA** (`hmk2fa.interros.ru`), рядом с API.  
Слушает **:8030**. BotX (платформа) — другой хост; URL для **отправки** — поле `BOTX_API_HOST`.

«Адрес бота» в консоли Express: `https://hmk2fa.interros.ru:8030/command`  
(если снаружи только 443 — проксируйте `/command` на `127.0.0.1:8030` и укажите `https://hmk2fa.interros.ru/command`.)

---

`install.sh` / `update.sh` спрашивают `BOTX_API_HOST`, `BOT_ID`, `BOT_SECRET_KEY`, собирают сервис `express-bot` вместе со стеком, гоняют **alembic**. Без вопросов: `--skip-express`.

**На стенде:** не `podman exec … alembic` руками — только `sudo ./scripts/update.sh` (или `install.sh` с нуля).

## Сборка

На **hmk2fa** (каталог репо, обычно `/opt/2fa`):

```bash
cd /opt/2fa
git pull --ff-only    # или scp дерева
podman build -t localhost/mk2fa-express-bot:latest ./express-bot
```

Docker: `docker build -t localhost/mk2fa-express-bot:latest ./express-bot`

Проверка образа: `podman images | grep mk2fa-express-bot`

### Без контейнера (отладка)

```bash
cd express-bot
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
# .env: BOT_ID, BOT_SECRET_KEY, BOTX_API_HOST, MK2FA_API_URL, INTERNAL_API_TOKEN
uvicorn app.main:app --host 0.0.0.0 --port 8030
curl -fsS http://127.0.0.1:8030/health
```

Тесты: `cd express-bot && PYTHONPATH=. python3 -m pytest tests -q`

---

## Доставка (тот же сервер, что API)

Код уже на hmk2fa — образ собрать там, секреты в `.env` **не** в git.

В `.env` стека (тот же файл, что у api/radius):

```env
BOT_LISTEN_HOST=0.0.0.0
BOT_LISTEN_PORT=8030
BOT_ID=<uuid из консоли Express>
BOT_SECRET_KEY=<секрет>
BOT_APP_ID=push2fa_bot
BOTX_API_HOST=<CTS/API отправки, с http(s) и портом>
MK2FA_API_URL=http://api:8000
EXPRESS_BOT_URL=http://express-bot:8030
INTERNAL_API_TOKEN=<уже есть у API>
```

`MK2FA_API_URL` из контейнера бота — имя сервиса `api`.  
`EXPRESS_BOT_URL` из контейнера API — имя сервиса `express-bot`.

### Compose (предпочтительно)

На стенде канон:

```bash
cd /opt/2fa
sudo ./scripts/update.sh
curl -fsS http://127.0.0.1:8030/health
curl -sk https://127.0.0.1/health
```

Скрипт: pull → параметры Express → build api/radius/web/express-bot → up → **alembic upgrade head** → smoke.

Отладка только бота (не вместо update на стенде):

```bash
cd /opt/2fa
podman-compose up -d --build express-bot
curl -fsS http://127.0.0.1:8030/health
```

### Только контейнер бота, без compose

```bash
podman run -d --name mk2fa-express-bot --restart unless-stopped \
  --env-file /opt/2fa/.env \
  -e MK2FA_API_URL=http://127.0.0.1:8000 \
  -p 8030:8030 \
  --network host \
  localhost/mk2fa-express-bot:latest
```

При `--network host` в `.env` API: `EXPRESS_BOT_URL=http://127.0.0.1:8030`, бот: `MK2FA_API_URL=http://127.0.0.1:8000`.

---

## Сеть

| Откуда | Куда | Зачем |
|--------|------|--------|
| BotX | `hmk2fa:8030` (или 443 + path) `POST /command` | входящие и нажатия |
| Бот | `BOTX_API_HOST` | отправка в Express |
| Бот | API `8000` (внутренняя сеть compose) | bind + decision |
| API | `EXPRESS_BOT_URL` `POST /internal/push` | запрос пуша, `X-Internal-Token` |

firewalld на hmk2fa: **8030/tcp** (или 443) **с адресов BotX**.  
Исходящий с hmk2fa до CTS (`BOTX_API_HOST`).

---

## Express и политика

1. В карточке бота «Адрес» = URL **этого** listener на hmk2fa, не хост BotX.
2. Пользователь в Express: `/start` (привязка чата).
3. Политика: ExpressMS = кнопки (`push`); метод пользователя EXPRESSMS. TOTP не переключать.

Проверка: `curl -fsS http://127.0.0.1:8030/health`  
Лог: `podman-compose logs -f express-bot`
