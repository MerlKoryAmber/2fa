#!/usr/bin/env bash
# Импорт seeds_export.csv в Postgres MK 2FA через контейнер api.
# На хосте нет cryptography/sqlalchemy; БД слушает hostname db только внутри compose.
#   sudo ./scripts/import_linotp_seeds.sh /opt/2fa/migration/seeds_export.csv
#   sudo ./scripts/import_linotp_seeds.sh ./seeds_export.csv --apply
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"

usage() {
  cat <<'EOF'
Usage: import_linotp_seeds.sh CSV [python-args...]

  CSV             seeds_export.csv (из export_seeds.py)
  (без флагов)    dry-run
  --apply         писать в БД
  --create-missing / --overwrite  как у import_seeds.py

Запускает python внутри контейнера api (зависимости уже в образе).
EOF
}

if [[ $# -lt 1 || "$1" == "-h" || "$1" == "--help" ]]; then
  usage
  exit 0
fi

CSV="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
[[ -f "$CSV" ]] || die "нет файла CSV: $1"
shift

IMP="${REPO_ROOT}/migration/import_seeds.py"
[[ -f "$IMP" ]] || die "нет $IMP"

cname=""
for c in "${COMPOSE_PROJECT_NAME}_api_1" "2fa_api_1" "mk2fa_api_1" "own2fa_api_1"; do
  if have_cmd podman && podman inspect "$c" >/dev/null 2>&1; then
    cname="$c"
    break
  fi
done
if [[ -z "$cname" ]] && have_cmd podman; then
  cname="$(podman ps --format '{{.Names}}' | grep -E '_api(_|$)' | head -1 || true)"
fi
[[ -n "$cname" ]] || die "контейнер api не найден (podman ps)"

log "api=$cname csv=$CSV"
podman cp "$IMP" "$cname:/tmp/import_seeds.py"
podman cp "$CSV" "$cname:/tmp/seeds_export.csv"
set +e
podman exec -w /tmp "$cname" python3 /tmp/import_seeds.py /tmp/seeds_export.csv "$@"
rc=$?
set -e
podman exec "$cname" rm -f /tmp/import_seeds.py /tmp/seeds_export.csv || true
exit "$rc"
