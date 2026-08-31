#!/usr/bin/env bash
# Общие функции для install / uninstall / update MK 2FA.
# shellcheck disable=SC2034

set -euo pipefail

_MK2FA_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${_MK2FA_LIB_DIR}/../.." && pwd)"

# sudo на EL/CentOS: secure_path без /usr/local/bin — pip ставит podman-compose туда.
export PATH="/usr/local/bin:/usr/local/sbin:${PATH}"
export PYTHONUNBUFFERED=1

# shellcheck disable=SC2034
COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-$(basename "$REPO_ROOT" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]//g')}"
if [[ -z "$COMPOSE_PROJECT_NAME" ]]; then
  COMPOSE_PROJECT_NAME="mk2fa"
fi

log()  { printf '[mk2fa] %s\n' "$*"; }
warn() { printf '[mk2fa] WARN: %s\n' "$*" >&2; }
die()  { printf '[mk2fa] ERROR: %s\n' "$*" >&2; exit 1; }

need_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    die "нужен root (sudo). Сейчас uid=${EUID}"
  fi
}

have_cmd() { command -v "$1" >/dev/null 2>&1; }

detect_pkg_manager() {
  if have_cmd apt-get; then echo apt
  elif have_cmd dnf; then echo dnf
  elif have_cmd yum; then echo yum
  elif have_cmd zypper; then echo zypper
  elif have_cmd pacman; then echo pacman
  elif have_cmd apk; then echo apk
  else echo none
  fi
}

pkg_install() {
  local pm
  pm="$(detect_pkg_manager)"
  [[ "$pm" != none ]] || die "неизвестный пакетный менеджер (нужны apt/dnf/yum/zypper/pacman/apk)"
  case "$pm" in
    apt)
      export DEBIAN_FRONTEND=noninteractive
      apt-get update -y
      apt-get install -y "$@"
      ;;
    dnf) dnf install -y "$@" ;;
    yum) yum install -y "$@" ;;
    zypper) zypper --non-interactive install -y "$@" ;;
    pacman) pacman -Sy --noconfirm "$@" ;;
    apk) apk add --no-cache "$@" ;;
  esac
}

# Пакеты по семейству ОС (имена могут отличаться — ставим что есть).
install_host_packages() {
  local pm pkg pkgs=()
  pm="$(detect_pkg_manager)"
  log "пакетный менеджер: $pm"

  case "$pm" in
    apt)
      pkg_install curl ca-certificates git openssl python3 python3-pip \
        podman uidmap slirp4netns || die "базовые пакеты (apt) не установились"
      apt-get install -y podman-compose 2>/dev/null || true
      apt-get install -y freeradius-utils 2>/dev/null || true
      ;;
    dnf|yum)
      pkg_install curl ca-certificates git openssl python3 python3-pip \
        podman containernetworking-plugins || die "базовые пакеты (dnf/yum) не установились"
      if have_cmd dnf; then
        dnf install -y podman-compose 2>/dev/null || true
        dnf install -y freeradius-utils 2>/dev/null || true
      else
        yum install -y podman-compose 2>/dev/null || true
        yum install -y freeradius-utils 2>/dev/null || true
      fi
      ;;
    zypper)
      pkg_install curl ca-certificates git openssl python3 python3-pip podman \
        || die "базовые пакеты (zypper) не установились"
      ;;
    pacman)
      pkg_install curl ca-certificates git openssl python python-pip podman \
        || die "базовые пакеты (pacman) не установились"
      ;;
    apk)
      pkg_install curl ca-certificates git openssl python3 py3-pip podman \
        || die "базовые пакеты (apk) не установились"
      ;;
  esac

  have_cmd podman || have_cmd docker || die "нет podman и docker после установки пакетов"

  # compose: пакет или pip (бинарь часто в /usr/local/bin — PATH уже поправлен выше)
  if have_cmd podman && ! podman_compose_ok; then
    log "ставим podman-compose через pip3"
    pip3 install --upgrade podman-compose \
      || die "pip3 install podman-compose не удался"
    hash -r 2>/dev/null || true
    podman_compose_ok || die "pip поставил модуль, но запустить podman-compose нельзя (проверь /usr/local/bin в PATH)"
  fi

  # Docker fallback, если podman так и не появился
  if ! have_cmd podman && have_cmd docker; then
    log "используем Docker (podman недоступен)"
    if ! docker compose version >/dev/null 2>&1 && ! have_cmd docker-compose; then
      warn "нет docker compose — поставьте docker-compose-plugin вручную"
    fi
  fi
}

_pc_pythonpath() {
  printf '%s' "${PYTHONPATH:-}${PYTHONPATH:+:}/usr/local/lib/python3.9/site-packages:/usr/local/lib/python3.11/site-packages:/usr/local/lib/python3.12/site-packages"
}

# pip-модуль и/или бинарь (sudo PATH часто без /usr/local/bin).
podman_compose_ok() {
  have_cmd podman-compose && return 0
  [[ -x /usr/local/bin/podman-compose ]] && return 0
  [[ -x /usr/bin/podman-compose ]] && return 0
  python3 -c "import podman_compose" 2>/dev/null && return 0
  return 1
}

run_podman_compose() {
  local pc=""
  pc="$(command -v podman-compose 2>/dev/null || true)"
  [[ -z "$pc" && -x /usr/local/bin/podman-compose ]] && pc=/usr/local/bin/podman-compose
  [[ -z "$pc" && -x /usr/bin/podman-compose ]] && pc=/usr/bin/podman-compose
  if [[ -n "$pc" ]]; then
    env PYTHONPATH="$(_pc_pythonpath)" PYTHONUNBUFFERED=1 "$pc" "$@"
  elif python3 -c "import podman_compose" 2>/dev/null; then
    env PYTHONPATH="$(_pc_pythonpath)" PYTHONUNBUFFERED=1 python3 -m podman_compose "$@"
  else
    die "podman есть, podman-compose нет (ни бинаря, ни python3 -m). pip3 install podman-compose"
  fi
}

detect_engine() {
  if have_cmd podman && podman_compose_ok; then
    echo podman
  elif have_cmd docker && docker compose version >/dev/null 2>&1; then
    echo docker
  elif have_cmd docker && have_cmd docker-compose; then
    echo docker-compose
  else
    echo none
  fi
}

# Ключи из .env в окружение процесса (sudo env_reset иначе пустой ${VAR} в yaml).
export_repo_env() {
  local envf="${REPO_ROOT}/.env" line key val
  [[ -f "$envf" ]] || return 0
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%$'\r'}"
    [[ "$line" =~ ^[[:space:]]*# ]] && continue
    [[ "$line" == *=* ]] || continue
    key="${line%%=*}"
    val="${line#*=}"
    key="${key#"${key%%[![:space:]]*}"}"
    key="${key%"${key##*[![:space:]]}"}"
    [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
    if [[ ${#val} -ge 2 ]]; then
      if [[ "${val:0:1}" == '"' && "${val: -1}" == '"' ]]; then
        val="${val:1:${#val}-2}"
      elif [[ "${val:0:1}" == "'" && "${val: -1}" == "'" ]]; then
        val="${val:1:${#val}-2}"
      fi
    fi
    export "${key}=${val}"
  done < "$envf"
}

# fetch+ff-only. Shallow clone от старого install --depth 1 иначе не видит новые коммиты.
git_sync_repo() {
  have_cmd git || die "нужен git"
  [[ -d "${REPO_ROOT}/.git" ]] || die "нет .git в $REPO_ROOT — ставьте через install.sh --dir"
  cd "$REPO_ROOT"
  if [[ "$(git rev-parse --is-shallow-repository 2>/dev/null || true)" == "true" ]]; then
    log "shallow clone — git fetch --unshallow (иначе update не подтягивает коммиты)"
    git fetch --unshallow origin || git fetch --unshallow || git fetch --deepen=200 origin
  fi
  log "git fetch origin"
  git fetch origin
  local br
  br="$(git rev-parse --abbrev-ref HEAD)"
  if [[ "$br" == "HEAD" ]]; then
    log "detached HEAD — checkout main"
    git checkout -B main origin/main
    br="main"
  fi
  log "git pull --ff-only origin $br"
  git pull --ff-only origin "$br"
  log "HEAD $(git log -1 --oneline)"
}

# Запуск compose: pip на EL → /usr/local/bin + PYTHONPATH.
compose() {
  local engine
  engine="$(detect_engine)"
  cd "$REPO_ROOT"
  export_repo_env
  case "$engine" in
    podman)
      run_podman_compose "$@"
      ;;
    docker)
      docker compose "$@"
      ;;
    docker-compose)
      docker-compose "$@"
      ;;
    *)
      die "нет podman-compose / docker compose. Запустите scripts/install.sh"
      ;;
  esac
}

rand_b64() {
  openssl rand -base64 "$1" | tr -d '\n' | tr '+/' '-_'
}

rand_hex() {
  openssl rand -hex "$1" | tr -d '\n'
}

# Fernet: 32 байта → url-safe base64
gen_fernet_key() {
  openssl rand -base64 32 | tr -d '\n'
}

# Первый IPv4 хоста (не loopback). Не docker0 в приоритете hostname -I обычно даёт основной.
host_primary_ipv4() {
  hostname -I 2>/dev/null | tr ' ' '\n' | awk '
    $0 ~ /^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$/ && $0 !~ /^127\./ { print; exit }
  '
}

suggest_public_base_url() {
  local ip
  ip="$(host_primary_ipv4)"
  if [[ -n "$ip" ]]; then
    printf 'https://%s' "$ip"
  else
    printf 'https://127.0.0.1'
  fi
}

env_file_get() {
  local key="$1" envf="${REPO_ROOT}/.env"
  [[ -f "$envf" ]] || return 0
  grep -E "^${key}=" "$envf" | head -1 | cut -d= -f2- || true
}

env_file_set() {
  local key="$1" val="$2" envf="${REPO_ROOT}/.env"
  [[ -f "$envf" ]] || die "нет $envf"
  local esc
  esc="$(printf '%s' "$val" | sed -e 's/[\/&]/\\&/g')"
  if grep -q "^${key}=" "$envf"; then
    sed -i.bak "s|^${key}=.*|${key}=${esc}|" "$envf"
  else
    printf '%s=%s\n' "$key" "$val" >>"$envf"
  fi
  rm -f "${envf}.bak"
}

ensure_env_file() {
  local envf="${REPO_ROOT}/.env"
  local ex="${REPO_ROOT}/.env.example"
  [[ -f "$ex" ]] || die "нет .env.example в $REPO_ROOT"

  if [[ -f "$envf" ]]; then
    log ".env уже есть — не перезаписываю"
    normalize_env_file
    return 0
  fi

  log "создаю .env из .env.example + сгенерированные секреты"
  cp "$ex" "$envf"

  local fernet pg jwt internal radius
  fernet="$(gen_fernet_key)"
  pg="$(rand_hex 16)"
  jwt="$(rand_hex 24)"
  internal="$(rand_hex 24)"
  radius="$(rand_hex 12)"

  env_file_set APP_ENCRYPTION_KEY "$fernet"
  env_file_set POSTGRES_PASSWORD "$pg"
  env_file_set JWT_SECRET "$jwt"
  env_file_set INTERNAL_API_TOKEN "$internal"
  env_file_set RADIUS_SECRET "$radius"
  env_file_set ADMIN_USERNAME "admin"
  env_file_set ADMIN_PASSWORD "admin"
  env_file_set PUBLIC_BASE_URL "$(suggest_public_base_url)"
  log "PUBLIC_BASE_URL=$(grep '^PUBLIC_BASE_URL=' "$envf" | cut -d= -f2-)"
  # lab defaults из example; LDAP настраивается в панели

  umask 077
  chmod 600 "$envf" 2>/dev/null || true

  cat >"${REPO_ROOT}/.install-credentials.txt" <<EOF
# Сгенерировано $(date -u +%Y-%m-%dT%H:%MZ) — смените после первого входа. Не коммитить.
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin
RADIUS_SECRET=${radius}
POSTGRES_PASSWORD=${pg}
EOF
  chmod 600 "${REPO_ROOT}/.install-credentials.txt" 2>/dev/null || true
  log "учётные данные: ${REPO_ROOT}/.install-credentials.txt"
  normalize_env_file
}

# CRLF из Windows/notepad ломает X-Internal-Token (403 radius→api).
normalize_env_file() {
  local envf="${REPO_ROOT}/.env"
  [[ -f "$envf" ]] || return 0
  if grep -q $'\r' "$envf" 2>/dev/null; then
    log "нормализую CRLF в .env"
    sed -i 's/\r$//' "$envf"
  fi
}

# Старый .env без ключей бота — дописать пустые/дефолтные.
ensure_express_env_keys() {
  local envf="${REPO_ROOT}/.env"
  [[ -f "$envf" ]] || return 0
  grep -q '^EXPRESS_BOT_URL=' "$envf" || printf 'EXPRESS_BOT_URL=http://express-bot:8030\n' >>"$envf"
  grep -q '^BOTX_API_HOST=' "$envf" || printf 'BOTX_API_HOST=\n' >>"$envf"
  grep -q '^BOT_ID=' "$envf" || printf 'BOT_ID=\n' >>"$envf"
  grep -q '^BOT_SECRET_KEY=' "$envf" || printf 'BOT_SECRET_KEY=\n' >>"$envf"
  grep -q '^BOT_APP_ID=' "$envf" || printf 'BOT_APP_ID=push2fa_bot\n' >>"$envf"
  grep -q '^BOT_LISTEN_PORT=' "$envf" || printf 'BOT_LISTEN_PORT=8030\n' >>"$envf"
  grep -q '^MK2FA_API_URL=' "$envf" || printf 'MK2FA_API_URL=http://api:8000\n' >>"$envf"
}

express_bot_configured() {
  local id host secret
  id="$(env_file_get BOT_ID)"
  host="$(env_file_get BOTX_API_HOST)"
  secret="$(env_file_get BOT_SECRET_KEY)"
  [[ -n "${id// /}" && -n "${host// /}" && -n "${secret// /}" ]]
}

_ask_yn() {
  local prompt="$1" default="${2:-n}" reply yn="y/N"
  [[ "$default" == [yY] ]] && yn="Y/n"
  if [[ -r /dev/tty ]]; then
    printf '[mk2fa] %s [%s]: ' "$prompt" "$yn" >/dev/tty
    IFS= read -r reply </dev/tty || reply=""
  elif [[ -t 0 ]]; then
    printf '[mk2fa] %s [%s]: ' "$prompt" "$yn"
    IFS= read -r reply || reply=""
  else
    reply="$default"
  fi
  reply="${reply#"${reply%%[![:space:]]*}"}"
  reply="${reply%"${reply##*[![:space:]]}"}"
  if [[ -z "$reply" ]]; then
    [[ "$default" == [yY] ]] && return 0
    return 1
  fi
  case "$reply" in
    y|Y|yes|YES|д|Д|да|Да) return 0 ;;
    *) return 1 ;;
  esac
}

_read_prompt() {
  local prompt="$1" secret="${2:-0}" out=""
  if [[ -r /dev/tty ]]; then
    printf '[mk2fa] %s' "$prompt" >/dev/tty
    if [[ "$secret" == 1 ]]; then
      IFS= read -rs out </dev/tty || out=""
      printf '\n' >/dev/tty
    else
      IFS= read -r out </dev/tty || out=""
    fi
  elif [[ -t 0 ]]; then
    printf '[mk2fa] %s' "$prompt"
    if [[ "$secret" == 1 ]]; then
      IFS= read -rs out || out=""
      printf '\n'
    else
      IFS= read -r out || out=""
    fi
  fi
  printf '%s' "$out"
}

# SKIP_EXPRESS=1 или --skip-express: не спрашивать.
# Без TTY: не блокировать; если ключи пустые — предупреждение.
configure_express_bot() {
  ensure_express_env_keys
  if [[ "${SKIP_EXPRESS:-0}" == 1 ]]; then
    log "Express-бот: пропуск настройки (--skip-express)"
    return 0
  fi

  local can_ask=0
  [[ -r /dev/tty || -t 0 ]] && can_ask=1

  if [[ "$can_ask" -eq 0 ]]; then
    if express_bot_configured; then
      log "Express-бот: BOT_ID / BOTX_API_HOST уже в .env"
    else
      warn "нет TTY — параметры Express не спрашиваю. Заполните BOT_ID, BOT_SECRET_KEY, BOTX_API_HOST в .env и снова update.sh"
    fi
    return 0
  fi

  log "--- Express-бот (push Approve/Deny) ---"
  log "слушает этот хост :8030; «Адрес бота» в Express: https://<этот-хост>:8030 (без /command)"
  log "BOTX_API_HOST — CTS/API отправки (не порт 8030)"

  if express_bot_configured; then
    _ask_yn "Параметры бота уже в .env. Изменить?" n || {
      log "Express-бот: оставляю текущие параметры"
      return 0
    }
  else
    _ask_yn "Настроить Express-бота (BOT_ID, секрет, BOTX_API_HOST)?" y || {
      log "Express-бот: без параметров (образ всё равно соберётся)"
      return 0
    }
  fi

  local cur_host cur_id cur_app in_host in_id in_secret in_app
  cur_host="$(env_file_get BOTX_API_HOST)"
  cur_id="$(env_file_get BOT_ID)"
  cur_app="$(env_file_get BOT_APP_ID)"
  [[ -n "$cur_app" ]] || cur_app="push2fa_bot"

  in_host="$(_read_prompt "BOTX_API_HOST [${cur_host}]: ")"
  [[ -n "$in_host" ]] || in_host="$cur_host"
  in_id="$(_read_prompt "BOT_ID [${cur_id}]: ")"
  [[ -n "$in_id" ]] || in_id="$cur_id"
  in_secret="$(_read_prompt "BOT_SECRET_KEY (пусто = не менять): " 1)"
  in_app="$(_read_prompt "BOT_APP_ID [${cur_app}]: ")"
  [[ -n "$in_app" ]] || in_app="$cur_app"

  [[ -n "${in_host// /}" ]] || die "BOTX_API_HOST пустой"
  [[ -n "${in_id// /}" ]] || die "BOT_ID пустой"
  if [[ -z "$in_secret" ]]; then
    in_secret="$(env_file_get BOT_SECRET_KEY)"
  fi
  [[ -n "${in_secret// /}" ]] || die "BOT_SECRET_KEY пустой"

  env_file_set BOTX_API_HOST "$in_host"
  env_file_set BOT_ID "$in_id"
  env_file_set BOT_SECRET_KEY "$in_secret"
  env_file_set BOT_APP_ID "$in_app"
  env_file_set EXPRESS_BOT_URL "http://express-bot:8030"
  env_file_set MK2FA_API_URL "http://api:8000"
  env_file_set BOT_LISTEN_PORT "8030"
  chmod 600 "${REPO_ROOT}/.env" 2>/dev/null || true
  log "Express-бот: параметры записаны в .env (секрет не печатаю)"
}

# Контейнер по суффиксу имени: api / radius.
find_compose_ctr() {
  local kind="$1"
  local name=""
  if have_cmd podman; then
    name="$(podman ps --format '{{.Names}}' | grep -E "_${kind}(_|$)" | head -1 || true)"
  fi
  if [[ -z "$name" ]] && have_cmd docker; then
    name="$(docker ps --format '{{.Names}}' | grep -E "_${kind}(_|$)" | head -1 || true)"
  fi
  printf '%s' "$name"
}

ctr_exec() {
  local name="$1"
  shift
  if have_cmd podman && podman inspect "$name" >/dev/null 2>&1; then
    podman exec "$name" "$@"
    return
  fi
  if have_cmd docker && docker inspect "$name" >/dev/null 2>&1; then
    docker exec "$name" "$@"
    return
  fi
  return 1
}

# После up: radius должен получить 200 на /internal/radius/config, не 403.
smoke_internal_radius() {
  local rad code out api
  rad="$(find_compose_ctr radius)"
  if [[ -z "$rad" ]]; then
    die "smoke RADIUS: контейнер radius не найден"
  fi
  log "smoke: RADIUS → API /internal/radius/config ($rad)"
  out="$(ctr_exec "$rad" python3 -c "
import os
import httpx

def tok():
    p = '/run/mk2fa/host.env'
    if os.path.isfile(p):
        with open(p, encoding='utf-8', errors='replace') as f:
            for line in f:
                line = line.strip().lstrip('\ufeff')
                if line.startswith('INTERNAL_API_TOKEN='):
                    t = line.split('=', 1)[1].strip().strip(chr(34)).strip(chr(39))
                    if t:
                        return t
    return (os.environ.get('INTERNAL_API_TOKEN') or '').strip().strip(chr(34)).strip(chr(39))

t = tok()
api = (os.environ.get('API_URL') or 'http://127.0.0.1:8000').rstrip('/')
print('token_len', len(t), 'file', os.path.isfile('/run/mk2fa/host.env'), 'api', api)
r = httpx.get(
    api + '/internal/radius/config',
    headers={'X-Internal-Token': t, 'Authorization': 'Bearer ' + t},
    timeout=10,
    trust_env=False,
)
print(r.status_code)
# не печатать body: там shared_secret в открытом виде
try:
    j = r.json() if r.content else {}
except Exception:
    j = {}
sec = j.get('shared_secret') if isinstance(j, dict) else None
clients = j.get('allowed_clients') if isinstance(j, dict) else None
print(
    'ok_json', isinstance(j, dict),
    'secret_set', bool(sec),
    'secret_len', len(sec) if isinstance(sec, str) else 0,
    'clients', len(clients) if isinstance(clients, list) else 'n/a',
)
" 2>&1 || true)"
  log "smoke out: $out"
  code="$(printf '%s\n' "$out" | grep -E '^[0-9]{3}$' | tail -1 || true)"
  if [[ "$code" == "200" ]]; then
    log "smoke RADIUS→API: 200 (secret не выводим)"
    return 0
  fi
  api="$(find_compose_ctr api)"
  if [[ -n "$api" ]]; then
    log "smoke fail HTTP ${code:-нет}: длины/sha256 (не секрет)"
    ctr_exec "$api" python -c "
import os, hashlib
from pathlib import Path
from app.config import settings
from app.internal_token import expected_internal_token
a = os.environ.get('INTERNAL_API_TOKEN') or ''
b = settings.internal_api_token or ''
c = expected_internal_token()
def h(x):
    x = (x or '').strip().strip(chr(34)).strip(chr(39))
    return '%s sha=%s' % (len(x), hashlib.sha256(x.encode()).hexdigest()[:12])
print('env', h(a))
print('settings', h(b))
print('expected', h(c))
print('host.env', Path('/run/mk2fa/host.env').is_file())
" || true
  fi
  die "smoke RADIUS→API: HTTP ${code:-нет ответа} (нужен 200)"
}

wait_health() {
  local url="${1:-https://127.0.0.1/health}"
  local i
  log "ждём health: $url"
  for i in $(seq 1 60); do
    if curl -skf "$url" >/dev/null 2>&1; then
      log "health OK (${i}s)"
      return 0
    fi
    # fallback API
    if curl -sf "http://127.0.0.1:8000/health" >/dev/null 2>&1; then
      log "API health OK (${i}s)"
      return 0
    fi
    sleep 2
  done
  die "health не поднялся за ~120с. Смотри: podman-compose -f ${REPO_ROOT}/docker-compose.yml logs"
}

compose_down() {
  compose down "$@" || true
}

compose_up_build() {
  # Полный down+up — иначе на lab новый образ api часто не подхватывается
  log "podman/docker compose: down, затем build + up (первая сборка тянет docker.io, минуты, вывод без буфера)"
  compose down || true
  # Один build ./api (worker/otp/beat берут localhost/mk2fa-api) — иначе 4 параллельных COMMIT и Prepare images failed
  log "podman/docker compose: build api, затем radius, web, express-bot (по очереди — меньше гонок/RAM)"
  compose build api
  compose build radius
  compose build web
  compose build express-bot
  log "podman/docker compose: up -d"
  compose up -d
}

alembic_upgrade() {
  local cname
  # типичные имена: 2fa_api_1, mk2fa_api_1, own2fa_api_1 (legacy)
  for cname in "${COMPOSE_PROJECT_NAME}_api_1" "2fa_api_1" "mk2fa_api_1" "own2fa_api_1"; do
    if have_cmd podman && podman inspect "$cname" >/dev/null 2>&1; then
      log "alembic upgrade head в $cname"
      podman exec "$cname" alembic upgrade head || warn "alembic в $cname не прошёл"
      return 0
    fi
    if have_cmd docker && docker inspect "$cname" >/dev/null 2>&1; then
      log "alembic upgrade head в $cname"
      docker exec "$cname" alembic upgrade head || warn "alembic в $cname не прошёл"
      return 0
    fi
  done
  # поиск по имени
  if have_cmd podman; then
    cname="$(podman ps --format '{{.Names}}' | grep -E '_api(_|$)' | head -1 || true)"
    if [[ -n "$cname" ]]; then
      podman exec "$cname" alembic upgrade head || true
      return 0
    fi
  fi
  warn "контейнер api не найден — миграции должны были пройти в entrypoint"
}

open_firewall_hint() {
  log "порты: TCP 80,443,8030 (Express-бот); UDP 1812 (RADIUS)"
  if have_cmd firewall-cmd; then
    if firewall-cmd --state >/dev/null 2>&1; then
      firewall-cmd --permanent --add-service=http --add-service=https >/dev/null || true
      firewall-cmd --permanent --add-port=1812/udp >/dev/null || true
      firewall-cmd --permanent --add-port=8030/tcp >/dev/null || true
      firewall-cmd --reload >/dev/null || true
      log "firewalld: http, https, 8030/tcp, 1812/udp открыты"
    else
      warn "firewalld не запущен — откройте 80/443/8030/tcp и 1812/udp сами"
    fi
  elif have_cmd ufw; then
    ufw allow 80/tcp >/dev/null 2>&1 || true
    ufw allow 443/tcp >/dev/null 2>&1 || true
    ufw allow 8030/tcp >/dev/null 2>&1 || true
    ufw allow 1812/udp >/dev/null 2>&1 || true
    log "ufw: 80, 443, 8030/tcp, 1812/udp"
  fi
}
