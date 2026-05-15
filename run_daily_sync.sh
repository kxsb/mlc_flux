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

  echo "=== $(date -u +%Y-%m-%dT%H:%M:%SZ) DAILY SYNC END - transactions=${TRANSACTIONS_STATUS} odoo_enrichment=${ODOO_ENRICHMENT_STATUS} ==="

  if [ "$TRANSACTIONS_STATUS" -ne 0 ] || [ "$ODOO_ENRICHMENT_STATUS" -ne 0 ]; then
    exit 1
  fi
} >> "$LOG_FILE" 2>&1
