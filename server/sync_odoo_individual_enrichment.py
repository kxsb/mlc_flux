from __future__ import annotations

import argparse
from collections import Counter
from datetime import UTC, datetime

from server import create_app
from server.database import get_connection, init_db
from server.services.odoo_individual_enrichment import (
    build_odoo_individual_enrichment_snapshot,
    replace_odoo_individual_enrichment,
)


SYNC_NAME = "odoo_individual_enrichment"


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


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Synchronise l'enrichissement territorial des particuliers "
            "via actor_user_links.json, Cyclos et Odoo."
        )
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help=(
            "Limite optionnelle du nombre de liens traités. "
            "À utiliser uniquement pour un test."
        ),
    )

    return parser.parse_args()


def _print_progress(event):
    stage = event.get("stage")

    if stage == "cyclos_user_progress":
        print(
            f"[Cyclos users] {event['done']}/{event['total']} profils parcourus...",
            flush=True,
        )
        return

    if stage == "odoo_chunk_start":
        print(
            f"[Odoo] lot {event['chunk_index']}/{event['chunk_count']} "
            f"— {event['ref_count']} ref(s) Uxxxx recherchée(s)...",
            flush=True,
        )
        return

    if stage == "odoo_chunk_done":
        print(
            f"[Odoo] lot {event['chunk_index']}/{event['chunk_count']} terminé "
            f"— {event['partner_count']} partenaire(s) retourné(s).",
            flush=True,
        )


def run_sync(limit=None):
    app = create_app()

    with app.app_context():
        init_db()

        snapshot = build_odoo_individual_enrichment_snapshot(
            progress_callback=_print_progress,
            limit=limit,
        )

        storage = replace_odoo_individual_enrichment(snapshot)

        stats = Counter(snapshot.get("stats") or {})
        matched = int(stats.get("matched") or 0)
        with_zip = 0
        with_city = 0
        with_coordinates = 0
        former_members = 0

        for item in snapshot.get("items") or []:
            if item.get("odoo_match_status") != "matched":
                continue
            with_zip += int(bool(item.get("has_zip")))
            with_city += int(bool(item.get("has_city")))
            with_coordinates += int(bool(item.get("has_coordinates")))
            former_members += int(bool(item.get("is_former_member")))

        message = (
            f"{storage['stored_rows']} ligne(s) individuelles stockée(s), "
            f"{matched} matchée(s) Odoo, "
            f"{with_zip} avec code postal, "
            f"{with_city} avec commune, "
            f"{with_coordinates} avec coordonnées."
        )

        save_sync_state(status="success", message=message)

        print()
        print("ODOO INDIVIDUAL ENRICHMENT SYNC OK")
        print(f"- liens actor↔user lus : {snapshot['source_link_count']}")
        print(f"- refs Uxxxx exploitables : {snapshot['member_ref_count']}")
        print(f"- lignes stockées : {storage['stored_rows']}")
        print(f"- matchs Odoo : {matched}")
        print(f"- avec code postal : {with_zip}")
        print(f"- avec commune : {with_city}")
        print(f"- avec coordonnées : {with_coordinates}")
        print(f"- anciens membres parmi les matchs : {former_members}")
        print()
        print("Statuts de raccordement :")
        for key in sorted(stats):
            print(f"- {key}: {stats[key]}")

        return {
            "stored_rows": storage["stored_rows"],
            "matched": matched,
            "with_zip": with_zip,
            "with_city": with_city,
            "with_coordinates": with_coordinates,
            "former_members": former_members,
            "stats": dict(stats),
        }


if __name__ == "__main__":
    args = parse_args()

    try:
        run_sync(limit=args.limit)
    except Exception as exc:
        app = create_app()
        with app.app_context():
            init_db()
            save_sync_state(status="error", message=str(exc))
        raise
