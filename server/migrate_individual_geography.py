from __future__ import annotations

import argparse

from server.database import get_connection
from server.services.geography_individual_migration import (
    apply_individual_geography_migration,
    build_individual_geography_migration_plan,
)


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Migration ponctuelle de la géographie "
            "des particuliers vers actor_geography."
        )
    )

    parser.add_argument(
        "--historical-db",
        required=True,
    )

    parser.add_argument(
        "--actor-user-links",
        required=True,
    )

    parser.add_argument(
        "--user-mapping",
        required=True,
    )

    parser.add_argument(
        "--territory-area-id",
        default=None,
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Écrit dans actor_geography. "
            "Sans ce flag : dry-run."
        ),
    )

    args = parser.parse_args()

    conn = get_connection()

    try:
        plan = (
            build_individual_geography_migration_plan(
                conn,
                historical_db_path=(
                    args.historical_db
                ),
                actor_user_links_path=(
                    args.actor_user_links
                ),
                user_mapping_path=(
                    args.user_mapping
                ),
                territory_area_id=(
                    args.territory_area_id
                ),
            )
        )

        stats = plan["stats"]

        print()
        print("=== PLAN GEO U ===")

        for key in (
            "actor_links",
            "exact_pairs",
            "source_rows",
            "current_u",
            "migratable",
            "with_zip",
            "with_area",
            "outside_reference",
            "without_zip",
            "skipped_no_bridge",
            "skipped_not_current",
            "territory_area_id",
        ):
            print(
                f"{key:<24}: "
                f"{stats.get(key)}"
            )

        print(
            f"{'statuses':<24}: "
            f"{stats.get('statuses')}"
        )

        if not args.apply:
            print()
            print(
                "DRY-RUN — aucune écriture."
            )
            return

        result = (
            apply_individual_geography_migration(
                conn,
                plan,
            )
        )

        print()
        print("=== ÉCRITURE ===")

        print(
            "Lignes écrites :",
            result["written"],
        )

        print(
            "Lignes déjà gérées :",
            result["existing_managed"],
        )

    finally:
        conn.close()


if __name__ == "__main__":
    main()
