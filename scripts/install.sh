#!/usr/bin/env bash
# Установка MK 2FA на Linux: зависимости хоста + .env + compose up.
# Использование:
#   sudo ./scripts/install.sh
#   sudo ./scripts/install.sh --dir /opt/mk2fa --repo https://github.com/MerlKoryAmber/2fa.git
#   sudo ./scripts/install.sh --skip-pkgs   # только стек, пакеты уже стоят
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"

SKIP_PKGS=0
INSTALL_DIR=""
REPO_URL="${MK2FA_REPO_URL:-${OWN2FA_REPO_URL:-https://github.com/MerlKoryAmber/2fa.git}}"
BRANCH="${MK2FA_BRANCH:-${OWN2FA_BRANCH:-main}}"

usage() {
  cat <<'EOF'
Usage: install.sh [options]

  --dir PATH       каталог установки (clone, если пусто / нет docker-compose.yml)
  --repo URL       git remote (default: GitHub MerlKoryAmber/2fa)
  --branch NAME    ветка (default: main)
  --skip-pkgs      не ставить пакеты ОС (только .env + compose)
  -h, --help

Требует root для установки пакетов. Предпочтительно Podman + podman-compose;
если есть только Docker Compose v2 — используется он.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dir) INSTALL_DIR="$2"; shift 2 ;;
    --repo) REPO_URL="$2"; shift 2 ;;
    --branch) BRANCH="$2"; shift 2 ;;
    --skip-pkgs) SKIP_PKGS=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "неизвестный аргумент: $1" ;;
  esac
done

# Если указали --dir и там ещё нет проекта — клонируем
prepare_tree() {
  if [[ -n "$INSTALL_DIR" ]]; then
    mkdir -p "$INSTALL_DIR"
    if [[ ! -f "${INSTALL_DIR}/docker-compose.yml" ]]; then
      need_root
      if [[ "$SKIP_PKGS" -eq 0 ]]; then
        # git нужен до clone
        if ! have_cmd git; then
          install_host_packages
        fi
      fi
      have_cmd git || die "нужен git"
      log "clone $REPO_URL → $INSTALL_DIR (branch $BRANCH)"
      if [[ -z "$(ls -A "$INSTALL_DIR" 2>/dev/null || true)" ]]; then
        git clone --branch "$BRANCH" "$REPO_URL" "$INSTALL_DIR"
      else
        die "$INSTALL_DIR не пуст и без docker-compose.yml"
      fi
    fi
    REPO_ROOT="$(cd "$INSTALL_DIR" && pwd)"
  fi
  [[ -f "${REPO_ROOT}/docker-compose.yml" ]] || die "нет docker-compose.yml в $REPO_ROOT"
  log "REPO_ROOT=$REPO_ROOT"
}

main() {
  prepare_tree

  if [[ "$SKIP_PKGS" -eq 0 ]]; then
    need_root
    log "=== установка пакетов хоста ==="
    install_host_packages
  else
    log "пропуск пакетов (--skip-pkgs)"
  fi

  local engine
  engine="$(detect_engine)"
  [[ "$engine" != none ]] || die "после установки пакетов нет podman-compose/docker compose"
  log "engine: $engine"

  # rootless podman иногда ломается на привилегированных портах 80/443 — для install рекомендуем rootful
  if [[ "$engine" == podman ]] && [[ "${EUID}" -ne 0 ]]; then
    warn "не root: порты 80/443 могут быть недоступны rootless podman — запускайте install через sudo"
  fi

  ensure_env_file
  normalize_env_file
  open_firewall_hint

  log "=== сборка и запуск стека ==="
  # compose из REPO_ROOT
  cd "$REPO_ROOT"
  compose_up_build
  sleep 3
  alembic_upgrade
  wait_health
  smoke_internal_radius

  local pub detected
  detected="$(suggest_public_base_url)"
  pub="$(grep -E '^PUBLIC_BASE_URL=' "${REPO_ROOT}/.env" 2>/dev/null | cut -d= -f2- || true)"
  # старый .env.example тащил IP домашней lab — не показывать его как «этот сервер»
  if [[ -z "$pub" || "$pub" == "https://192.168.0.178" ]]; then
    pub="$detected"
  fi

  cat <<EOF

=== MK 2FA установлен ===
Каталог:     $REPO_ROOT
Панель:      ${pub}/
Health:      curl -sk https://127.0.0.1/health
Логин:       admin
Пароль:      admin  (смените в панели после входа)
Дальше:      Настройки → LDAP / RADIUS / SMTP
Обновление:  sudo ${REPO_ROOT}/scripts/update.sh
Удаление:    sudo ${REPO_ROOT}/scripts/uninstall.sh [--purge]

EOF
}

main "$@"
