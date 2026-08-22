# RADIUS: IP для политики без NPS (или с другим прокси)

_Зафиксировано: 2026-08-23 ~00:50 МСК. Связь: ADR 0002 («Match по NAS-IP-Address за NPS — фаза 2»), гибкие политики после Express push._

## Цель (Merl)

Заменить текущий **проксирующий NPS** на что-то, что доставит на MK 2FA RADIUS **IP настоящего NAS** (Check Point / UAG / …), чтобы `resolve_policy(nas_ip)` / будущие гибкие политики применялись **по этому IP**, а не по IP прокси.

Сейчас: `radius/server.py` → `nas_ip = addr[0]` (UDP peer). За NPS peer = NPS → все VPN на одну политику по peer.

## Решение (отложено) — **вариант 1**

_Зафиксировано Merl 2026-08-23 ~00:52 МСК: в дальнейшие доработки, не сейчас._

**Прокси остаётся** (NPS или замена на FreeRADIUS/иной — отдельно).  
**MK 2FA** для выбора политики берёт IP настоящего NAS из атрибута (**`NAS-IP-Address`** / согласованный attr), не из UDP peer.

| Слой | Ключ |
|------|------|
| `allowed_clients` | UDP peer = **IP прокси** |
| `resolve_policy` / гибкие политики | **`NAS-IP-Address`** (fallback: peer, если attr нет) |

### Почему не «убрать прокси» и не spoof

| Причина | Смысл |
|---------|--------|
| **Check Point → otp_only** | 1-й фактор / схема на стороне CP; на RADIUS часто только OTP. Прокси + разные политики per NAS IP позволяют держать CP на otp_only, не ломая общий вход. |
| **UAG → Access-Challenge** | UAG умеет нормальный challenge (2-е окно). Нужна **другая** политика/схема, чем у CP — ключ = IP UAG из attr за одним прокси. |
| **Переключение 2FA на резерв** | Прокси может перенаправить второй фактор на **резервный** RADIUS/MFA с минимальными потерями (failover / смена backend), без перенастройки каждого NAS на новый IP. Прямой NAS→MK это усложняет. |

Spoof UDP source — не планируем.

Прямое подключение NAS→MK (вариант 0) — не выбираем как основной путь по причинам выше; lab/smoke напрямую по-прежнему ок.

---

## Что считать «IP источника»

| IP | Обычно | Для политики MK |
|----|--------|-----------------|
| UDP source пакета | Кто прислал datagram | Сейчас единственный ключ |
| `NAS-IP-Address` (attr 4) | IP шлюза/VPN, как его записал NAS или прокси | **Нужный** ключ за прокси |
| IP конечного пользователя | Часто Calling-Station-Id / Framed-IP | Не для policy scope NAS |

Нужен IP **шлюза (NAS)**, не телефона пользователя.

## Варианты (от простого к сложному)

### 0. Убрать прокси — NAS → MK 2FA напрямую

Check Point / UAG / … шлют Access-Request **сразу** на `radius` MK 2FA.

- UDP source = IP NAS → политика работает **как есть**.
- Минусы: один shared secret / allowlist на каждого NAS; нет NPS-политик Windows; если NPS делал AD — AD остаётся на NAS (`otp_only`) или на MK (`challenge`).

**Если NPS нужен только как «пересылка на MFA» — это лучший путь.**

### 1. Оставить любой прокси, научить MK 2FA читать `NAS-IP-Address` _(фаза 2 ADR 0002)_

Прокси (NPS / FreeRADIUS / свой) форвардит; UDP peer = прокси.

MK 2FA:

1. `allowed_clients` — IP **прокси** (как сейчас NPS).
2. Для `resolve_policy` брать **`NAS-IP-Address`** (если валиден), иначе fallback на UDP peer.
3. Опционально: attr от прокси «original client» если NAS-IP пустой/врёт.

Плюсы: NPS можно не трогать или заменить на лёгкий proxy без spoof.  
Минусы: доверять attr (прокси не должен давать клиенту подставить чужой NAS-IP без контроля).

**Это закрывает цель политик без «сохранить IP в UDP-заголовке».**

### 2. Заменить NPS на FreeRADIUS (или radsecproxy) как proxy

Типовой стек: NAS → FreeRADIUS proxy → MK 2FA.

- FreeRADIUS умеет proxy, `Proxy-State`, rewrite attributes.
- UDP source на MK = FreeRADIUS (не NAS), если не transparent.
- Чтобы политика видела NAS: либо **вариант 1** в MK, либо на proxy выставить/пробросить `NAS-IP-Address` = `%{Packet-Src-IP-Address}` первого хопа.

Замена NPS имеет смысл, если нужны: Linux, проще отладка, меньше Windows, единый secret map — **не** потому что «UDP IP сохранится сам».

### 3. Transparent / spoof source IP

Прокси шлёт на MK пакет с source = IP NAS.

- Теоретически `addr[0]` = NAS без правок MK.
- Практически: return path, uRPF, хрупко (см. прошлый разбор).
- **Не рекомендуем** как основу замены NPS.

## Рекомендация под MK 2FA

| Приоритет | Действие | Статус |
|-----------|----------|--------|
| **Выбрано (отложено)** | **Вариант 1** — прокси + политика по `NAS-IP-Address` | Дальнейшие доработки |
| Альтернатива | Прямой NAS→MK | Не основной (теряем failover 2FA / единую точку) |
| Не делать | Spoof UDP | — |

При реализации — после или рядом с гибкими политиками post-Express; TOTP otp_only за CP не ломать.

## TODO (когда снимем с отложенного)

1. Парсинг `NAS-IP-Address` в `radius/server.py`; в API — `nas_ip` для policy = attr (настройка: `policy_ip_from=attr|peer`).
2. Trust: attr только если peer ∈ allowlist прокси.
3. Preview политики в UI — по IP NAS (attr), подсказка про прокси.
4. Проверить, что NPS/будущий proxy реально пробрасывает/заполняет NAS-IP шлюза (CP vs UAG).
5. ADR дополнение к 0002 / новый короткий ADR.
6. Регресс: CP otp_only + preview разных scope для IP CP и IP UAG за одним peer.

## Не делать вслепую

- Ломать текущий otp_only VPN, пока ключ политики не проверен preview + smoke.
- Доверять `NAS-IP-Address` с интернета без allowlist peer.

## Связь с Express / гибкими политиками

После Express push политики станут гибче (fallback, timeouts per NAS). Ключ scope всё равно должен быть **IP настоящего NAS** — этот файл = как его получить, убрав или оставив прокси.
