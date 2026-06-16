from __future__ import annotations

import argparse
from datetime import datetime, UTC

from server import create_app
from server.database import get_connection, init_db
from server.services.cyclos_actor_user_links import (
    sync_actor_user_links,
)


SYNC_NAME = "cyclos_actor_user_links"


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
        SYNC_NAME,
        datetime.now(UTC).isoformat(),
        status,
        message,
    ))

    conn.commit()
    conn.close()


def _print_progress(event):
    stage = event.get("stage")

    if stage == "month_start":
        print(
            f"[{event['month_key']}] récupération Cyclos "
            f"{event['date_from']} → {event['date_to']}...",
            flush=True,
        )
        return

    if stage == "month_done":
        print(
            f"[{event['month_key']}] "
            f"{event['transactions_fetched']} tx | "
            f"{event['candidate_actor_count']} acteur(s) raccordable(s) | "
            f"{event['candidate_evidences']} preuve(s)",
            flush=True,
        )


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Synchronise le mapping technique actor.id ↔ user.id "
            "depuis les transactions Cyclos bulk."
        )
    )

    parser.add_argument(
        "--date-from",
        required=True,
        help="Date de début inclusive au format YYYY-MM-DD.",
    )
    parser.add_argument(
        "--date-to",
        required=True,
        help="Date de fin inclusive au format YYYY-MM-DD.",
    )

    return parser.parse_args()


def run_sync(date_from, date_to):
    app = create_app()

    with app.app_context():
        init_db()

        result = sync_actor_user_links(
            date_from=date_from,
            date_to=date_to,
            progress_callback=_print_progress,
        )

        message = (
            f"{result['stored_total']} lien(s) stocké(s) au total ; "
            f"{result['created']} créé(s), "
            f"{result['updated']} mis à jour ; "
            f"{result['candidate_actor_count']} acteur(s) raccordable(s) détecté(s) "
            f"sur {result['transactions_fetched']} transaction(s)."
        )

        save_sync_state(status="success", message=message)

        print()
        print("CYCLOS ACTOR USER LINKS SYNC OK")
        print(f"- période : {date_from} → {date_to}")
        print(f"- transactions vérifiées : {result['transactions_fetched']}")
        print(f"- acteurs raccordables détectés : {result['candidate_actor_count']}")
        print(f"- preuves actor↔user : {result['candidate_evidences']}")
        print(f"- liens créés : {result['created']}")
        print(f"- liens mis à jour : {result['updated']}")
        print(f"- liens stockés au total : {result['stored_total']}")
        print(f"- fichier : {result['output_path']}")

        return result


if __name__ == "__main__":
    args = parse_args()

    try:
        run_sync(
            date_from=args.date_from,
            date_to=args.date_to,
        )
    except Exception as exc:
        app = create_app()
        with app.app_context():
            init_db()
            save_sync_state(status="error", message=str(exc))
        raise
