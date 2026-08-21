# ADR 0001 — RADIUS: только OTP, если LDAP уже на NAS

- Дата: 2026-08-21 МСК
- Статус: принято

## Контекст

VMware UAG / Check Point проверяют 1-й фактор (AD) сами. На RADIUS уходит **только код токена** (`User-Password` = TOTP), как с LinOTP. MK 2FA на каждый Access-Request делал LDAP bind этим «паролем» → bind в AD с OTP, таймаут NAS, аудит `RADIUS_ERROR`.

Поле `policies.radius_scheme_preference` уже в схеме (default `challenge`), в flow не использовалось.

## Решение

- `challenge` — как в плане §1: LDAP, затем Access-Challenge + OTP.
- `otp_only` — LDAP не вызывать; найти пользователя, проверить TOTP, сразу Accept/Reject. Для UAG/checkpoint.

## Отвергнуто

- Автодетект «6 цифр = OTP»: пароль AD тоже может быть из цифр.
- otp_only для ExpressMS/Telegram без предварительного challenge: код ещё не отправляли.
