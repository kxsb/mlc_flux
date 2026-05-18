import argparse
from datetime import datetime, UTC

from server import create_app
from server.database import init_db, get_connection
from server.services.odoo_professional_enrichment import (
    extract_mlcflux_professional_refs,
    fetch_odoo_professional_enrichment,
    replace_odoo_professional_enrichment,
)


SYNC_NAME = "odoo_professional_enrichment"


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


def run_sync():
    """
    Rafraîchit le snapshot SQLite des enrichissements professionnels Odoo.

    Périmètre :
    - détecter les refs Pxxxx déjà présentes dans MLCFlux ;
    - les matcher avec res.partner.ref côté Odoo ;
    - stocker le snapshot d'enrichissement en SQLite.
    """
    app = create_app()

    with app.app_context():
        init_db()

        professional_refs = extract_mlcflux_professional_refs()
        snapshot = fetch_odoo_professional_enrichment(professional_refs)

        requested_count = len(snapshot["requested_refs"])
        matched_count = len(snapshot["matched"])
        unmatched_count = len(snapshot["unmatched_refs"])

        # Garde-fou : ne jamais vider le snapshot existant à cause
        # d'une réponse Odoo anormalement vide.
        if requested_count > 0 and matched_count == 0:
            raise RuntimeError(
                "Synchronisation Odoo interrompue : "
                f"{requested_count} références MLCFlux détectées, "
                "mais aucun professionnel Odoo matché."
            )

        storage_result = replace_odoo_professional_enrichment(snapshot)

        message = (
            f"{storage_result['professional_count']} professionnels enrichis depuis Odoo, "
            f"{storage_result['secondary_industry_count']} secteurs secondaires stockés, "
            f"{unmatched_count} références MLCFlux non matchées"
        )

        save_sync_state(status="success", message=message)

        print(
            "ODOO PROFESSIONAL ENRICHMENT SYNC OK - "
            f"{matched_count} professionnels matchés, "
            f"{storage_result['secondary_industry_count']} secteurs secondaires stockés, "
            f"{unmatched_count} références non matchées"
        )

        return {
            "requested": requested_count,
            "matched": matched_count,
            "unmatched": unmatched_count,
            "stored_professionals": storage_result["professional_count"],
            "stored_secondary_industries": storage_result["secondary_industry_count"],
        }


def build_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        description=(
            "Synchronise l’enrichissement professionnel Odoo "
            "à partir des références Pxxxx déjà présentes dans MLCFlux."
        )
    )


def main() -> None:
    build_parser().parse_args()
    run_sync()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        app = create_app()
        with app.app_context():
            init_db()
            save_sync_state(status="error", message=str(e))
        raise
