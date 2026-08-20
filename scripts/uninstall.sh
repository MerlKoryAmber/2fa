#!/usr/bin/env bash
# Остановка и удаление стека MK 2FA.
#   sudo ./scripts/uninstall.sh           # down, volumes сохранить
#   sudo ./scripts/uninstall.sh --purge   # down -v + удалить .env credentials
#   sudo ./scripts/uninstall.sh --purge --remove-dir   # + удалить каталог репо (осторожно)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"

PURGE=0
REMOVE_DIR=0

usage() {
  cat <<'EOF'
Usage: uninstall.sh [options]

  --purge         удалить volumes (БД, ssl_certs) — данные 2FA пропадут
  --remove-dir    удалить весь каталог репозитория (только с --purge)
  -h, --help

Не удаляет пакеты ОС (podman/python) — только стек приложения.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --purge) PURGE=1; shift ;;
    --remove-dir) REMOVE_DIR=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "неизвестный аргумент: $1" ;;
  esac
done

[[ -f "${REPO_ROOT}/docker-compose.yml" ]] || die "нет docker-compose.yml в $REPO_ROOT"

if [[ "$REMOVE_DIR" -eq 1 && "$PURGE" -ne 1 ]]; then
  die "--remove-dir только вместе с --purge"
fi

log "остановка стека в $REPO_ROOT"
cd "$REPO_ROOT"

if [[ "$PURGE" -eq 1 ]]; then
  log "compose down -v (volumes будут удалены)"
  compose down -v || true
  rm -f "${REPO_ROOT}/.install-credentials.txt"
  warn ".env не удаляю автоматически (секреты). Удалите вручную при необходимости: rm ${REPO_ROOT}/.env"
else
  compose down || true
  log "volumes сохранены (pgdata, ssl_certs). Для полного сноса: $0 --purge"
fi

if [[ "$REMOVE_DIR" -eq 1 ]]; then
  need_root
  parent="$(dirname "$REPO_ROOT")"
  base="$(basename "$REPO_ROOT")"
  log "удаляю каталог $REPO_ROOT"
  cd "$parent"
  rm -rf -- "$base"
  log "каталог удалён"
else
  log "готово. Каталог $REPO_ROOT на месте."
fi
