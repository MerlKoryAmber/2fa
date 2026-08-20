# Own 2FA

Собственная MFA: LDAP 1-й фактор; 2-й — TOTP, ExpressMS или **Telegram** (по плану); RADIUS Access-Challenge для любого совместимого NAS (не только UAG).

План: `PLAN_OWN_2FA_SYSTEM_RU.md`.

## Состав

| Сервис | Порт | Назначение |
|--------|------|------------|
| web | 80 | Админка |
| api | 8000 | FastAPI |
| worker | — | Celery, отправка ExpressMS |
| db | — | PostgreSQL 16 |
| redis | — | брокер очереди |
| radius | 1812/udp | RADIUS gateway (challenge-response) |

На хосте: Podman + podman-compose (не Docker Engine).

## Запуск

```bash
cd /root/2fa
podman-compose up --build -d
make verify    # локальные тесты (без podman)
```

Админка: `https://<IP>/` (self-signed, браузер предупредит)  
HTTP `:80` редиректит на HTTPS.  
API напрямую: `http://<IP>:8000/health`

Демо RADIUS-пользователь (LDAP mock):

- username `demo`
- password `demo`
- TOTP secret `JBSWY3DPEHPK3PXP` (можно добавить в Google Authenticator вручную)
- RADIUS shared secret `testing123`

Проверка с хоста:

```bash
# шаг 1 — пароль AD, ожидается Access-Challenge
echo User-Name=demo,User-Password=demo | radclient -x 127.0.0.1:1812 auth testing123

# шаг 2 — OTP в User-Password, тот же State
# удобнее scripts/radius_demo.py
```

## Переход на настоящий AD

Через вкладку **Настройки** в админке или bootstrap в `.env`:

- **DC** — один или несколько контроллеров (host + port), при ошибке — следующий в списке
- **Bind user** — `CORP\svc_mfa`, `svc_mfa@corp.local` или `svc_mfa` (UPN достроится из Base DN)
- **SSL** — галка LDAPS (636) / LDAP (389)
- **Base DN** — `DC=corp,DC=local`

Legacy `LDAP_URL=ldaps://dc...` по-прежнему читается как один DC.

## ExpressMS и Telegram

Настраиваются во вкладке **Настройки**. В lab по умолчанию dry-run: код уходит в лог worker (без значения OTP).

```
EXPRESSMS_DRY_RUN=true
TELEGRAM_DRY_RUN=true
```

RADIUS shared secret тоже из панели; gateway подтягивает его с `/internal/radius/config` (кэш 60 с).

**Разрешённые NAS** — textarea в настройках RADIUS (IP или CIDR, по строке). Пусто = любой источник.

Дизайн админки: `docs/design/DESIGN.md` (Linear из [awesome-claude-design](https://github.com/VoltAgent/awesome-claude-design)).

## Безопасность лаборатории

Секреты в `.env` — учебные, смените перед любой сетью кроме изолированной lab.  
Rate-limit: `RATE_LIMIT_RADIUS_PER_MINUTE`, `RATE_LIMIT_LOGIN_PER_MINUTE`.  
Миграции: `podman exec 2fa_api_1 alembic upgrade head` (на старте — автоматически).
