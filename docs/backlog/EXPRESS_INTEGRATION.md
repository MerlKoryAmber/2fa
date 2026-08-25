# Express (eXpress) / BotX — backlog интеграции 2FA

_Зафиксировано: 2026-08-22 ~12:00 МСК. Обновлено: **2026-08-25 ~11:10 МСК**. Статус: **код бота в репо** (`express-bot/`). Деплой на hmk2fa.

## Контекст у Merl

- В компании **локальная установка eXpress** + **свой BotX** (on-prem, не облако).
- MK 2FA + процесс бота: **`hmk2fa.interros.ru`**, listener `:8030` («Адрес бота» в Express). CTS/API **отправки** — `BOTX_API_HOST` (настраиваемое). Не ставить бота на хост платформы BotX.
- Сайт продукта: https://express.ms/
- Цель (потенциальная): OTP и/или **push с кнопками** Approve/Deny через корпоративный мессенджер вместо/рядом с TOTP.

## Отбой по другим «пушам» (кратко, чтобы не путать)

| Канал | Push Approve/Deny? | В MK 2FA |
|-------|-------------------|----------|
| **Яндекс ID (Ключ)** | Нет, только TOTP | Уже через канал `TOTP` |
| **Google Authenticator** | Нет, только TOTP | Уже через канал `TOTP` |
| **ExpressMS** | Да, **через BotX + бот + webhook** | Заглушка, см. ниже |

Push «нажал ОК на телефоне» ≠ TOTP-приложение. Нужен мессенджер/ MFA-платформа с API обратного вызова.

---

## Что умеет eXpress (официально)

Интеграция — **BotX API** + зарегистрированный **чат-бот** в админке Express.

Документация:

- [Руководство разработчика](https://docs.express.ms/chatbots/developer-guide/)
- [Notifications API v4](https://docs.express.ms/chatbots/developer-guide/api/botx-api/notifications-api/)
- [Примеры (кнопки, silent)](https://docs.express.ms/chatbots/developer-guide/development-and-debugging/examples/)
- [Chats API](https://docs.express.ms/chatbots/developer-guide/api/botx-api/chats-api/)
- FAQ: [Боты и SmartApps](https://express.ms/faq/bots-and-smartapps/)

### Кнопки в сообщениях — **да**

Два типа:

| Тип | Где | Заметка |
|-----|-----|---------|
| **`bubble`** | Под текстом | Ближе всего к «inline» |
| **`keyboard`** | Клавиатура | Сворачивается после нажатия |

Отправка: `POST {botx}/api/v4/botx/notifications/direct`, Bearer-токен бота.

При нажатии в бота уходит **команда** (`command`) + JSON **`data`** (на кнопке) + **`metadata`** (на всё сообщение).  
Для Approve/Deny без мусора в чате: **`opts.silent: true`** на кнопке.

Обработка нажатия: **Bot API webhook** на наш HTTPS (URL в карточке бота). Без webhook MK 2FA ответ не получит.

### On-prem

Локальный Express + свой BotX **не меняет** формат API — только **base URL** и токены. Данные не уходят во внешнее облако Express.

---

## Что сейчас в MK 2FA (lab)

### Модель пользователя

```text
users.expressms_id  — String(256), nullable
```

Семантика сейчас: **произвольная строка**, админ/enroll вводит «логин или ID в ExpressMS» вручную.

Связь с AD: основной ключ `ad_username`; для lookup в eXpress потенциально **`ldap_email`** (уже есть после LDAP sync).

Файлы: `api/app/models.py`, `web/index.html` (`#ue-expressms`), `web/enroll.js`, `api/app/routers/admin.py`, `api/app/routers/public_enroll.py`.

### Worker (заглушка, не BotX)

`api/app/tasks.py` → `send_expressms_otp`:

```json
POST {expressms_api_url}
Authorization: Bearer {token}
{"to": "<expressms_id>", "text": "OTP: 123456"}
```

Так BotX **не работает**. Нужны `group_chat_id`, структура `notification`, при кнопках — webhook.

### RADIUS

`api/app/radius_flow.py`: при `otp_method=EXPRESSMS` генерируется numeric OTP, Celery шлёт в ExpressMS (dry-run в lab).

**Живой стенд VPN:** политика **otp_only** (NPS уже проверил AD, `User-Password` = OTP). Push с кнопками **не заменяет** ввод цифр на NAS без смены RADIUS-сценария (нужен pending challenge + async ответ или Access-Challenge).

### Настройки панели

Вкладка ExpressMS: dry-run, API URL, token (`api/app/settings_service.py`, `web/app.js`).

---

## «Смена модели пользователя» — что имелось в виду

Не переписывание таблицы `users`, а **уточнение привязки AD ↔ eXpress**:

| Сейчас | Нужно BotX |
|--------|------------|
| `expressms_id` = любая строка | **`user_huid`** (UUID) и/или **`group_chat_id`** (UUID чата) |
| Поле `to` в JSON | `group_chat_id` + `notification.body` (+ `bubble`/`keyboard`) |
| Ручной ввод в enroll | Скорее lookup по **email** или автопривязка через бота |

### Варианты реализации (решить после доки Merl)

**A — минимальный (часто хватит)**  
- БД без миграции (или только переименование подписи в UI).  
- При отправке: `ldap_email` → BotX `POST /api/v3/botx/users/by_email` → huid → `GET /api/v1/botx/chats/personal?user_huid=…` → send.  
- Убрать ручной «ID в ExpressMS» из enroll.

**B — кэш в БД**  
- Колонки `express_huid`, опционально `express_chat_id` (alembic).  
- Первый lookup/enroll заполняет, дальше меньше вызовов API.

**C — одно поле, но осознанно**  
- Хранить huid/chat_id в `expressms_id`, подпись в UI. Хуже UX, чем A.

### Что ещё понадобится (не User)

| Слой | Изменение |
|------|-----------|
| Settings | Base URL **вашего** BotX, токен бота, опционально bot_id, callback URL |
| Worker | BotX `notifications/direct` JSON |
| API | Webhook endpoint для Bot API (нажатия кнопок) |
| Enroll | Привязка eXpress (email / команда боту / deep link) |
| RADIUS | Для push: pending challenge в Redis, не только otp_only |

---

## Сценарии 2FA через Express (на выбор позже)

1. **OTP текстом** — только `notification.body`, кнопки не нужны. Проще всего.
2. **Push Approve/Deny** — `bubble` + silent + webhook + pending challenge; NAS должен ждать второй шаг (не текущий otp_only на VPN без доработки).

---

## Деплой и изоляция (prod TOTP нельзя ломать)

_Та же концепция, что `docs/backlog/EXTERNAL_INTEGRATION_API.md`: **рестарт сервисов допустим**, **ломать проверку TOTP нельзя**. К моменту внедрения Express в проде уже работает VPN **otp_only + TOTP** (U1807 и массовый cutover)._

### Инвариант prod

```
NPS → radius → api:8000 /internal/radius/access-request
     → otp_only + otp_method=TOTP → verify_totp → Accept/Reject
```

Любой Express-rollout обязан сохранять **бит-в-бит** этот путь для пользователей с `otp_method=TOTP`. Регресс: верный OTP → Accept, неверный → Reject (без NPS 117).

### Что можно трогать / рестартовать

| Компонент | Express-доработка | Риск для TOTP |
|-----------|-------------------|---------------|
| **`worker-otp`** | BotX send, retries | **Низкий** — TOTP не использует очередь otp |
| **Новый контейнер `express-webhook`** | Приём нажатий Bot API | **Низкий** — если **не** в `radius.router` |
| **`api` restart** | Допустим | **Средний** — radius healthcheck; короткий gap UDP |
| **`radius` restart** | Допустим | **Средний** — окно VPN |
| **`radius_flow.py`** правки | Нужны для EXPRESSMS | **Высокий** — общий файл с TOTP |

### Правила разработки (acceptance)

1. **Отдельные ветки по `otp_method`** — Express/push **не рефакторить** TOTP/`verify_totp`/`otp_only`; только `elif method == "EXPRESSMS"` (+ push отдельно).
2. **Feature flags** — dry-run, push отдельным flag; выключено = как до фичи.
3. **Политика** — Express только где включён фактор; TOTP-пользователей не переключать молча.
4. **Webhook BotX** — отдельный контейнер `express-webhook` (как integration API).
5. **Фазы** (не один deploy):
   - **Фаза 1:** OTP текстом в BotX — код на VPN вручную, **совместимо с otp_only**.
   - **Фаза 2:** Push Approve/Deny — challenge/async, **opt-in**; TOTP otp_only не меняем.
6. **Гейт:** `test_radius_flow` TOTP + smoke U1807 перед prod.
7. **Миграции** — только additive.

### Контейнеры (черновик)

- **`worker-otp`** — BotX send; restart OK.
- **`express-webhook`** — тот же образ, entrypoint webhook + health; nginx `/api/v1/express/` → `:8002`.
- **`api`** — RADIUS; правки `radius_flow` только с TOTP-регрессом.

### otp_only vs push

| Express | NAS | TOTP-путь |
|---------|-----|-----------|
| OTP текстом | otp_only | **Не меняется** (другой `otp_method`) |
| Push кнопки | challenge/async | **Не меняется** при opt-in для TOTP |

ADR 0001: push = pending state + webhook, не один User-Password на otp_only.

### Клон prod для критичных выкатов

См. **[`PROD_SAFE_DEPLOY.md`](PROD_SAFE_DEPLOY.md)** — при правках `radius_flow` / смене RADIUS-схемы можно тестировать на **клоне prod-сервера**; пользоваться **редко** (нужна другая команда). Дефолт: lab + TOTP smoke, отдельные контейнеры, feature flags.

---

## Push → fallback TOTP (после N секунд)

_Запрос Merl 2026-08-23: Check Point (гипотетически latest) запросил push в Express; push потерялся; можно ли через N сек запросить TOTP — в MK 2FA._

### На стороне MK 2FA — **да, реализуемо**

Логика продукта (не зависит от вендора NAS):

1. Access-Request → открыть pending challenge, отправить push Express (кнопки Approve/Deny).
2. Ждать webhook Approve **до `push_wait_seconds`** (настраиваемо в политике).
3. Если Approve вовремя → Access-Accept.
4. Если **таймаут / push потерян / Deny** → fallback:
   - **A (предпочтительно при поддержке NAS):** Access-Challenge + `Reply-Message` «введите код TOTP» + `State`; следующий Access-Request с TOTP → Accept/Reject.
   - **B (без Challenge):** Access-Reject + сообщение; пользователь **переподключается** и вводит TOTP (нужны оба фактора у пользователя: Express + confirmed TOTP).

Предусловия в ПО:

- у пользователя **оба** канала: Express привязан **и** `totp_confirmed`;
- политика: Express primary + TOTP fallback; `push_wait_seconds`;
- RADIUS **не** текущий чистый `otp_only` (туда уже приходит только код) — нужен режим «ждать push» (hold request или challenge).

TOTP-путь для пользователей **без** Express **не трогать** (см. § деплой выше).

### Узкое место — Check Point / клиент

Текущий стенд: **otp_only** (User-Password = TOTP сразу). Push так **не работает** — некуда «ждать» кнопку.

Типовые паттерны MFA с Check Point:

| Паттерн | Что видит пользователь | Fallback TOTP после N сек |
|---------|------------------------|---------------------------|
| Hold Access-Request, push на телефоне | «Подключаюсь…» пока gateway ждёт RADIUS | **Авто-prompt TOTP в том же сеансе** — только если NAS/клиент умеет **Access-Challenge** или свой OTP UI |
| Challenge → поле OTP | Второе окно «введите код» | Да, если CP понимает Challenge |
| Reject после таймаута → повтор с TOTP | Ошибка, потом новый логин с кодом | **Да всегда** (вариант B), хуже UX |

Исторически на CheckMates: Remote Access **часто не показывает** второе окно на Access-Challenge; рабочий режим — пароль+OTP в одном поле **или** «RADIUS молчит, ждёт Accept» пока внешний push (LoginTC и аналоги). Таймауты gateway (`radius_*_timeout`) ограничивают, сколько можно ждать push.

**«Latest Check Point» сам по себе не гарантирует** push→OTP в одном диалоге. Нужен **Discovery** на реальном клиенте/gateway:

1. Blank / без OTP Access-Request → MK шлёт Challenge «enter OTP» — появляется ли поле?
2. Hold 30–60 с без ответа → что делает Endpoint (ждёт / обрывает)?
3. После Challenge с TOTP — Accept?

Пока Discovery не зелёный — в продукте закладывать:

- **fallback B** (reject + retry TOTP) — гарантированно;
- **fallback A** (Challenge TOTP) — feature flag + только для NAS, прошедших Discovery.

### Omnissa UAG (Horizon) — тот же сценарий

Официально ([Omnissa RADIUS](https://docs.omnissa.com/bundle/UnifiedAccessGatewayDeployandConfigureV2603/page/RADIUS.html)):

> If the RADIUS server issues a RADIUS **Access-Challenge**, Unified Access Gateway displays a **second dialog** prompting for the challenge response text (SMS OTP и т.п.). Только **текстовый** ввод.

То есть fallback **A** (после таймаута push → Challenge «введите TOTP») у UAG **на бумаге реалистичен** — в отличие от типичного Check Point Remote Access.

| | Check Point RA | Omnissa UAG |
|--|----------------|-------------|
| Access-Challenge → 2-е окно | Часто **нет** / ненадёжно | **Да** (документация Omnissa) |
| Hold RADIUS (ждать push) | Да, с лимитом timeout gateway | Да; **Server Timeout** / retries; формула Omnissa ≤ **~120 с** на primary |
| Push как Duo | Hold → Accept | Hold → Accept (типичный Duo на UAG) |
| Push потерян → TOTP в **том же** сеансе | Скорее **B** (reject+retry) | Скорее **A** (Challenge TOTP) |
| Текущий стенд MK | otp_only (код сразу) | Тот же `otp_only` в ADR 0001 / lab |

**Схема на UAG для push+fallback (черновик в MK 2FA):**

1. UAG уже сделал AD (или passcode = AD / blank — как настроят).
2. Access-Request → MK: Express push, **hold** до `push_wait_seconds` (должен быть **&lt;** Server Timeout UAG с запасом).
3. Approve → Access-Accept.
4. Таймаут / push потерян → **Access-Challenge** + Reply-Message «введите код TOTP» + State.
5. UAG показывает второе окно → пользователь вводит TOTP → Access-Request + State → Accept/Reject.

Ограничения UAG:

- Challenge только **текст** (не «нажмите кнопку в клиенте Horizon»).
- Долгий hold: если `push_wait_seconds` ≥ Server Timeout UAG — UAG **retry/обрыв**, Challenge не дойдёт. Настройка политики MK ↔ timeout на UAG **обязательна**.
- Текущий **otp_only** (User-Password = TOTP) для push **не подходит** — нужна отдельная политика/схема для UAG с push (per-client policy ADR 0002: UAG → push+challenge, NPS/CP → otp_only TOTP).

**Вывод по NAS:**

| NAS | Рекомендуемый `push_fallback` до Discovery | После Discovery |
|-----|--------------------------------------------|-----------------|
| Check Point | `totp_reject_retry` | Challenge — если подтвердили 2-е окно |
| Omnissa UAG | `totp_challenge` (ожидаемо) | Подтвердить hold+Challenge+TOTP e2e |
| Оба | Feature flag / `Policy` per NAS IP | Не ломать TOTP otp_only для остальных |

### Настройки (черновик, когда пойдём в код)

| Параметр | Смысл |
|----------|--------|
| `push_wait_seconds` | Сколько ждать Approve в Express (**&lt;** NAS RADIUS timeout) |
| `push_fallback` | `none` \| `totp_challenge` \| `totp_reject_retry` |
| Факторы политики | EXPRESSMS (+ TOTP для fallback) |
| Per NAS (ADR 0002) | UAG → challenge/push; CP/NPS → otp_only TOTP без поломки |

### Гибкие политики — **после** Express push (Merl 2026-08-23)

Вопросы CP / UAG / push→TOTP задавались **в разрезе будущей гибкой настройки политик**, не как требование «всё в первом релизе push».

**Порядок внедрения:**

1. **Express push** (BotX, webhook, hold/challenge в RADIUS) + минимальные настройки: wait seconds, fallback mode, dry-run. TOTP otp_only для текущих пользователей **не ломать**.
2. **Потом** — расширенные политики (гибче ADR 0002): per NAS/scope — `push_fallback`, timeouts, факторы, возможно разные схемы для UAG vs Check Point vs NPS.

До шага 2 достаточно:

- заложить в код/схему **поля или флаги**, которые политика потом начнёт читать (не хардкодить «только UAG» / «только CP»);
- default fallback консервативный (`totp_reject_retry` или глобальный setting);
- не раздувать UI политик до появления живого push.

Сравнение NAS (таблица выше) — **входные требования к модели политики**, не к MVP push.

---

## Готовое решение компании: `kteam-express`

Репо: https://github.com/v-bondarev/kteam-express.git (private). Снимок на lab: `/root/kteam-express-main`.

Это **корпоративный AI-помощник** (Bitrix, Directum, Jira, SmartApp, AD). **Не** сервис 2FA. Код бота в Express **не создаёт** — только обслуживает уже зарегистрированного.

### Как бот появляется (вне git)

1. Админ eXpress/CTS заводит чат-бота → выдаёт **`BOT_ID`** (UUID) и **`BOT_SECRET_KEY`**.
2. В карточке бота URL webhook = HTTPS нашего сервиса (`POST /command`).
3. Секреты в `.env` процесса, не в git (`.env.example`: `BOT_ID`, `BOT_SECRET_KEY`, `BOTX_API_HOST`, `BOTX_PROTOCOL_VERSION=4`).
4. Для 2FA — **отдельный бот**, не вселять push в этот помощник.

Два хоста (грабля kteam): `from.host` во входящем webhook (CTS, у них `hbotx.hci.interros.ru`) **часто недоступен из контейнера**. Исходящие — на **`BOTX_API_HOST`** (`exb.interros.ru`). JWT `aud` = hostname API-хоста (`makeToken(this.apiHost)` в `src/botx/client.js`).

### Как процесс слушает BotX

Node, порт **8001** (`PORT`). `src/app.js`:

| Метод | Путь | Зачем |
|-------|------|--------|
| `POST` | `/command` | входящие сообщения и **нажатия кнопок** |
| `POST` | `/notification/callback` | статус доставки; на `status=error` лог, ответ всегда 200 |
| `POST` | `/status` | статус бота для CTS |
| `POST` | `/smartapps/request` | SmartApp (для 2FA **не нужно**) |
| `GET` | `/health` | health |

Контракт `/command`: **сразу 200**, `processCommand` в фоне. Иначе BotX рвёт по таймауту.

Первый диалог: `command.body == system:chat_created` → приветствие. Прочие `system:*` без пользователя — игнор.

Идентичность из конверта `src/handlers/command.js` `parseIncoming`:

- `from.user_huid`
- `from.username` / ФИО
- `from.email`
- `from.group_chat_id` — **куда слать ответ**
- `from.host` — CTS этого пользователя

### Исходящее сообщение (паттерн для push)

Не статичный Bearer и не публичный `POST .../notifications/direct` из оф. доки как единственный путь.

kteam (`src/botx/auth.js` + `src/botx/client.js`):

1. JWT HS256, TTL **60 с**: `iss=BOT_ID`, `aud=<hostname BOTX_API_HOST>`, `version: 2`, `nbf`/`iat`/`exp`, `jti` без дефисов. Секрет = `BOT_SECRET_KEY`.
2. `POST {BOTX_API_HOST}/api/v4/botx/notifications/direct/sync`
3. Тело:

```json
{
  "group_chat_id": "<uuid чата>",
  "notification": {
    "status": "ok",
    "body": "текст",
    "bubble": [[
      {
        "command": "/approve",
        "label": "Разрешить",
        "data": { "challenge_id": "..." },
        "opts": { "silent": true }
      },
      {
        "command": "/deny",
        "label": "Отклонить",
        "data": { "challenge_id": "..." },
        "opts": { "silent": true }
      }
    ]]
  }
}
```

`opts.silent: true` — нажатие не печатает команду в чат. На webhook: `command.body` = `command` кнопки, `command.data` = payload.

Живой аналог Approve/Remind: `src/jira/approvals.js` (`buildApprovalNotification` + `botx.sendMessage(chatId, { body, bubble })`). Directum: `buildDirectumAssignmentActionBubble` в `src/handlers/directum.js`.

Заглушка MK 2FA `{"to": expressms_id, "text": "OTP: …"}` к этому API **не совместима**.

### Кого пушить: lookup в kteam нет

Вызовов BotX `users/by_email` / `chats/personal` **нет**. Проактив (Jira) берёт `chat_id` и `cts_host` из SQLite `usage_contacts` — строка появляется **только после** входящего `/command`.

Для 2FA: либо пользователь один раз открыл бота 2FA (enroll / `/start`), либо отдельно проверять официальный lookup по email (вариант A) — **в kteam не подтверждён**.

Email/ФИО дальше идут в AD/Directum/Jira, не в BotX.

### Что не тащить в MK 2FA

SmartApp, Ollama, Bitrix crawler, Jira SD, заказ авто, расчётный лист. Только: регистрация бота в CTS, JWT+`direct/sync`, webhook `/command`, `group_chat_id`, `bubble`+`silent`, раздельный `BOTX_API_HOST`.

---

## Открытые вопросы (закрыть когда Merl принесёт доку)

- [x] Есть ли **готовое решение** — да: `kteam-express` (помощник, не 2FA). Контакт по репо: v-bondarev.
- [ ] Как пользователи заведены в eXpress: **email = AD mail**? отдельный login?
- [x] Уже есть **бот для 2FA/уведомлений** или создавать нового? **Создавать нового** (помощник не шлюз MFA).
- [x] Куда слать: **личный чат** бот↔user (`group_chat_id` из webhook / кэш контакта), не security-чат.
- [x] Токен бота: kteam **не** ходит в `GET /api/v2/botx/bots/{id}/token`; сам подписывает JWT HS256 от `BOT_SECRET_KEY`.
- [ ] Нужен ли **только OTP** или **кнопки Approve/Deny**?
- [ ] Если push: NAS/VPN готов к **Access-Challenge / async**, или остаёмся на otp_only + код в сообщении?
- [ ] **Push → TOTP fallback:** Discovery CP / UAG — когда дойдём; модель `push_fallback` per policy — **после** MVP push (гибкие политики отдельным этапом)
- [ ] Rate limits BotX, DND, stealth_mode — требования безопасности?
- [ ] Первый контакт: обязательный `/start` у бота 2FA или lookup по email в BotX?

---

## TODO (когда будет дока)

1. ~~Сверить готовое решение компании с BotX API v4~~ — kteam: JWT + `notifications/direct/sync` + webhook `/command` (см. секцию выше). Не проксировать MFA через помощника.
2. ADR: Express + **non-regression TOTP** (deploy checklist).
3. Выбрать привязку: **сначала диалог с ботом** (как kteam) vs lookup email (вариант A, в kteam нет).
4. Реализовать `send_expressms_otp` под тот же контракт, что kteam (не `{"to","text"}`).
5. UI: убрать/заменить поле «ID в ExpressMS», подсказки по email.
6. Опционально: webhook + кнопки + связка с `OtpChallenge`.
7. Тесты + smoke на lab BotX Merl (dry-run → prod token).

---

## Ссылки в репо

| Что | Где |
|-----|-----|
| Канал EXPRESSMS в RADIUS | `api/app/radius_flow.py` |
| Celery OTP | `api/app/tasks.py`, очередь `otp` |
| ADR otp_only (ограничение для push) | `docs/adr/0001-radius-otp-only.md` |
| План продукта § ExpressMS | `PLAN_MK_2FA_SYSTEM_RU.md` |

---

_Следующий шаг: Merl находит документацию по готовым решениям Express в компании → агент читает этот файл + доку → предметный план/ADR._
