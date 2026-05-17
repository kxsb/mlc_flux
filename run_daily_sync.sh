#!/bin/bash

cd /opt/mlcflux-dev/app || exit 1

LOG_FILE="/opt/mlcflux-dev/logs/daily_sync.log"

{
  echo
  echo "=== $(date -u +%Y-%m-%dT%H:%M:%SZ) DAILY SYNC START ==="

  /opt/mlcflux-dev/venv/bin/python -m server.sync_transactions
  TRANSACTIONS_STATUS=$?

  /opt/mlcflux-dev/venv/bin/python -m server.sync_odoo_professional_enrichment
  ODOO_ENRICHMENT_STATUS=$?

  BALANCES_DATE_FROM="$(TZ=Europe/Paris date -d '2 days ago' +%F)"
  BALANCES_DATE_TO="$(TZ=Europe/Paris date +%F)"

  echo "=== $(date -u +%Y-%m-%dT%H:%M:%SZ) PROFESSIONAL ACTOR USER LINKS SYNC - ${BALANCES_DATE_FROM} -> ${BALANCES_DATE_TO} ==="

  /opt/mlcflux-dev/venv/bin/python -m server.sync_cyclos_professional_actor_user_links \
    --date-from "$BALANCES_DATE_FROM" \
    --date-to "$BALANCES_DATE_TO"
  PROFESSIONAL_LINKS_STATUS=$?

  echo "=== $(date -u +%Y-%m-%dT%H:%M:%SZ) INDIVIDUAL DAILY BALANCES SYNC - ${BALANCES_DATE_FROM} -> ${BALANCES_DATE_TO} ==="

  /opt/mlcflux-dev/venv/bin/python -m server.sync_cyclos_individual_daily_balances \
    --date-from "$BALANCES_DATE_FROM" \
    --date-to "$BALANCES_DATE_TO"
  INDIVIDUAL_BALANCES_STATUS=$?

  echo "=== $(date -u +%Y-%m-%dT%H:%M:%SZ) PROFESSIONAL DAILY BALANCES SYNC - ${BALANCES_DATE_FROM} -> ${BALANCES_DATE_TO} ==="

  /opt/mlcflux-dev/venv/bin/python -m server.sync_cyclos_professional_daily_balances \
    --date-from "$BALANCES_DATE_FROM" \
    --date-to "$BALANCES_DATE_TO"
  PROFESSIONAL_BALANCES_STATUS=$?

  echo "=== $(date -u +%Y-%m-%dT%H:%M:%SZ) DAILY SYNC END - transactions=${TRANSACTIONS_STATUS} odoo_enrichment=${ODOO_ENRICHMENT_STATUS} professional_links=${PROFESSIONAL_LINKS_STATUS} individual_balances=${INDIVIDUAL_BALANCES_STATUS} professional_balances=${PROFESSIONAL_BALANCES_STATUS} ==="

  if [ "$TRANSACTIONS_STATUS" -ne 0 ] || [ "$ODOO_ENRICHMENT_STATUS" -ne 0 ] || [ "$PROFESSIONAL_LINKS_STATUS" -ne 0 ] || [ "$INDIVIDUAL_BALANCES_STATUS" -ne 0 ] || [ "$PROFESSIONAL_BALANCES_STATUS" -ne 0 ]; then
    exit 1
  fi
} >> "$LOG_FILE" 2>&1
