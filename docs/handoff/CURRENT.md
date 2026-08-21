# Handoff — текущее состояние

Обновлять **перед каждым `git push`** (и при смене сессии / незавершёнке). Время — **МСК**.

## Срез

| Поле | Значение |
|------|----------|
| Дата | 2026-08-21 ~17:20 МСК |
| Ветка / коммит | `main` **b8079bb** |
| Lab | `/opt/2fa` (этот сервер), podman-compose |
| Alembic head | **007** |
| UI | **MK 2FA**; hash-вкладки; крупное меню сайдбара |

## Что сделано

- Own → **MK 2FA**; F5-вкладки; **worker-otp**; UI Interros
- **install:** pip `podman-compose` под sudo; `FROM docker.io/...`; **один** образ `localhost/mk2fa-api` на api+workers+beat
- **install:** `PUBLIC_BASE_URL` с IP текущего хоста, не lab `192.168.0.178`; clone **без** `--depth 1`
- Форма входа пустая; канон **`admin` / `admin`** сразу после install (правило install-ready)
- **UI:** displayName из AD — кириллица (не `\\u041a`); колонка имя не раздувает таблицу
- **RADIUS:** LDAP bind без schema ALL + timeout; firewalld/ufw 1812/udp в install **и** update
- **RADIUS 403:** токен из `/run/mk2fa/host.env`; httpx `trust_env=False` (не корпоративный HTTP_PROXY); 403 тело `got_len`/`exp_len`
- **update.sh:** unshallow + не глотать fetch + `exec --no-pull` после pull

## Хвосты

- На уже стоящем `/opt/2fa`: `sudo ./scripts/update.sh` (уже с re-exec)
- LDAP/RADIUS secret/NAS allowlist — настройки площадки в панели, не код
- Полный `guid_map.csv` → export → import на тест (`scripts/import_linotp_seeds.sh`, не python на хосте)
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
