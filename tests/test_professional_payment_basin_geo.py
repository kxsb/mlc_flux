import json

from server import database
from server.services.professional_payment_basin_map import (
    get_professional_payment_basin_map,
)


def test_payment_basin_uses_neutral_geography(
    tmp_path,
    monkeypatch,
):
    db_path = tmp_path / "geo.db"

    monkeypatch.setattr(
        database,
        "get_db_path",
        lambda: db_path,
    )

    database.init_db()
    database.init_professional_enrichment_db()
    database.init_geography_db()

    conn = database.get_connection()

    try:
        timestamp = (
            "2026-01-01T00:00:00+00:00"
        )

        territory_metadata = {
            "territorial_scope": {
                "postal_code_prefixes": [
                    "69"
                ],
                "outside_label":
                    "Hors territoire test",
            }
        }

        conn.execute(
            """
            INSERT INTO geographic_areas (
                area_id,
                area_type,
                country_code,
                area_code,
                name,
                source_provider,
                metadata_json,
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
                ?,
                ?,
                ?
            )
            """,
            (
                json.dumps(
                    territory_metadata
                ),
                timestamp,
                timestamp,
            ),
        )

        geometry = {
            "type":
                "FeatureCollection",
            "features": [],
        }

        conn.execute(
            """
            INSERT INTO geographic_areas (
                area_id,
                area_type,
                country_code,
                area_code,
                name,
                latitude,
                longitude,
                geometry_kind,
                geometry_geojson,
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
                45.74,
                4.84,
                'test_geometry',
                ?,
                'test',
                ?,
                ?
            )
            """,
            (
                json.dumps(geometry),
                timestamp,
                timestamp,
            ),
        )

        for ref, name in (
            ("P0001", "Pro cible"),
            ("P0002", "Pro payeur"),
        ):
            conn.execute(
                """
                INSERT INTO professional_enrichment (
                    professional_ref,
                    source_provider,
                    display_name,
                    fetched_at,
                    updated_at
                )
                VALUES (?, 'test', ?, ?, ?)
                """,
                (
                    ref,
                    name,
                    timestamp,
                    timestamp,
                ),
            )

        conn.execute(
            """
            INSERT INTO actor_geography (
                actor_ref,
                actor_family,
                mlc_territory_area_id,
                postal_area_id,
                postal_code,
                city,
                latitude,
                longitude,
                precision_level,
                confidence_level,
                resolution_method,
                resolved_at,
                updated_at
            )
            VALUES (
                'P0001',
                'P',
                'FR:mlc:gonette',
                'FR:postal:69007',
                '69007',
                'Lyon',
                45.75,
                4.85,
                'exact_point',
                'high',
                'test',
                ?,
                ?
            )
            """,
            (
                timestamp,
                timestamp,
            ),
        )

        conn.execute(
            """
            INSERT INTO actor_geography (
                actor_ref,
                actor_family,
                mlc_territory_area_id,
                postal_area_id,
                postal_code,
                city,
                latitude,
                longitude,
                precision_level,
                confidence_level,
                resolution_method,
                resolved_at,
                updated_at
            )
            VALUES (
                'P0002',
                'P',
                'FR:mlc:gonette',
                'FR:postal:69007',
                '69007',
                'Lyon',
                45.76,
                4.86,
                'exact_point',
                'medium',
                'test',
                ?,
                ?
            )
            """,
            (
                timestamp,
                timestamp,
            ),
        )

        conn.execute(
            """
            INSERT INTO actor_geography (
                actor_ref,
                actor_family,
                mlc_territory_area_id,
                postal_area_id,
                postal_code,
                city,
                precision_level,
                confidence_level,
                resolution_method,
                resolved_at,
                updated_at
            )
            VALUES (
                'U_TEST',
                'U',
                'FR:mlc:gonette',
                'FR:postal:69007',
                '69007',
                'Lyon',
                'postal_area',
                'high',
                'test',
                ?,
                ?
            )
            """,
            (
                timestamp,
                timestamp,
            ),
        )

        transactions = [
            (
                "TX1",
                "2026-01-05T12:00:00",
                "U_TEST",
                "P0001",
                10.0,
            ),
            (
                "TX2",
                "2026-01-06T12:00:00",
                "P0002",
                "P0001",
                20.0,
            ),
        ]

        for (
            number,
            tx_date,
            from_label,
            to_label,
            amount,
        ) in transactions:
            conn.execute(
                """
                INSERT INTO transactions (
                    transaction_number,
                    date,
                    from_label,
                    to_label,
                    amount
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    number,
                    tx_date,
                    from_label,
                    to_label,
                    amount,
                ),
            )

        conn.commit()

    finally:
        conn.close()

    payload = (
        get_professional_payment_basin_map(
            "P0001",
            start="2026-01-01",
            end="2026-01-31",
            min_users=1,
        )
    )

    assert payload["status"] == "ok"

    assert (
        payload["center"][
            "professional_ref"
        ]
        == "P0001"
    )

    assert (
        payload["center"][
            "has_coordinates"
        ]
        is True
    )

    assert (
        payload["center"][
            "confidence_level"
        ]
        == "high"
    )

    assert (
        payload["coverage"][
            "individual_total_payer_count"
        ]
        == 1
    )

    assert (
        payload["coverage"][
            "individual_visible_postal_source_count"
        ]
        == 1
    )

    assert (
        payload["coverage"][
            "professional_visible_source_count"
        ]
        == 1
    )

    kinds = {
        route["kind"]
        for route in payload["routes"]
    }

    assert "individual_postal" in kinds
    assert "professional_inbound" in kinds

    assert (
        "69007"
        in payload["geometry"][
            "visible_source_area_geojson"
        ]
    )
