from __future__ import annotations

import argparse
from datetime import UTC, datetime

from server import create_app
from server.database import get_connection, init_db
from server.services.cyclos_individual_daily_balances import (
    DailyBalanceBackfillAlreadyRunning,
    individual_balance_backfill_lock,
    run_daily_balance_backfill,
)


SYNC_NAME = "cyclos_individual_daily_balances"


def save_sync_state(status, message):
    conn = get_connection()
    conn.execute("PRAGMA busy_timeout = 30000")
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


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Archive les soldes quotidiens des particuliers depuis Cyclos "
            "via balances-history, par fenêtres résumables."
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
    parser.add_argument(
        "--limit-users",
        type=int,
        default=None,
        help="Limite optionnelle du nombre de particuliers traités, pour test.",
    )
    parser.add_argument(
        "--max-windows-per-user",
        type=int,
        default=None,
        help="Limite optionnelle du nombre de fenêtres traitées par utilisateur, pour test.",
    )
    parser.add_argument(
        "--request-pause-seconds",
        type=float,
        default=0.02,
        help="Pause légère entre requêtes Cyclos. Défaut : 0.02 seconde.",
    )

    return parser.parse_args()


def _print_progress(event):
    stage = event.get("stage")

    if stage == "subject_start":
        print(
            f"[{event['subject_index']:>3}/{event['subjects_total']}] "
            f"{event['pseudonym']} — démarrage",
            flush=True,
        )
        return

    if stage == "window_success":
        print(
            f"[{event['subject_index']:>3}/{event['subjects_total']}] "
            f"{event['pseudonym']} | "
            f"fenêtre {event['window_index']:>2}/{event['windows_per_subject']} "
            f"{event['window_date_from']}→{event['window_date_to']} | "
            f"OK {event['points_received']} pts | "
            f"global OK={event['global_windows_success']} "
            f"ERR={event['global_windows_error']} "
            f"SKIP={event['global_windows_skipped']}",
            flush=True,
        )
        return

    if stage == "window_skipped":
        print(
            f"[{event['subject_index']:>3}/{event['subjects_total']}] "
            f"{event['pseudonym']} | "
            f"fenêtre {event['window_index']:>2}/{event['windows_per_subject']} "
            f"{event['window_date_from']}→{event['window_date_to']} | "
            f"SKIP déjà success",
            flush=True,
        )
        return

    if stage == "window_error":
        print(
            f"[{event['subject_index']:>3}/{event['subjects_total']}] "
            f"{event['pseudonym']} | "
            f"fenêtre {event['window_index']:>2}/{event['windows_per_subject']} "
            f"{event['window_date_from']}→{event['window_date_to']} | "
            f"ERROR {event.get('error')} | "
            f"global OK={event['global_windows_success']} "
            f"ERR={event['global_windows_error']} "
            f"SKIP={event['global_windows_skipped']}",
            flush=True,
        )


def run_sync(
    *,
    date_from,
    date_to,
    limit_users=None,
    max_windows_per_user=None,
    request_pause_seconds=0.02,
):
    app = create_app()

    with app.app_context():
        init_db()

        with individual_balance_backfill_lock():
            start_message = (
                f"running — archive soldes journaliers "
                f"{date_from}→{date_to}"
            )
            save_sync_state(status="running", message=start_message)

            result = run_daily_balance_backfill(
                date_from=date_from,
                date_to=date_to,
                limit_users=limit_users,
                max_windows_per_user=max_windows_per_user,
                request_pause_seconds=request_pause_seconds,
                progress_callback=_print_progress,
            )

            message = (
                f"{result['windows_success']} fenêtre(s) OK, "
                f"{result['windows_error']} erreur(s), "
                f"{result['windows_skipped_success']} déjà présente(s), "
                f"{result['points_stored']} point(s) écrit(s) / upserté(s), "
                f"{result['subjects_total']} particulier(s) parcouru(s)."
            )

            final_status = "success" if result["windows_error"] == 0 else "partial_success"
            save_sync_state(status=final_status, message=message)

            print()
            print("CYCLOS INDIVIDUAL DAILY BALANCES SYNC TERMINEE")
            print(f"- période demandée : {date_from} → {date_to}")
            print(f"- particuliers parcourus : {result['subjects_total']}")
            print(f"- fenêtres / particulier : {result['windows_per_subject']}")
            print(f"- fenêtres candidates : {result['candidate_windows_total']}")
            print(f"- fenêtres OK : {result['windows_success']}")
            print(f"- fenêtres en erreur : {result['windows_error']}")
            print(f"- fenêtres déjà présentes : {result['windows_skipped_success']}")
            print(f"- points reçus : {result['points_received']}")
            print(f"- points écrits / upsertés : {result['points_stored']}")

            return result


if __name__ == "__main__":
    args = parse_args()

    try:
        run_sync(
            date_from=args.date_from,
            date_to=args.date_to,
            limit_users=args.limit_users,
            max_windows_per_user=args.max_windows_per_user,
            request_pause_seconds=args.request_pause_seconds,
        )
    except DailyBalanceBackfillAlreadyRunning as exc:
        app = create_app()
        with app.app_context():
            init_db()
            save_sync_state(status="already_running", message=str(exc))
        raise SystemExit(str(exc))
    except Exception as exc:
        app = create_app()
        with app.app_context():
            init_db()
            save_sync_state(status="error", message=str(exc))
        raise
