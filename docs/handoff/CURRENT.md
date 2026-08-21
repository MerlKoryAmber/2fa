# Handoff — текущее состояние

Обновлять **перед каждым `git push`** (и при смене сессии / незавершёнке). Время — **МСК**.

## Срез

| Поле | Значение |
|------|----------|
| Дата | 2026-08-21 ~16:20 МСК |
| Ветка / коммит | локально (кнопки в ряд) поверх `5afaaf0` |
| Lab | `/root/2fa`, podman-compose |
| Alembic head | **007** |
| UI | **MK 2FA**; hash-вкладки; крупное меню сайдбара |

## Что сделано

- Own → **MK 2FA**; F5-вкладки; **worker-otp**; UI Interros
- **install:** pip `podman-compose` под sudo; `FROM docker.io/...`; **один** образ `localhost/mk2fa-api` на api+workers+beat
- **install:** `PUBLIC_BASE_URL` с IP текущего хоста, не lab `192.168.0.178`
- Форма входа пустая; канон **`admin` / `admin`** сразу после install (правило install-ready)
- **UI:** displayName из AD — кириллица (не `\\u041a`); колонка имя не раздувает таблицу

## Хвосты

- Повторить `sudo ./scripts/install.sh` на свежем сервере (после этих правок)
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
