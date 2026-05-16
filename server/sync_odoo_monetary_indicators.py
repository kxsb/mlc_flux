from __future__ import annotations

import argparse
from datetime import UTC, datetime

from server import create_app
from server.database import get_connection, init_db
from server.services.odoo_monetary_indicators import (
    fetch_odoo_monetary_indicators,
    upsert_odoo_monetary_indicators,
)


SYNC_NAME = "odoo_monetary_indicators"


def save_sync_state(status: str, message: str) -> None:
    """
    Stocke l'état de la dernière synchronisation monétaire Odoo
    dans la table générique sync_state.
    """
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


def _normalize_years(years: list[int] | None, current_year: bool) -> list[int]:
    """
    Résout proprement les années demandées par la CLI.

    - --year peut être répété ;
    - --current-year ajoute l'année calendaire UTC courante ;
    - sans argument, on synchronise l'année courante uniquement.
    """
    normalized = set()

    for year in years or []:
        normalized.add(int(year))

    if current_year:
        normalized.add(datetime.now(UTC).year)

    if not normalized:
        normalized.add(datetime.now(UTC).year)

    return sorted(normalized)


def run_sync(years: list[int] | None = None, current_year: bool = False) -> dict:
    """
    Synchronise en SQLite les indicateurs monétaires Odoo
    pour une ou plusieurs années.
    """
    requested_years = _normalize_years(years, current_year)

    app = create_app()

    with app.app_context():
        init_db()

        stored = []

        for year in requested_years:
            snapshot = fetch_odoo_monetary_indicators(year)
            storage_result = upsert_odoo_monetary_indicators(snapshot)

            stored.append({
                "year": year,
                "gonettes_total_circulation": snapshot["gonettes_total_circulation"],
                "fetched_at": storage_result["fetched_at"],
            })

        year_labels = ", ".join(str(item["year"]) for item in stored)
        message = (
            f"{len(stored)} année(s) synchronisée(s) depuis Odoo : "
            f"{year_labels}"
        )

        save_sync_state(status="success", message=message)

        print(
            "ODOO MONETARY INDICATORS SYNC OK - "
            f"{len(stored)} année(s) stockée(s) : {year_labels}"
        )

        for item in stored:
            print(
                f"- {item['year']} : "
                f"{item['gonettes_total_circulation']:.2f} G au total "
                f"(fetched_at={item['fetched_at']})"
            )

        return {
            "years": requested_years,
            "stored": stored,
        }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Synchronise depuis Odoo les indicateurs annuels "
            "de masse monétaire et de fonds de garantie."
        )
    )

    parser.add_argument(
        "--year",
        dest="years",
        action="append",
        type=int,
        help=(
            "Année à synchroniser. "
            "L'option peut être répétée : --year 2024 --year 2025."
        ),
    )

    parser.add_argument(
        "--current-year",
        action="store_true",
        help="Ajoute l'année calendaire courante à la synchronisation.",
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    run_sync(
        years=args.years,
        current_year=args.current_year,
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
