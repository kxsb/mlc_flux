from __future__ import annotations

import argparse
import json
import os
from datetime import date, timedelta

from server.services.cyclos_system_daily_balances import (
    sync_cyclos_system_daily_balances,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Synchronise les soldes quotidiens des comptes système Cyclos."
    )
    parser.add_argument("--mlc", default=os.environ.get("MLCFLUX_DEFAULT_MLC_ID") or "graine")
    parser.add_argument("--date-from", required=True)
    parser.add_argument("--date-to", required=True)
    args = parser.parse_args()

    os.environ["MLCFLUX_DEFAULT_MLC_ID"] = args.mlc

    result = sync_cyclos_system_daily_balances(
        mlc_id=args.mlc,
        date_from=args.date_from,
        date_to=args.date_to,
    )

    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
