#!/usr/bin/env bash
set -Eeuo pipefail

APP="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -x "$APP/.venv/bin/python" ]; then
  PY="$APP/.venv/bin/python"
elif [ -x "$(dirname "$APP")/venv/bin/python" ]; then
  PY="$(dirname "$APP")/venv/bin/python"
else
  PY="python3"
fi

LOG_DIR="$APP/_sync_logs"
mkdir -p "$LOG_DIR"

STAMP="$(date -u +%Y%m%d_%H%M%S)"
LOG_FILE="$LOG_DIR/multi_daily_sync_${STAMP}.log"
JSON_FILE="$LOG_DIR/multi_daily_sync_${STAMP}.json"

DAYS="${SYNC_DAYS:-3}"
PROFESSIONAL_PROFILE_DAYS="${SYNC_PROFESSIONAL_PROFILE_DAYS:-3650}"
PROFESSIONAL_PROFILE_LIMIT="${SYNC_PROFESSIONAL_PROFILE_LIMIT:-none}"

{
  echo "=================================================================="
  echo "MLCFlux multi — daily sync"
  echo "started_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "app=$APP"
  echo "python=$PY"
  echo "days=$DAYS"
  echo "professional_profile_days=$PROFESSIONAL_PROFILE_DAYS"
  echo "professional_profile_limit=$PROFESSIONAL_PROFILE_LIMIT"
  echo "=================================================================="

  cd "$APP"

  "$PY" -m server.sync_all_instances \
    --mlc graine \
    --mlc gonette \
    --days "$DAYS" \
    --professional-profile-days "$PROFESSIONAL_PROFILE_DAYS" \
    --professional-profile-limit "$PROFESSIONAL_PROFILE_LIMIT" \
    --json-out "$JSON_FILE"

  echo
  echo "ended_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
} >> "$LOG_FILE" 2>&1

echo "Log : $LOG_FILE"
echo "JSON: $JSON_FILE"
