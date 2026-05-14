#!/bin/bash
cd /opt/mlcflux-dev/app || exit 1
/opt/mlcflux-dev/venv/bin/python -m server.sync_transactions >> /opt/mlcflux-dev/logs/daily_sync.log 2>&1
