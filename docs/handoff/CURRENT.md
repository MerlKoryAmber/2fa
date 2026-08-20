# Handoff — текущее состояние

Обновлять **перед каждым `git push`** (и при смене сессии / незавершёнке). Время — **МСК**.

## Срез

| Поле | Значение |
|------|----------|
| Дата | 2026-08-20 ~15:05 МСК |
| Ветка / коммит | `main` — docs `push-docs` + CHANGELOG; feature tip `280752f` |
| Lab | `/root/2fa`, podman-compose |
| Alembic head | **007** (`admins.auth_source`) |
| Health | `curl -sk https://127.0.0.1/health` |

## Что сделано (последний крупный кусок)

- RBAC панели: `admin` / `operator` / `auditor` (миграция 006)
- Вход: локальный admin; оператор/аудитор — AD + группы из **Настройки → Доступ** (007)
- Mock LDAP убран
- `scripts/install.sh` / `update.sh` / `uninstall.sh`
- UI: порядок вкладки Доступ; легенды `settings-section` без разреза рамкой
- Docs-процесс: `CHANGELOG.md` + `docs/handoff/CURRENT.md` + правило `.cursor/rules/push-docs.mdc` (писать перед каждым push)
## Хвосты (не закрыты)

- LinOTP-миграция — **отложена**, чеклист `LINOTP_MIGRATION_TODO.md`
- Известный fail теста: `test_normalize_bind_user_domain_backslash` (не блокер head)
- Telegram bot `/start`, Discovery NAS, policy по OU/группе — backlog README

## Не делать без команды Merl

- Push с force; prod-like down с `-v`
- Возобновлять LinOTP-миграцию
- Коммит секретов / `.env`

## Следующий агент — старт

1. Прочитать этот файл + `CHANGELOG.md` (верх) + `README.md`
2. `git fetch` + `git status` + сверка alembic head в контейнере
3. Не `git add .`; не принимать задачу за пользователя
