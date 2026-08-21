# Handoff — текущее состояние

Обновлять **перед каждым `git push`** (и при смене сессии / незавершёнке). Время — **МСК**.

Следующая сессия (основной клиент Cursor): **этот файл + `CHANGELOG.md` верх + `docs/adr/0001-radius-otp-only.md`**. Код на GitHub `main` уже содержит otp_only.

## Срез

| Поле | Значение |
|------|----------|
| Дата | 2026-08-21 ~17:55 МСК |
| GitHub | `https://github.com/MerlKoryAmber/2fa` ветка **`main`** |
| Коммит (docs) | **`2e00155`** (handoff для основного клиента; фича **`bd4097f`** otp_only) |
| Фича HEAD кода | **`bd4097f`** `feat: RADIUS otp_only — TOTP без LDAP, как LinOTP на UAG` |
| Локальный workspace | Windows `C:\cursor\2fa` (этот репозиторий) |
| Сервер | CentOS Stream 9, каталог **`/opt/2fa`**, compose project `2fa_*` |
| Alembic head | **007** (`admins.auth_source`) |
| Вход панели | `admin` / `admin`, форма пустая |
| Автор коммитов | `MerlKory <llevelamoney@gmail.com>` через env, не `git config` |
| Push | только по команде Merl; **не** `git add .`; Windows git: `C:\Program Files\Git\cmd` |

## Живой стенд (не закрыто)

Хост 2FA, firewall **выключен**. NAS VPN: **`172.22.10.231`**. Пользователь **`U1807`**.

1. RADIUS пакет **доходит** (secret ок): был аудит `RADIUS_ERROR` / `NAS: 172.22.10.231` / «gateway не достучался до API».
2. LDAP в панели («Проверить LDAP») — **успех мгновенно**.
3. Архитектура площадки как **LinOTP + VMware UAG**: 1-й фактор на checkpoint/UAG, на RADIUS уходит **только OTP**, не пароль AD.
4. MK 2FA до `bd4097f` всегда делал LDAP bind `User-Password` → bind в AD кодом TOTP → timeout NAS.

**На сервере ещё нужно (человек / следующий агент не делает руками compose):**

```bash
cd /opt/2fa
sudo ./scripts/update.sh
```

Затем панель → **Политика** → «Что приходит на RADIUS» → **«Только OTP — LDAP уже проверил NAS»** → сохранить.

`U1807` должен быть в Пользователях с **подтверждённым TOTP** (импорт LinOTP). Проверка: попытка VPN → Аудит `RADIUS_ACCEPT` причина `otp_only`. `unknown_user` = нет учётки в MK 2FA.

## Что вошло в код (сессия 21.08)

- RADIUS 403: пустой `${INTERNAL_API_TOKEN}` с хоста; pydantic dotenv vs env; httpx **`trust_env=False`** (корпоративный HTTP_PROXY); `.env` → `/run/mk2fa/host.env`
- `update.sh`: `source` **после** pull (`exec --no-pull`); unshallow; smoke с `token_len`
- Gateway не silent-drop NAS; аудит `RADIUS_NAS_DENIED` / `RADIUS_BAD_PACKET` / `RADIUS_ERROR` (`timeout` / `http_*` / `connect`)
- LDAP user bind на первый DC (без service-search на RADIUS)
- **`otp_only`**: `api/app/radius_flow.py`, политика UI `web/app.js`, ADR `docs/adr/0001-radius-otp-only.md`
- Колонка `policies.radius_scheme_preference` с **001**, до этой сессии **не читалась** в flow

## Ключевые файлы

| Зачем | Где |
|-------|-----|
| RADIUS Accept OTP без LDAP | `api/app/radius_flow.py` (`OTP_ONLY_SCHEMES`, `_otp_only`, `find_radius_user`) |
| Политика API | `api/app/routers/admin.py` `PolicyPatch.radius_scheme_preference` |
| UI политики | `web/app.js` radio «Что приходит на RADIUS» |
| Gateway UDP | `radius/server.py` |
| Internal token | `api/app/internal_token.py`, `api/app/routers/radius.py` |
| Install/update | `scripts/update.sh`, `scripts/lib/common.sh` |
| ADR | `docs/adr/0001-radius-otp-only.md` |

## Хвосты

- **Сервер `/opt/2fa`:** `update.sh` + политика `otp_only` + проверка VPN `U1807` (не сделано в этой сессии после пуша `bd4097f`)
- Полный `guid_map.csv` → LinOTP export → `scripts/import_linotp_seeds.sh`
- Fail теста: `test_normalize_bind_user_domain_backslash`
- Backlog: Telegram `/start`, Discovery NAS, policy OU; вариант B (отдельные worker на канал)
- `PLAN_MK_2FA_SYSTEM_RU.md` §1 всё ещё канон challenge; otp_only — ADR 0001 (доп. схема для UAG)

## Не делать без команды Merl

- Force-push; `compose down -v` на не-lab
- Apply миграции токенов / коммит `.env` / дампа LinOTP
- Менять git config
- Руками править compose/токен на сервере (install-ready)

## Следующий агент — старт

1. `git pull --ff-only` в `C:\cursor\2fa` и на `/opt/2fa` если код там отстаёт
2. Прочитать этот файл + CHANGELOG верх + ADR 0001
3. Если VPN ещё timeout: на сервере update + политика otp_only; смотреть Аудит, не выдумывать LDAP
4. Стиль: caveman RU, Conventional Commits, время МСК
5. Не `git add .`
