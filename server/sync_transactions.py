from datetime import datetime, UTC
import argparse
from server import create_app
from server.database import init_db, get_connection
from server.services.cyclos_client import get_transactions
from server.utils.anonymizer import anonymize_transactions


def save_sync_state(status, message):
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
        "daily_sync",
        datetime.now(UTC).isoformat(),
        status,
        message,
    ))

    conn.commit()
    conn.close()


def insert_transactions(transactions):
    conn = get_connection()
    cur = conn.cursor()

    inserted = 0

    for tx in transactions:
        cur.execute("""
            INSERT OR IGNORE INTO transactions (
                transaction_number,
                cyclos_id,
                date,
                group_label,
                from_label,
                to_label,
                amount,
                type_label
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            tx.get("transactionNumber"),
            tx.get("id"),
            tx.get("date"),
            tx.get("group"),
            tx.get("from"),
            tx.get("to"),
            float(tx.get("amount")) if tx.get("amount") is not None else None,
            tx.get("type"),
        ))

        if cur.rowcount > 0:
            inserted += 1

    conn.commit()
    conn.close()

    return inserted

def run_sync(days=None, date_from=None, date_to=None):
    """
    Synchronise les transactions Cyclos vers SQLite.

    Sans argument :
    - comportement quotidien par défaut du client Cyclos, actuellement 48h.

    Avec arguments :
    - days=N
    - date_from=YYYY-MM-DD ou ISO
    - date_to=YYYY-MM-DD ou ISO
    """
    app = create_app()

    with app.app_context():
        init_db()

        raw_transactions = get_transactions(
            days=days,
            date_from=date_from,
            date_to=date_to,
        )
        safe_transactions = anonymize_transactions(raw_transactions)
        inserted = insert_transactions(safe_transactions)

        fetched = len(raw_transactions)

        save_sync_state(
            status="success",
            message=(
                f"{inserted} nouvelles transactions importées "
                f"sur {fetched} transactions récupérées"
            )
        )

        print(
            "SYNC OK - "
            f"{fetched} transactions récupérées, "
            f"{inserted} nouvelles transactions importées"
        )

        return {
            "fetched": fetched,
            "inserted": inserted,
        }


def parse_args():
    parser = argparse.ArgumentParser(
        description="Synchronise les transactions Cyclos vers la base SQLite MLCFlux."
    )

    period_group = parser.add_mutually_exclusive_group()

    period_group.add_argument(
        "--days",
        type=int,
        default=None,
        help="Nombre de jours glissants à récupérer depuis maintenant.",
    )

    period_group.add_argument(
        "--date-from",
        dest="date_from",
        type=str,
        default=None,
        help="Date de début, au format YYYY-MM-DD ou ISO 8601.",
    )

    parser.add_argument(
        "--date-to",
        dest="date_to",
        type=str,
        default=None,
        help="Date de fin, au format YYYY-MM-DD ou ISO 8601. Requiert --date-from.",
    )

    args = parser.parse_args()

    if args.days is not None and args.days <= 0:
        parser.error("--days doit être un entier strictement positif.")

    if args.date_to and not args.date_from:
        parser.error("--date-to nécessite --date-from.")

    return args


if __name__ == "__main__":
    args = parse_args()

    try:
        run_sync(
            days=args.days,
            date_from=args.date_from,
            date_to=args.date_to,
        )
    except Exception as e:
        app = create_app()
        with app.app_context():
            init_db()
            save_sync_state(status="error", message=str(e))
        raise
