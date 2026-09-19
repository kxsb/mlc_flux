import json

from server import database
from server.services.professional_payment_basin_map import (
    _load_territory_basemap,
)


def test_territory_basemap_filters_and_deduplicates(
    tmp_path,
    monkeypatch,
):
    db_path = tmp_path / "basemap.db"

    monkeypatch.setattr(
        database,
        "get_db_path",
        lambda: db_path,
    )

    database.init_geography_db()

    conn = database.get_connection()

    try:
        timestamp = (
            "2026-01-01T00:00:00+00:00"
        )

        same_lyon_feature = {
            "type": "Feature",
            "properties": {
                "code": "69123",
                "nom": "Lyon",
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [4.80, 45.70],
                    [4.90, 45.70],
                    [4.90, 45.80],
                    [4.80, 45.80],
                    [4.80, 45.70],
                ]],
            },
        }

        outside_feature = {
            "type": "Feature",
            "properties": {
                "code": "38185",
                "nom": "Grenoble",
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [5.70, 45.10],
                    [5.80, 45.10],
                    [5.80, 45.20],
                    [5.70, 45.20],
                    [5.70, 45.10],
                ]],
            },
        }

        rows = [
            (
                "FR:postal:69001",
                "69001",
                same_lyon_feature,
            ),
            (
                "FR:postal:69002",
                "69002",
                same_lyon_feature,
            ),
            (
                "FR:postal:38000",
                "38000",
                outside_feature,
            ),
        ]

        for area_id, area_code, feature in rows:
            conn.execute(
                """
                INSERT INTO geographic_areas (
                    area_id,
                    area_type,
                    country_code,
                    area_code,
                    name,
                    geometry_kind,
                    geometry_geojson,
                    source_provider,
                    fetched_at,
                    updated_at
                )
                VALUES (
                    ?,
                    'postal_area',
                    'FR',
                    ?,
                    ?,
                    'test',
                    ?,
                    'test',
                    ?,
                    ?
                )
                """,
                (
                    area_id,
                    area_code,
                    area_code,
                    json.dumps({
                        "type":
                            "FeatureCollection",
                        "features": [
                            feature
                        ],
                    }),
                    timestamp,
                    timestamp,
                ),
            )

        conn.commit()

        territory = {
            "country_code": "FR",
            "postal_code_prefixes": [
                "69"
            ],
        }

        result = _load_territory_basemap(
            conn,
            territory,
        )

        assert (
            result["postal_area_count"]
            == 2
        )

        # Deux zones postales lyonnaises contiennent
        # le même contour communal.
        assert (
            result["raw_feature_count"]
            == 2
        )

        assert (
            result["feature_count"]
            == 1
        )

        features = (
            result[
                "feature_collection"
            ]["features"]
        )

        assert (
            features[0]["properties"]["code"]
            == "69123"
        )

    finally:
        conn.close()
