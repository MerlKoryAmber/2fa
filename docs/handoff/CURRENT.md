# Handoff — текущее состояние

Обновлять **перед каждым `git push`** (и при смене сессии / незавершёнке). Время — **МСК**.

Следующая сессия (основной клиент Cursor): **этот файл + `CHANGELOG.md` верх + `docs/adr/0001-radius-otp-only.md`**. Код на GitHub `main` уже содержит otp_only.

## Срез

| Поле | Значение |
|------|----------|
| Дата | 2026-08-21 ~20:38 МСК |
| GitHub | `main` @ **`01c8d1e`** (RADIUS network_mode: host) |
| Фича HEAD кода | host-network RADIUS + MA + ACL + otp_only |
| Локальный workspace | `/root/2fa` (lab) |
| Сервер | CentOS Stream 9, **`/opt/2fa`** |
| Alembic head | **007** |
| LinOTP → тест | **импорт утром 21.08** |

| Вход панели | `admin` / `admin`, форма пустая |
| Автор коммитов | `MerlKory <llevelamoney@gmail.com>` через env, не `git config` |
| Push | только по команде Merl; **не** `git add .`; Windows git: `C:\Program Files\Git\cmd` |

## Живой стенд (не закрыто)

Хост 2FA, firewall **выключен**. NAS VPN: **`172.22.10.231`**. Пользователь **`U1807`**.

1. RADIUS пакет **доходит** (secret ок): был аудит `RADIUS_ERROR` / `NAS: 172.22.10.231` / «gateway не достучался до API».
2. LDAP в панели («Проверить LDAP») — **успех мгновенно**.
3. Архитектура площадки как **LinOTP + VMware UAG**: 1-й фактор на checkpoint/UAG, на RADIUS уходит **только OTP**, не пароль AD.
4. MK 2FA до `bd4097f` всегда делал LDAP bind `User-Password` → bind в AD кодом TOTP → timeout NAS.

**Симптом:** аудит OTP_FAIL + `reply_len=51`, NPS **117** did not respond — UDP DNAT. Фикс: `network_mode: host` для radius.

**На сервере после push:**

```bash
cd /opt/2fa
sudo ./scripts/update.sh
podman logs --tail 5 2fa_radius_1   # listening; NetworkMode=host
```

Политика **otp_only**. Проверка: неверный OTP → NPS не 117; верный → Accept.

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

- **Сервер `/opt/2fa`:** `update.sh` (host-network radius) → VPN: неверный OTP без 117; верный → Accept
- Fail теста: `test_normalize_bind_user_domain_backslash`
- Backlog: Telegram `/start`, Discovery NAS, policy OU; вариант B (отдельные worker на канал)
- `PLAN_MK_2FA_SYSTEM_RU.md` §1 канон challenge; otp_only — ADR 0001

## Не делать без команды Merl

- Force-push; `compose down -v` на не-lab
- Apply миграции токенов / коммит `.env` / дампа LinOTP
- Менять git config
- Руками править compose/токен на сервере (install-ready)

## Следующий агент — старт

1. `git pull --ff-only` в `C:\cursor\2fa` и на `/opt/2fa` если код там отстаёт
2. Прочитать этот файл + CHANGELOG верх + ADR 0001
3. После update фикса ACL: VPN + Аудит; не копать LDAP при otp_only
4. Стиль: caveman RU, Conventional Commits, время МСК
5. Не `git add .`
