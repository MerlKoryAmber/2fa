#!/usr/bin/env bash
# Диагностика Express push + NPS 117 на lab. Запуск: sudo ./scripts/diagnose_radius_push.sh [username]
set -euo pipefail
USER_FILTER="${1:-U1807}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"

log "=== MK2FA diagnose push (user ~${USER_FILTER}) ==="

if [[ -d "${REPO_ROOT}/.git" ]]; then
  log "git: $(git -C "$REPO_ROOT" log -1 --oneline 2>/dev/null || echo '?')"
fi

RADIUS_CTR="$(find_compose_ctr radius)"
API_CTR="$(find_compose_ctr api)"
DB_CTR="$(find_compose_ctr db)"

if [[ -n "$RADIUS_CTR" ]]; then
  log "--- radius startup (workers?) ---"
  podman logs "$RADIUS_CTR" 2>&1 | grep -E 'RADIUS listening|workers=' | tail -3 || true
  log "--- radius last packets (${USER_FILTER}) ---"
  podman logs --since 20m "$RADIUS_CTR" 2>&1 | grep -E "recv user=${USER_FILTER}|user=${USER_FILTER}.*decision=" | tail -20 || true
  last_accept="$(podman logs --since 20m "$RADIUS_CTR" 2>&1 | grep -E "user=${USER_FILTER}.*decision=accept.*api_s=" | tail -1 || true)"
  if [[ -n "$last_accept" ]]; then
    api_s="$(printf '%s' "$last_accept" | sed -n 's/.*api_s=\([0-9.]*\).*/\1/p')"
    if [[ -n "$api_s" ]] && awk -v t="$api_s" 'BEGIN{exit!(t>5.0)}'; then
      warn "api_s=${api_s}s > 5s при accept — типично HNPS Connection timeout=5 (default). См. docs/backlog/NPS_EXPRESS_PUSH_TIMEOUT.md"
    fi
  fi
else
  warn "контейнер radius не найден"
fi

if [[ -n "$API_CTR" ]]; then
  log "--- api express push (${USER_FILTER}) ---"
  podman logs --since 20m "$API_CTR" 2>&1 | grep -iE "express push|EXPRESS_PUSH|access-request" | tail -15 || true
fi

if [[ -n "$DB_CTR" ]]; then
  log "--- policy + user ---"
  podman exec "$DB_CTR" psql -U mfa -d mfa -t -c \
    "SELECT radius_scheme_preference, mfa_scenario, push_wait_seconds FROM policies LIMIT 1;" 2>/dev/null || true
  podman exec "$DB_CTR" psql -U mfa -d mfa -t -c \
    "SELECT ad_username, express_channel_enabled, ldap_email FROM users WHERE ad_username ILIKE '${USER_FILTER}';" 2>/dev/null || true
  log "--- audit last 15 (${USER_FILTER}) ---"
  podman exec "$DB_CTR" psql -U mfa -d mfa -c \
    "SELECT timestamp AT TIME ZONE 'Europe/Moscow' AS msk, event_type, meta->>'reason' AS reason
     FROM audit_events WHERE username ILIKE '${USER_FILTER}'
     ORDER BY id DESC LIMIT 15;" 2>/dev/null || warn "audit: psql failed (проверь контейнер db)"
fi

log "ожидаем на push: EXPRESS_PUSH_SEND (1x) → EXPRESS_PUSH_REUSE (ретраи NPS) → HOLD → DECISION → RADIUS_ACCEPT"
log "117 при accept в radius: HNPS Remote RADIUS Server Group → Connection timeout ≥ push_wait+30с (default NPS = 5с)"
log "док: docs/backlog/NPS_EXPRESS_PUSH_TIMEOUT.md"
