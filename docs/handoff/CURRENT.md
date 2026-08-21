# Handoff — текущее состояние

Обновлять **перед каждым `git push`** (и при смене сессии / незавершёнке). Время — **МСК**.

## Срез

| Поле | Значение |
|------|----------|
| Дата | 2026-08-21 ~17:00 МСК |
| Ветка / коммит | `main` **ceb56e0** |
| Lab | `/root/2fa`, podman-compose |
| Alembic head | **007** |
| UI | **MK 2FA**; hash-вкладки; крупное меню сайдбара |

## Что сделано

- Own → **MK 2FA**; F5-вкладки; **worker-otp**; UI Interros
- **install:** pip `podman-compose` под sudo; `FROM docker.io/...`; **один** образ `localhost/mk2fa-api` на api+workers+beat
- **install:** `PUBLIC_BASE_URL` с IP текущего хоста, не lab `192.168.0.178`
- Форма входа пустая; канон **`admin` / `admin`** сразу после install (правило install-ready)
- **UI:** displayName из AD — кириллица (не `\\u041a`); колонка имя не раздувает таблицу
- **RADIUS:** LDAP bind без schema ALL + timeout; firewalld/ufw 1812/udp в install **и** update
- **RADIUS 403:** токен `/internal/*` из `os.environ`; pydantic env **выше** dotenv; `compose()` export `.env` до interpolate
- **install-ready:** smoke `GET /internal/radius/config`; при 403 — длины/sha256 env vs settings (не секрет)

## Хвосты

- На уже стоящем `/opt/2fa`: `git pull --ff-only` + `sudo ./scripts/update.sh` (не ручной compose/токен)
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
