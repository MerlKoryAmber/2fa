# ADR 0002 — Политика RADIUS по клиенту (scope)

- Дата: 2026-08-21 МСК
- Статус: принято

## Контекст

Одна глобальная политика: VPN (NPS → otp_only) и другие NAS (LDAP+challenge) не могут сосуществовать.  
`Policy.scope` уже в схеме (`*`), в выборе не использовался. `nas_ip` в Access-Request = UDP peer.

## Решение

- Несколько строк `policies`; `scope` = `*` | IP | CIDR (список через `,`/`;`/newline).
- `resolve_policy(nas_ip)` — максимальная специфичность (точный IP > prefixlen CIDR > `*`).
- RADIUS (`_start` / `_complete`) — только `resolve_policy`.
- Enroll / TTL приглашений / confirm TOTP в админке — `default_policy` (первая с `scope` содержащим `*`).
- Allowlist `radius.allowed_clients` без изменений (отдельно от политики).

## Совместимость

Одна политика с `scope=*` — поведение как до ADR: все клиенты на неё.  
Существующий стенд VPN не ломается, пока не добавлена более узкая строка.

## Как проверять (не «не трогай вообще»)

**Безопасно, без смены VPN-поведения**

1. В панели **Политика** оставь единственную запись `*` как есть (на стенде обычно `otp_only`).
2. Блок «Проверка выбора»: введи IP своего RADIUS-клиента → «Какая политика» — должна показать эту же `*`.
3. Или API: `GET /api/policies/resolve-preview?nas_ip=<IP>` (с JWT админа).
4. Регресс VPN: один Accept/Reject пилотом — как до фичи.

**Проверка «две политики» (lab или окно обслуживания)**

1. `*` → `challenge` (или оставь как fallback).
2. Добавь политику scope=IP клиента, режим **только OTP**.
3. Preview для этого IP → узкая; для другого → `*`.
4. VPN с этим клиентом → otp_only; другой RADIUS-клиент → challenge.

Пока второй клиент не нужен — достаточно шагов 1–4 блока «безопасно».

## Отвергнуто

- Только map scheme в settings (вариант B) — не покрывает TTL/методы per client.
- Таблица `radius_clients` + secret (вариант C) — следующий этап.
- Match по NAS-IP-Address attr за NPS — **выбрано, отложено** (Merl 2026-08-23): вариант 1; причины — CP otp_only, UAG challenge, failover 2FA через прокси. См. `docs/backlog/RADIUS_POLICY_SOURCE_IP.md`.
