# Prod-safe deploy — общие правила (backlog)

_Зафиксировано: 2026-08-22 ~12:18 МСК. Применимо к: Express/BotX, external integration API, любым правкам `radius_flow`._

## Инвариант

В prod работает **VPN otp_only + TOTP**. Ломать проверку TOTP нельзя. **Рестарт** сервисов (`api`, `radius`, `worker-*`, новые контейнеры) — допустим.

Регресс-эталон: верный OTP → Accept, неверный → Reject (без NPS 117).

## Линии защиты (по возрастанию «цены»)

| Уровень | Что | Когда |
|---------|-----|--------|
| **1. Lab `/root/2fa`** | pytest, `curl /health`, deploy-lab, RADIUS smoke | Каждый deploy api/radius |
| **2. Изоляция в коде** | Отдельные ветки `otp_method`, feature flags, отдельные контейнеры (`integration`, `express-webhook`) | При проектировании фичи |
| **3. Клон prod-сервера** | Snapshot/клон VM с полным стеком + NPS-тест или radclient | **Только критичные изменения**, когда lab не покрывает |

## Клон prod (Merl)

**Доступно:** при критичных изменениях можно **клонировать текущий prod-сервер** и гонять регресс (TOTP, RADIUS, enroll) на клоне до выката на бой.

**Ограничение:** пользоваться **редко**, только когда реально нужно — задействует **другую команду** (инфра/ виртуализация / сеть). Не дефолтный pipeline агента.

### Когда клон оправдан

- Правки **`radius_flow.py`**, меняющие общий путь otp_only.
- Смена схемы RADIUS (challenge ↔ otp_only) на живой конфигурации NPS.
- Крупный cutover (Express push, смена политики для всех VPN-клиентов).
- Lab не повторяет prod (другой NPS, другой `allowed_clients`, другой alembic/data).

### Когда клон не нужен

- Новый контейнер (`integration`, webhook) **без** touch RADIUS path; TOTP smoke на lab + короткий prod smoke после deploy.
- Только UI / SMTP test / dashboard / integration API за feature flag OFF.
- Только `worker-otp` / Express dry-run.
- Docs, скрипты без rebuild api/radius.

### Чеклист на клоне (минимум)

1. `curl -sk https://127.0.0.1/health` — ok.
2. RADIUS: тестовый user **TOTP**, otp_only — Accept/Reject.
3. Enroll: ссылка открывается, LDAP + QR (если трогали enroll).
4. Новая фича — только если в scope deploy.

После зелёного клона — выкат на prod по окну + тот же smoke на бою.

## Связанные backlog

- [`EXPRESS_INTEGRATION.md`](EXPRESS_INTEGRATION.md) — Express/BotX, фазы OTP → push.
- [`EXTERNAL_INTEGRATION_API.md`](EXTERNAL_INTEGRATION_API.md) — invite API, контейнер `integration`.

## Для ADR / handoff

При реализации критичной фичи в ADR указать:

- затронут ли **TOTP path**;
- достаточно ли lab + pytest;
- нужен ли **клон prod** (да/нет + причина);
- если да — **какая команда** и что просить (clone VM, отдельный IP, не трогать боевой NPS без согласования).
