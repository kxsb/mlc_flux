import json
import sqlite3

from server import database
from server.services.geography_resolver import (
    resolve_professional_geography_from_enrichment,
)


def test_professional_geography_resolution_is_neutral_and_idempotent(
    tmp_path,
    monkeypatch,
):
    db_path = tmp_path / "geography.db"

    monkeypatch.setattr(
        database,
        "get_db_path",
        lambda: db_path,
    )

    database.init_professional_enrichment_db()
    database.init_geography_db()

    conn = database.get_connection()

    try:
        conn.execute(
            """
            INSERT INTO geographic_areas (
                area_id,
                area_type,
                country_code,
                area_code,
                name,
                source_provider,
                fetched_at,
                updated_at
            )
            VALUES (
                'FR:mlc:gonette',
                'mlc_territory',
                'FR',
                'gonette',
                'Territoire test',
                'test',
                '2026-01-01T00:00:00+00:00',
                '2026-01-01T00:00:00+00:00'
            )
            """
        )

        conn.execute(
            """
            INSERT INTO geographic_areas (
                area_id,
                area_type,
                country_code,
                area_code,
                name,
                source_provider,
                fetched_at,
                updated_at
            )
            VALUES (
                'FR:postal:69007',
                'postal_area',
                'FR',
                '69007',
                'Lyon',
                'test',
                '2026-01-01T00:00:00+00:00',
                '2026-01-01T00:00:00+00:00'
            )
            """
        )

        confirmed_raw = {
            "geo_match_status": "confirmed",
            "geo_distance_meters": 8.0,
            "odoo_address": {
                "latitude": 45.75,
                "longitude": 4.84,
            },
            "legacy_cyclos_address": {
                "latitude": 45.750001,
                "longitude": 4.840001,
            },
        }

        mismatch_raw = {
            "geo_match_status": "mismatch",
            "geo_distance_meters": 2500.0,
            "odoo_address": {
                "latitude": 45.70,
                "longitude": 4.80,
            },
            "legacy_cyclos_address": {
                "latitude": 45.90,
                "longitude": 4.90,
            },
        }

        conn.execute(
            """
            INSERT INTO professional_enrichment (
                professional_ref,
                source_provider,
                street,
                zip,
                city,
                latitude,
                longitude,
                raw_safe_json,
                fetched_at,
                updated_at
            )
            VALUES (
                'P0001',
                'legacy_snapshot',
                '1 rue Test',
                '69007',
                'Lyon',
                45.75,
                4.84,
                ?,
                '2026-01-01T00:00:00+00:00',
                '2026-01-02T00:00:00+00:00'
            )
            """,
            (json.dumps(confirmed_raw),),
        )

        conn.execute(
            """
            INSERT INTO professional_enrichment (
                professional_ref,
                source_provider,
                street,
                zip,
                city,
                latitude,
                longitude,
                raw_safe_json,
                fetched_at,
                updated_at
            )
            VALUES (
                'P0002',
                'legacy_snapshot',
                '2 rue Test',
                '38300',
                'Bourgoin-Jallieu',
                45.70,
                4.80,
                ?,
                '2026-01-01T00:00:00+00:00',
                '2026-01-03T00:00:00+00:00'
            )
            """,
            (json.dumps(mismatch_raw),),
        )

        conn.execute(
            """
            INSERT INTO professional_enrichment (
                professional_ref,
                source_provider,
                street,
                zip,
                city,
                latitude,
                longitude,
                raw_safe_json,
                fetched_at,
                updated_at
            )
            VALUES (
                'P0003',
                'legacy_snapshot',
                '3 rue Test',
                '42670',
                'Ville test',
                NULL,
                NULL,
                ?,
                '2026-01-01T00:00:00+00:00',
                '2026-01-04T00:00:00+00:00'
            )
            """,
            (
                json.dumps({
                    "geo_match_status":
                        "no_cyclos_coordinates",
                }),
            ),
        )

        conn.commit()

    finally:
        conn.close()

    first = resolve_professional_geography_from_enrichment(
        "gonette"
    )

    assert first["resolved_count"] == 3
    assert first["precision_counts"] == {
        "address": 1,
        "exact_point": 2,
    }

    assert first["confidence_counts"] == {
        "high": 1,
        "low": 1,
        "medium": 1,
    }

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    try:
        rows_before = [
            tuple(row)
            for row in conn.execute(
                """
                SELECT *
                FROM actor_geography
                ORDER BY actor_ref
                """
            ).fetchall()
        ]

        p1 = conn.execute(
            """
            SELECT *
            FROM actor_geography
            WHERE actor_ref = 'P0001'
            """
        ).fetchone()

        assert p1["actor_family"] == "P"
        assert (
            p1["mlc_territory_area_id"]
            == "FR:mlc:gonette"
        )
        assert (
            p1["postal_area_id"]
            == "FR:postal:69007"
        )
        assert p1["precision_level"] == "exact_point"
        assert p1["confidence_level"] == "high"
        assert (
            p1["resolution_method"]
            == "cross_source_confirmed"
        )

        p2 = conn.execute(
            """
            SELECT *
            FROM actor_geography
            WHERE actor_ref = 'P0002'
            """
        ).fetchone()

        assert p2["postal_area_id"] is None
        assert p2["precision_level"] == "exact_point"
        assert p2["confidence_level"] == "low"

        p3 = conn.execute(
            """
            SELECT *
            FROM actor_geography
            WHERE actor_ref = 'P0003'
            """
        ).fetchone()

        assert p3["latitude"] is None
        assert p3["longitude"] is None
        assert p3["precision_level"] == "address"
        assert p3["confidence_level"] == "medium"

    finally:
        conn.close()

    # L'UPSERT doit être idempotent jusque dans le contenu.
    second = resolve_professional_geography_from_enrichment(
        "gonette"
    )

    assert second == first

    conn = sqlite3.connect(db_path)

    try:
        rows_after = [
            tuple(row)
            for row in conn.execute(
                """
                SELECT *
                FROM actor_geography
                ORDER BY actor_ref
                """
            ).fetchall()
        ]
    finally:
        conn.close()

    assert rows_after == rows_before
