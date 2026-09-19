from __future__ import annotations

from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

import json
import sqlite3


RESOLUTION_METHOD = "historical_sqlite_identity_bridge"

RESOLUTION_SOURCES = (
    "historical_sqlite:odoo_individual_enrichment",
    "instance:actor_user_links",
    "runtime:user_mapping",
)


class IndividualGeographyMigrationError(RuntimeError):
    """Erreur de cohérence de la migration géographique U."""


def _clean(value):
    return str(value or "").strip()


def _normalize_postal_code(value):
    value = _clean(value)

    if not value:
        return None

    return value.replace(" ", "")


def _utc_now_iso():
    return datetime.now(UTC).isoformat(
        timespec="seconds"
    )


def load_exact_identity_bridge(
    *,
    actor_user_links_path,
    user_mapping_path,
):
    """
    Construit le pont historique exact :

        ancien pseudonyme enrichment
              ↓
        actor_user_links[actor.id]
              ↓
        user_mapping["actor:<actor.id>"]
              ↓
        pseudonyme transactionnel actuel

    Aucune heuristique actor/user n'est utilisée.
    """

    actor_user_links_path = Path(
        actor_user_links_path
    )

    user_mapping_path = Path(
        user_mapping_path
    )

    actor_payload = json.loads(
        actor_user_links_path.read_text(
            encoding="utf-8"
        )
    )

    links = actor_payload.get("links")

    if not isinstance(links, dict):
        raise IndividualGeographyMigrationError(
            "actor_user_links.json invalide : "
            "champ links absent ou non dictionnaire."
        )

    user_mapping = json.loads(
        user_mapping_path.read_text(
            encoding="utf-8"
        )
    )

    if not isinstance(user_mapping, dict):
        raise IndividualGeographyMigrationError(
            "user_mapping.json invalide."
        )

    old_to_new = {}
    new_to_old = {}

    missing_mapping = 0
    invalid_links = 0

    for actor_id, record in links.items():
        if not isinstance(record, dict):
            invalid_links += 1
            continue

        actor_id = _clean(actor_id)

        old_pseudonym = _clean(
            record.get("pseudonym")
        )

        if not actor_id or not old_pseudonym:
            invalid_links += 1
            continue

        new_pseudonym = _clean(
            user_mapping.get(
                f"actor:{actor_id}"
            )
        )

        if not new_pseudonym:
            missing_mapping += 1
            continue

        previous_new = old_to_new.get(
            old_pseudonym
        )

        if (
            previous_new is not None
            and previous_new != new_pseudonym
        ):
            raise IndividualGeographyMigrationError(
                "Pont non bijectif : "
                "un ancien pseudonyme conduit "
                "à plusieurs pseudonymes actuels."
            )

        previous_old = new_to_old.get(
            new_pseudonym
        )

        if (
            previous_old is not None
            and previous_old != old_pseudonym
        ):
            raise IndividualGeographyMigrationError(
                "Pont non bijectif : "
                "un pseudonyme actuel conduit "
                "à plusieurs anciens pseudonymes."
            )

        old_to_new[
            old_pseudonym
        ] = new_pseudonym

        new_to_old[
            new_pseudonym
        ] = old_pseudonym

    stats = {
        "actor_links": len(links),
        "exact_pairs": len(old_to_new),
        "missing_mapping": missing_mapping,
        "invalid_links": invalid_links,
    }

    return old_to_new, stats


def _load_current_u_actor_refs(conn):
    return {
        _clean(row["actor_ref"])
        for row in conn.execute("""
            SELECT DISTINCT
                TRIM(actor_ref) AS actor_ref
            FROM (
                SELECT
                    from_label AS actor_ref
                FROM transactions

                UNION ALL

                SELECT
                    to_label AS actor_ref
                FROM transactions
            )
            WHERE TRIM(actor_ref) LIKE 'U_%'
        """)
        if _clean(row["actor_ref"])
    }


def _load_postal_areas(conn):
    result = {}

    rows = conn.execute("""
        SELECT
            area_id,
            area_code
        FROM geographic_areas
        WHERE area_type = 'postal_area'
          AND NULLIF(
              TRIM(area_code),
              ''
          ) IS NOT NULL
    """).fetchall()

    for row in rows:
        postal_code = _normalize_postal_code(
            row["area_code"]
        )

        if not postal_code:
            continue

        existing = result.get(
            postal_code
        )

        if (
            existing is not None
            and existing != row["area_id"]
        ):
            raise IndividualGeographyMigrationError(
                "Référentiel postal ambigu pour "
                f"le code {postal_code}."
            )

        result[
            postal_code
        ] = row["area_id"]

    return result


def _resolve_territory_area_id(
    conn,
    territory_area_id=None,
):
    if territory_area_id:
        row = conn.execute("""
            SELECT
                area_id
            FROM geographic_areas
            WHERE area_id = ?
              AND area_type = 'mlc_territory'
        """, (
            territory_area_id,
        )).fetchone()

        if not row:
            raise IndividualGeographyMigrationError(
                "Territoire MLC explicitement demandé "
                "introuvable."
            )

        return row["area_id"]

    rows = conn.execute("""
        SELECT area_id
        FROM geographic_areas
        WHERE area_type = 'mlc_territory'
        ORDER BY area_id
    """).fetchall()

    if len(rows) != 1:
        raise IndividualGeographyMigrationError(
            "La résolution automatique exige exactement "
            "un geographic_area de type mlc_territory. "
            f"Trouvé : {len(rows)}."
        )

    return rows[0]["area_id"]


def build_individual_geography_migration_plan(
    conn,
    *,
    historical_db_path,
    actor_user_links_path,
    user_mapping_path,
    territory_area_id=None,
):
    """
    Construit un plan de migration sans écrire dans SQLite.

    La source historique n'est utilisée que pour récupérer
    la granularité territoriale.

    Les latitude / longitude individuelles sont
    volontairement ignorées.
    """

    bridge, bridge_stats = (
        load_exact_identity_bridge(
            actor_user_links_path=(
                actor_user_links_path
            ),
            user_mapping_path=(
                user_mapping_path
            ),
        )
    )

    current_u = (
        _load_current_u_actor_refs(
            conn
        )
    )

    postal_areas = (
        _load_postal_areas(
            conn
        )
    )

    territory_id = (
        _resolve_territory_area_id(
            conn,
            territory_area_id=(
                territory_area_id
            ),
        )
    )

    historical_db_path = Path(
        historical_db_path
    )

    if not historical_db_path.exists():
        raise IndividualGeographyMigrationError(
            "Base historique introuvable : "
            f"{historical_db_path}"
        )

    historical = sqlite3.connect(
        (
            f"file:"
            f"{historical_db_path.resolve()}"
            f"?mode=ro"
        ),
        uri=True,
    )

    historical.row_factory = sqlite3.Row

    try:
        source_rows = historical.execute("""
            SELECT
                pseudonym,
                odoo_match_status,
                NULLIF(
                    TRIM(zip),
                    ''
                ) AS zip,
                NULLIF(
                    TRIM(city),
                    ''
                ) AS city,
                fetched_at,
                source
            FROM odoo_individual_enrichment
        """).fetchall()

    finally:
        historical.close()

    items = []
    statuses = Counter()

    skipped_no_bridge = 0
    skipped_not_current = 0

    with_zip = 0
    with_area = 0
    outside_reference = 0
    without_zip = 0

    for source_row in source_rows:
        old_pseudonym = _clean(
            source_row["pseudonym"]
        )

        new_pseudonym = bridge.get(
            old_pseudonym
        )

        if not new_pseudonym:
            skipped_no_bridge += 1
            continue

        if new_pseudonym not in current_u:
            skipped_not_current += 1
            continue

        postal_code = (
            _normalize_postal_code(
                source_row["zip"]
            )
        )

        city = (
            _clean(
                source_row["city"]
            )
            or None
        )

        source_status = (
            _clean(
                source_row[
                    "odoo_match_status"
                ]
            )
            or "unknown"
        )

        statuses[
            source_status
        ] += 1

        postal_area_id = None

        if postal_code:
            with_zip += 1

            postal_area_id = (
                postal_areas.get(
                    postal_code
                )
            )

            if postal_area_id:
                with_area += 1
            else:
                outside_reference += 1
        else:
            without_zip += 1

        if postal_code:
            precision_level = (
                "postal_area"
            )
        else:
            precision_level = (
                "mlc_territory"
            )

        if (
            source_status == "matched"
            and postal_area_id
        ):
            confidence_level = "high"

        elif postal_code:
            confidence_level = "medium"

        else:
            confidence_level = "low"

        source_timestamp = (
            _clean(
                source_row["fetched_at"]
            )
            or _utc_now_iso()
        )

        trace = {
            "identity_bridge": (
                "actor_id_exact"
            ),
            "source_match_status": (
                source_status
            ),
            "postal_area_resolved": bool(
                postal_area_id
            ),
            "coordinates_imported": False,
        }

        sources = list(
            RESOLUTION_SOURCES
        )

        source_name = _clean(
            source_row["source"]
        )

        if source_name:
            sources.append(
                f"historical_source:{source_name}"
            )

        items.append({
            "actor_ref": new_pseudonym,
            "actor_family": "U",
            "mlc_territory_area_id": (
                territory_id
            ),
            "postal_area_id": (
                postal_area_id
            ),
            "commune_area_id": None,
            "street": None,
            "postal_code": (
                postal_code
            ),
            "city": city,
            "latitude": None,
            "longitude": None,
            "precision_level": (
                precision_level
            ),
            "confidence_level": (
                confidence_level
            ),
            "resolution_method": (
                RESOLUTION_METHOD
            ),
            "resolution_sources_json": (
                json.dumps(
                    sources,
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
            ),
            "resolution_trace_json": (
                json.dumps(
                    trace,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
            ),
            "resolved_at": (
                source_timestamp
            ),
            "updated_at": (
                source_timestamp
            ),
        })

    actor_refs = [
        item["actor_ref"]
        for item in items
    ]

    if len(actor_refs) != len(
        set(actor_refs)
    ):
        raise IndividualGeographyMigrationError(
            "Le plan contient plusieurs lignes "
            "pour un même actor_ref."
        )

    return {
        "items": items,
        "stats": {
            **bridge_stats,
            "source_rows": len(
                source_rows
            ),
            "current_u": len(
                current_u
            ),
            "migratable": len(
                items
            ),
            "with_zip": with_zip,
            "with_area": with_area,
            "outside_reference": (
                outside_reference
            ),
            "without_zip": without_zip,
            "skipped_no_bridge": (
                skipped_no_bridge
            ),
            "skipped_not_current": (
                skipped_not_current
            ),
            "statuses": dict(
                sorted(
                    statuses.items()
                )
            ),
            "territory_area_id": (
                territory_id
            ),
        },
    }


def apply_individual_geography_migration(
    conn,
    plan,
):
    """
    Matérialise le plan dans actor_geography.

    Protection importante :
    une résolution U provenant d'une source plus récente
    ou d'une autre méthode n'est jamais écrasée par
    cette migration historique.
    """

    items = plan.get("items") or []

    actor_refs = [
        item["actor_ref"]
        for item in items
    ]

    if not actor_refs:
        return {
            "written": 0,
            "existing_managed": 0,
        }

    existing_managed = 0

    owns_transaction = not conn.in_transaction
    savepoint_name = "geo_individual_migration"

    try:
        if owns_transaction:
            conn.execute("BEGIN")
        else:
            conn.execute(
                f"SAVEPOINT {savepoint_name}"
            )

        for item in items:
            existing = conn.execute("""
                SELECT
                    resolution_method
                FROM actor_geography
                WHERE actor_ref = ?
            """, (
                item["actor_ref"],
            )).fetchone()

            if existing:
                existing_method = _clean(
                    existing[
                        "resolution_method"
                    ]
                )

                if (
                    existing_method
                    and existing_method
                    != RESOLUTION_METHOD
                ):
                    raise (
                        IndividualGeographyMigrationError(
                            "Refus d'écraser une résolution "
                            "géographique U issue d'une autre "
                            "méthode."
                        )
                    )

                existing_managed += 1

            conn.execute("""
                INSERT INTO actor_geography (
                    actor_ref,
                    actor_family,
                    mlc_territory_area_id,
                    postal_area_id,
                    commune_area_id,
                    street,
                    postal_code,
                    city,
                    latitude,
                    longitude,
                    precision_level,
                    confidence_level,
                    resolution_method,
                    resolution_sources_json,
                    resolution_trace_json,
                    resolved_at,
                    updated_at
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?
                )
                ON CONFLICT(actor_ref)
                DO UPDATE SET
                    actor_family =
                        excluded.actor_family,
                    mlc_territory_area_id =
                        excluded.mlc_territory_area_id,
                    postal_area_id =
                        excluded.postal_area_id,
                    commune_area_id =
                        excluded.commune_area_id,
                    street =
                        excluded.street,
                    postal_code =
                        excluded.postal_code,
                    city =
                        excluded.city,
                    latitude =
                        excluded.latitude,
                    longitude =
                        excluded.longitude,
                    precision_level =
                        excluded.precision_level,
                    confidence_level =
                        excluded.confidence_level,
                    resolution_method =
                        excluded.resolution_method,
                    resolution_sources_json =
                        excluded.resolution_sources_json,
                    resolution_trace_json =
                        excluded.resolution_trace_json,
                    resolved_at =
                        excluded.resolved_at,
                    updated_at =
                        excluded.updated_at
            """, (
                item["actor_ref"],
                item["actor_family"],
                item[
                    "mlc_territory_area_id"
                ],
                item["postal_area_id"],
                item["commune_area_id"],
                item["street"],
                item["postal_code"],
                item["city"],
                item["latitude"],
                item["longitude"],
                item["precision_level"],
                item["confidence_level"],
                item["resolution_method"],
                item[
                    "resolution_sources_json"
                ],
                item[
                    "resolution_trace_json"
                ],
                item["resolved_at"],
                item["updated_at"],
            ))

        if owns_transaction:
            conn.commit()
        else:
            conn.execute(
                f"RELEASE SAVEPOINT {savepoint_name}"
            )

    except Exception:
        if owns_transaction:
            conn.rollback()
        else:
            conn.execute(
                f"ROLLBACK TO SAVEPOINT {savepoint_name}"
            )
            conn.execute(
                f"RELEASE SAVEPOINT {savepoint_name}"
            )
        raise

    return {
        "written": len(items),
        "existing_managed": (
            existing_managed
        ),
    }
