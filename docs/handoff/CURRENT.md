# Handoff — текущее состояние

Обновлять **перед каждым `git push`** (и при смене сессии / незавершёнке). Время — **МСК**.

## Срез

| Поле | Значение |
|------|----------|
| Дата | 2026-08-20 ~22:50 МСК |
| Ветка / коммит | `main` — перед push: `migration/` tools |
| Lab | `/root/2fa`, podman-compose |
| Alembic head | **007** |
| Миграция LinOTP | **В РАБОТЕ** B; инструменты в `migration/`; ждём полный guid_map |

## Что сделано

- RBAC / AD-вход / install-скрипты / легенды настроек (см. CHANGELOG 2026-08-20)
- Старт LinOTP B: площадка `/root/linotp-migrate/`, чеклист в `LINOTP_MIGRATION_TODO.md`
- Агент **без** живого LDAP; Merl — бэкап + AD map + тест-приёмка

## Хвосты

- **Сейчас:** полный `guid_map.csv` → `export_seeds.py` → перенос CSV на тест → `import_seeds.py` (dry-run / `--apply`)
- Инструменты: `migration/` (`export_seeds.py` / `import_seeds.py`)
- Decrypt подтверждён (U2008)
- Fail теста: `test_normalize_bind_user_domain_backslash`
- Backlog: Telegram `/start`, Discovery NAS, policy OU

## Не делать без команды Merl

- Force-push; `compose down -v` на не-lab
- Apply миграции токенов в prod
- Коммит секретов / `.env` / дампа LinOTP

## Следующий агент — старт

1. `LINOTP_MIGRATION_TODO.md` + `docs/agent_reports/linotp-migrate/REPORT.md`
2. `ls /root/linotp-migrate/incoming/` — нужен `guid_map.csv`
3. Не `git add .`