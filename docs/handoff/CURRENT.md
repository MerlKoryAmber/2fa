# Handoff — текущее состояние

Обновлять **перед каждым `git push`** (и при смене сессии / незавершёнке). Время — **МСК**.

## Срез

| Поле | Значение |
|------|----------|
| Дата | 2026-08-21 ~23:13 МСК |
| GitHub | `main` @ **`059ec66`** (политики per client + сводка MVP) |
| Фича HEAD кода | otp_only + policy scope + SMTP + dashboard MVP |
| Локальный workspace | `/root/2fa` (lab) |
| Сервер | CentOS Stream 9, **`/opt/2fa`** |
| Alembic head | **007** |
| LinOTP → тест | **все пользователи/токены импортированы** (подтверждено Merl 21.08 ~21:13 МСК) |
| Вход панели | `admin` / `admin`, форма пустая |
| Push | только по команде Merl; **не** `git add .` |

## Живой стенд — ПРИНЯТО (21.08 ~20:49 МСК)

Цепочка: **HCPGW-CL** (`172.22.1.167`) → **NPS proxy** (`172.22.10.231`, policy `u1807`) → **MK 2FA** (`172.22.10.140`).

- Политика **otp_only**; пользователь **U1807** + TOTP из LinOTP (пилот); **полный импорт LinOTP — да**
- **Верный OTP** → пускает (Accept)
- **Неверный OTP** → отбивает (Reject), без NPS **117**

Грабли по пути (уже в коде): ACL `parse_allowed_clients`; Message-Authenticator; `network_mode: host`; эхо **Proxy-State** + MA первым attr.

## Что вошло в код (сессия 21.08)

- RADIUS install-ready / 403 / httpx `trust_env=False` / host.env
- **otp_only** (ADR 0001)
- host-network radius; Proxy-State; MA first
- **SMTP:** `POST /api/settings/test-smtp` + UI «Отправить тест» до save; STARTTLS при выкл. SSL
- **UI:** смена пароля — повтор ввода + успех без браузерного `alert`
- **Политика per client:** `Policy.scope` + `resolve_policy(nas_ip)` (ADR 0002); UI вкладки + черновик; Default
- **Сводка MVP:** `/api/stats` → статус, 2FA, RADIUS 24ч, лента (новые сверху)
- Правила: no-browser-dialogs, no-stand-ips-in-ui

## Ключевые файлы

| Зачем | Где |
|-------|-----|
| otp_only | `api/app/radius_flow.py`, ADR `docs/adr/0001-radius-otp-only.md` |
| Gateway UDP | `radius/server.py`, `radius/dictionary` |
| Compose host net | `docker-compose.yml` (`radius.network_mode: host`) |
| SMTP тест | `api/app/mail_service.py`, `api/app/routers/settings.py`, вкладка SMTP в `web/app.js` |
| Policy per NAS | `api/app/policy_resolve.py`, ADR `docs/adr/0002-policy-per-radius-client.md` |
| Сводка | `api/app/dashboard.py`, вкладка «Сводка» в `web/` |

## Как проверять политику per client

См. ADR 0002 §«Как проверять». Кратко: в панели **Политика → Проверка выбора** IP NPS — без смены конфига; VPN регресс Accept/Reject. Две политики — только когда нужен второй клиент.

## Хвосты

- Backlog: Telegram `/start`, Discovery NAS, policy OU; вариант B (отдельные worker на канал)
- Cutover: пилоты ещё юзеров / чеклист вывода LinOTP из боя (когда скажет Merl)
- Опционально: конфиг LinOTP RADIUS для сверки

**Уже на стенде:** `allowed_clients` заполнен; полный импорт LinOTP; VPN otp_only принят.  
**Стабильность:** fail `test_normalize_bind_user_domain_backslash` — исправлен (`DOMAIN\\user`).

## Не делать без команды Merl

- Force-push; `compose down -v` на не-lab
- Apply миграции токенов / коммит `.env` / дампа LinOTP
- Менять git config

## Следующий агент — старт

1. `git pull --ff-only`
2. Handoff + CHANGELOG верх
3. Стенд VPN U1807 уже зелёный — не чинить RADIUS «с нуля»
4. Caveman RU; не `git add .`
