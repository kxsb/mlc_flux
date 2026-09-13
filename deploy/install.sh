#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

APP_DIR="/opt/mlcflux/app"
VENV_DIR="/opt/mlcflux/venv"
CONFIG_FILE="/etc/mlcflux/mlcflux.env"
RUN_USER="mlcflux"
RUN_GROUP="mlcflux"
PORT="8001"
DOMAIN=""
MLC_ID=""
GUNICORN_WORKERS="2"
RENDER_DIR=""
APPLY=0

usage() {
  cat <<'EOF'
Usage: deploy/install.sh --mlc-id ID --domain DOMAIN [options]

INSTALL001 phase 1 is render-first. By default it only renders deployment
artifacts for review and performs no privileged action.

Required:
  --mlc-id ID             Standalone MLC profile identifier.
  --domain DOMAIN         Public hostname for the Nginx template.

Options:
  --app-dir PATH          Existing application checkout (default: /opt/mlcflux/app).
  --venv-dir PATH         Python virtualenv path (default: /opt/mlcflux/venv).
  --config-file PATH      Runtime env file (default: /etc/mlcflux/mlcflux.env).
  --run-user USER         systemd service user (default: mlcflux).
  --run-group GROUP       systemd service group (default: mlcflux).
  --port PORT             Local Gunicorn port (default: 8001).
  --gunicorn-workers N    Gunicorn worker count (default: 2).
  --render-dir PATH       Render destination (default: temporary directory).
  --apply                 Install rendered infrastructure files on this host.
  -h, --help              Show this help.

--apply deliberately does NOT clone/update application code, create the service
account, enable timers, start services, request TLS certificates, or create the
first application administrator. Those operations remain explicit until the
release/install contract is frozen.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mlc-id) MLC_ID="${2:?missing value for --mlc-id}"; shift 2 ;;
    --domain) DOMAIN="${2:?missing value for --domain}"; shift 2 ;;
    --app-dir) APP_DIR="${2:?missing value for --app-dir}"; shift 2 ;;
    --venv-dir) VENV_DIR="${2:?missing value for --venv-dir}"; shift 2 ;;
    --config-file) CONFIG_FILE="${2:?missing value for --config-file}"; shift 2 ;;
    --run-user) RUN_USER="${2:?missing value for --run-user}"; shift 2 ;;
    --run-group) RUN_GROUP="${2:?missing value for --run-group}"; shift 2 ;;
    --port) PORT="${2:?missing value for --port}"; shift 2 ;;
    --gunicorn-workers) GUNICORN_WORKERS="${2:?missing value for --gunicorn-workers}"; shift 2 ;;
    --render-dir) RENDER_DIR="${2:?missing value for --render-dir}"; shift 2 ;;
    --apply) APPLY=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ -z "$MLC_ID" || -z "$DOMAIN" ]]; then
  echo "--mlc-id and --domain are required." >&2
  usage >&2
  exit 2
fi

if [[ ! "$PORT" =~ ^[0-9]+$ ]] || (( PORT < 1 || PORT > 65535 )); then
  echo "Invalid --port: $PORT" >&2
  exit 2
fi

if [[ ! "$GUNICORN_WORKERS" =~ ^[0-9]+$ ]] || (( GUNICORN_WORKERS < 1 )); then
  echo "Invalid --gunicorn-workers: $GUNICORN_WORKERS" >&2
  exit 2
fi

if [[ -z "$RENDER_DIR" ]]; then
  RENDER_DIR="$(mktemp -d -t mlcflux-install.XXXXXX)"
else
  mkdir -p "$RENDER_DIR"
fi

mkdir -p "$RENDER_DIR/systemd" "$RENDER_DIR/nginx"

SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
LOCATION_SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"

render_template() {
  local source="$1"
  local destination="$2"

  python3 - \
    "$source" "$destination" \
    "$APP_DIR" "$VENV_DIR" "$CONFIG_FILE" \
    "$RUN_USER" "$RUN_GROUP" "$PORT" "$DOMAIN" "$MLC_ID" \
    "$GUNICORN_WORKERS" "$SECRET_KEY" "$LOCATION_SECRET" <<'PY'
from pathlib import Path
import sys

(
    source,
    destination,
    app_dir,
    venv_dir,
    config_file,
    run_user,
    run_group,
    port,
    domain,
    mlc_id,
    gunicorn_workers,
    secret_key,
    location_secret,
) = sys.argv[1:]

replacements = {
    "@@APP_DIR@@": app_dir,
    "@@VENV_DIR@@": venv_dir,
    "@@CONFIG_FILE@@": config_file,
    "@@RUN_USER@@": run_user,
    "@@RUN_GROUP@@": run_group,
    "@@PORT@@": port,
    "@@DOMAIN@@": domain,
    "@@MLC_ID@@": mlc_id,
    "@@GUNICORN_WORKERS@@": gunicorn_workers,
    "@@SECRET_KEY@@": secret_key,
    "@@LOCATION_SECRET@@": location_secret,
}

text = Path(source).read_text(encoding="utf-8")
for token, value in replacements.items():
    text = text.replace(token, value)

unresolved = sorted({part for part in text.split() if "@@" in part})
if unresolved:
    raise SystemExit(f"Unresolved template token(s): {unresolved}")

Path(destination).write_text(text, encoding="utf-8")
PY
}

render_template "$SCRIPT_DIR/systemd/mlcflux.service.in" "$RENDER_DIR/systemd/mlcflux.service"
render_template "$SCRIPT_DIR/systemd/mlcflux-daily-sync.service.in" "$RENDER_DIR/systemd/mlcflux-daily-sync.service"
render_template "$SCRIPT_DIR/systemd/mlcflux-reconcile.service.in" "$RENDER_DIR/systemd/mlcflux-reconcile.service"
cp "$SCRIPT_DIR/systemd/mlcflux-daily-sync.timer" "$RENDER_DIR/systemd/mlcflux-daily-sync.timer"
cp "$SCRIPT_DIR/systemd/mlcflux-reconcile.timer" "$RENDER_DIR/systemd/mlcflux-reconcile.timer"
render_template "$SCRIPT_DIR/nginx/mlcflux.conf.in" "$RENDER_DIR/nginx/mlcflux.conf"
render_template "$SCRIPT_DIR/mlcflux.env.in" "$RENDER_DIR/mlcflux.env"
chmod 600 "$RENDER_DIR/mlcflux.env"

cat <<EOF
INSTALL001 render complete.

Rendered directory: $RENDER_DIR
Application path:   $APP_DIR
Virtualenv path:    $VENV_DIR
Runtime config:     $CONFIG_FILE
Service identity:   $RUN_USER:$RUN_GROUP
MLC profile:        $MLC_ID
Public domain:      $DOMAIN
Local port:         $PORT
Apply requested:    $APPLY
EOF

if (( APPLY == 0 )); then
  echo
  echo "No host changes were made. Review the rendered files before using --apply."
  exit 0
fi

if (( EUID != 0 )); then
  echo "--apply must be run as root." >&2
  exit 1
fi

if [[ ! -f "$APP_DIR/app.py" || ! -f "$APP_DIR/requirements.txt" ]]; then
  echo "Application checkout not found at $APP_DIR." >&2
  echo "INSTALL001 phase 1 does not clone or update application code." >&2
  exit 1
fi

if ! id "$RUN_USER" >/dev/null 2>&1; then
  echo "Service user does not exist: $RUN_USER" >&2
  echo "Create/select the service identity explicitly, then rerun --apply." >&2
  exit 1
fi

if ! getent group "$RUN_GROUP" >/dev/null 2>&1; then
  echo "Service group does not exist: $RUN_GROUP" >&2
  exit 1
fi

if [[ ! -x "$VENV_DIR/bin/python" ]]; then
  python3 -m venv "$VENV_DIR"
fi

"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/python" -m pip install -r "$APP_DIR/requirements.txt"

install -d -m 0755 "$(dirname "$CONFIG_FILE")"
if [[ ! -e "$CONFIG_FILE" ]]; then
  install -o root -g root -m 0600 "$RENDER_DIR/mlcflux.env" "$CONFIG_FILE"
else
  echo "Preserving existing runtime configuration: $CONFIG_FILE"
fi

install -o root -g root -m 0644 "$RENDER_DIR/systemd/mlcflux.service" /etc/systemd/system/mlcflux.service
install -o root -g root -m 0644 "$RENDER_DIR/systemd/mlcflux-daily-sync.service" /etc/systemd/system/mlcflux-daily-sync.service
install -o root -g root -m 0644 "$RENDER_DIR/systemd/mlcflux-daily-sync.timer" /etc/systemd/system/mlcflux-daily-sync.timer
install -o root -g root -m 0644 "$RENDER_DIR/systemd/mlcflux-reconcile.service" /etc/systemd/system/mlcflux-reconcile.service
install -o root -g root -m 0644 "$RENDER_DIR/systemd/mlcflux-reconcile.timer" /etc/systemd/system/mlcflux-reconcile.timer

if [[ -d /etc/nginx/sites-available && -d /etc/nginx/sites-enabled ]]; then
  install -o root -g root -m 0644 "$RENDER_DIR/nginx/mlcflux.conf" /etc/nginx/sites-available/mlcflux
  ln -sfn /etc/nginx/sites-available/mlcflux /etc/nginx/sites-enabled/mlcflux
else
  echo "Nginx sites-available/sites-enabled layout not found; Nginx template not installed." >&2
fi

systemctl daemon-reload

cat <<'EOF'

Infrastructure files installed, but nothing was enabled or started.

Before activation, validate at minimum:
  systemd-analyze verify /etc/systemd/system/mlcflux*.service /etc/systemd/system/mlcflux*.timer
  nginx -t

Then review /etc/mlcflux/mlcflux.env, provider credentials, profile metadata,
TLS, first-admin bootstrap, filesystem permissions and backup policy.
EOF
