# NPS reason 117 при Express push (TOTP при этом работает)

_2026-08-31 МСК. Лаба: HCPGW → HNPS (`172.22.10.231`) → MK2FA._

## Симптом

- Политика `otp_only` + `express_push`, в логе MK2FA: `decision=accept`, `api_s≈6`
- На HNPS: **reason 117** — «The remote RADIUS server did not respond»
- Сценарий **TOTP** на том же NAS — **Accept** (ответ < 1 с)

## Причина

У **Remote RADIUS Server Group** в NPS поле **Connection timeout** по умолчанию **5 секунд**.

Push-hold ждёт Approve дольше (типично 5–30 с). NPS обрывает ожидание **до** Access-Accept от MK2FA → 117. Accept в логе MK2FA приходит **после** таймаута прокси — для VPN уже поздно.

TOTP укладывается в 5 с → 117 не видно.

## Исправление на HNPS (Windows)

1. **Server Manager** → **Tools** → **Network Policy Server**
2. **RADIUS Servers** → **Remote RADIUS Server Groups**
3. Группа с MK2FA (IP `172.22.10.140` или как настроено) → **Properties**
4. Вкладка **Load Balancing** (или **Advanced** / таймауты передачи)
5. **Connection timeout**: **120** секунд (минимум `push_wait_seconds` + 30; при `push_wait_seconds=60` → **90–120**)
6. **Maximum number of retransmissions**: 2–3 (по желанию; MK2FA дедуплирует state на ретраях)
7. OK → перезапуск NPS не обязателен, но надёжнее: `Restart-Service RemoteAccess`

Проверка: VPN → Approve в Express **в течение 10 с** — без 117; в radius `api_s` может быть > 5, если таймаут поднят.

## Сверка с логами MK2FA

```bash
./scripts/diagnose_radius_push.sh U1807
```

- `api_s=5.97` + 117 на NPS → почти наверняка **Connection timeout = 5**
- После правки NPS: тот же `api_s`, но VPN **пускает**

## Не путать

| Проблема | Где чинить |
|----------|------------|
| Ответ UDP не с IP хоста | MK2FA `network_mode: host` для radius |
| Нет Proxy-State в ответе | код radius (уже есть) |
| Ретраи NPS → второй push | MK2FA дедуп `EXPRESS_PUSH_REUSE` |
| Hold > **5 с**, TOTP ок | **HNPS Connection timeout** |

MK2FA кодом таймаут NPS **не увеличить** — только настройка HNPS или Approve быстрее 5 с (ненадёжно).
