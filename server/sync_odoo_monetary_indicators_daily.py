from __future__ import annotations

import argparse
from datetime import UTC, date, datetime

from server import create_app
from server.database import get_connection, init_db
from server.services.odoo_monetary_indicators import (
    fetch_odoo_monetary_indicators_daily,
    upsert_odoo_monetary_indicators_daily,
)


SYNC_NAME = "odoo_monetary_indicators_daily"


def save_sync_state(status: str, message: str) -> None:
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO sync_state (sync_name, last_run_at, last_status, last_message)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(sync_name) DO UPDATE SET
            last_run_at=excluded.last_run_at,
            last_status=excluded.last_status,
            last_message=excluded.last_message
    """, (
        SYNC_NAME,
        datetime.now(UTC).isoformat(),
        status,
        message,
    ))

    conn.commit()
    conn.close()


def _parse_iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"Date invalide '{value}'. Format attendu : YYYY-MM-DD."
        ) from exc


def run_sync(date_from: date, date_to: date) -> dict:
    if date_from > date_to:
        raise ValueError(f"Période invalide : {date_from} > {date_to}")

    app = create_app()

    with app.app_context():
        init_db()

        snapshot = fetch_odoo_monetary_indicators_daily(
            date_from=date_from,
            date_to=date_to,
        )
        storage_result = upsert_odoo_monetary_indicators_daily(snapshot)

        message = (
            f"{storage_result['stored_rows']} snapshot(s) journalier(s) stocké(s) "
            f"du {storage_result['date_from']} au {storage_result['date_to']}"
        )

        save_sync_state(status="success", message=message)

        print(
            "ODOO MONETARY INDICATORS DAILY SYNC OK - "
            f"{storage_result['stored_rows']} jours stockés "
            f"du {storage_result['date_from']} au {storage_result['date_to']}"
        )

        return {
            "stored_rows": storage_result["stored_rows"],
            "date_from": storage_result["date_from"],
            "date_to": storage_result["date_to"],
            "fetched_at": storage_result["fetched_at"],
        }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Reconstruit et stocke les indicateurs monétaires Odoo "
            "jour par jour sur une période."
        )
    )

    parser.add_argument(
        "--date-from",
        required=True,
        type=_parse_iso_date,
        help="Date de début inclusive au format YYYY-MM-DD.",
    )

    parser.add_argument(
        "--date-to",
        required=True,
        type=_parse_iso_date,
        help="Date de fin inclusive au format YYYY-MM-DD.",
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    run_sync(
        date_from=args.date_from,
        date_to=args.date_to,
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        app = create_app()
        with app.app_context():
            init_db()
            save_sync_state(status="error", message=str(exc))
        raise
