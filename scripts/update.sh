#!/usr/bin/env bash
# Обновление MK 2FA: git pull (если есть remote) + полный rebuild стека + миграции.
#   sudo ./scripts/update.sh
#   sudo ./scripts/update.sh --no-pull    # только образы/контейнеры
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"

DO_PULL=1

usage() {
  cat <<'EOF'
Usage: update.sh [options]

  --no-pull     не делать git fetch/pull
  -h, --help

Делает полный compose down → build api/radius/web → up -d (иначе на lab новый образ api
часто не подхватывается). Затем alembic, health, smoke RADIUS→API.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-pull) DO_PULL=0; shift ;;
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
    log "git fetch + pull --ff-only"
    git fetch origin 2>/dev/null || git fetch 2>/dev/null || warn "git fetch не удался"
    if ! git pull --ff-only 2>/dev/null; then
      warn "fast-forward pull не удался — обновите ветку вручную, затем: $0 --no-pull"
    fi
  else
    warn "не git-репозиторий — пропуск pull (положите новый код и снова update --no-pull)"
  fi
fi

normalize_env_file
open_firewall_hint

log "=== rebuild стека ==="
compose_up_build
sleep 3
alembic_upgrade
wait_health
smoke_internal_radius

log "обновление завершено"
log "версия миграций: podman exec <api> alembic current"
