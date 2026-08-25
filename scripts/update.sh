#!/usr/bin/env bash
# Обновление MK 2FA: git pull (если есть remote) + полный rebuild стека + миграции.
#   sudo ./scripts/update.sh
#   sudo ./scripts/update.sh --no-pull    # только образы/контейнеры
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"

DO_PULL=1
SKIP_EXPRESS=0

usage() {
  cat <<'EOF'
Usage: update.sh [options]

  --no-pull        не делать git fetch/pull
  --skip-express   не спрашивать параметры Express-бота
  -h, --help

После pull скрипт exec'ит себя с --no-pull — иначе в памяти остаётся старый
common.sh (smoke 403 без диагностики). Затем спрашивает BOT_ID / секрет /
BOTX_API_HOST (если пусто или согласились изменить), down → build api/radius/web/
express-bot → up, alembic, health, smoke RADIUS→API.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-pull) DO_PULL=0; shift ;;
    --skip-express) SKIP_EXPRESS=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "неизвестный аргумент: $1" ;;
  esac
done

[[ -f "${REPO_ROOT}/docker-compose.yml" ]] || die "нет docker-compose.yml в $REPO_ROOT"
[[ -f "${REPO_ROOT}/.env" ]] || die "нет .env — сначала install.sh"

engine="$(detect_engine)"
[[ "$engine" != none ]] || die "нет podman-compose / docker compose"

cd "$REPO_ROOT"

if [[ "$DO_PULL" -eq 1 ]]; then
  if [[ -d "${REPO_ROOT}/.git" ]] && have_cmd git; then
    git_sync_repo
    log "перечитываю update.sh после pull"
    if [[ "$SKIP_EXPRESS" == 1 ]]; then
      exec bash "${SCRIPT_DIR}/update.sh" --no-pull --skip-express
    else
      exec bash "${SCRIPT_DIR}/update.sh" --no-pull
    fi
  else
    die "не git-репозиторий — положите код и: $0 --no-pull"
  fi
fi

log "сборка с HEAD $(git log -1 --oneline 2>/dev/null || echo 'нет git')"
normalize_env_file
configure_express_bot
open_firewall_hint

log "=== rebuild стека ==="
compose_up_build
sleep 3
alembic_upgrade
wait_health
smoke_internal_radius

log "обновление завершено"
log "версия миграций: podman exec <api> alembic current"
