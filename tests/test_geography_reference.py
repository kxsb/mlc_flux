import json
import sqlite3

from server import database
from server.services.geography_reference import (
    sync_geographic_areas_from_reference,
)


def test_geography_reference_import_is_idempotent(
    tmp_path,
    monkeypatch,
):
    db_path = tmp_path / "geography.db"
    reference_path = tmp_path / "postal.json"

    monkeypatch.setattr(
        database,
        "get_db_path",
        lambda: db_path,
    )

    database.init_geography_db()

    payload = {
        "schema_version": "test.v1",
        "generated_at": "2026-01-01T00:00:00+00:00",
        "mlc_id": "gonette",
        "territorial_scope": {
            "kind": "test_scope",
            "label": "Territoire test",
        },
        "source": {
            "provider": "geo.api.gouv.fr",
            "note": "test",
        },
        "area_count": 2,
        "areas": {
            "69001": {
                "postal_code": "69001",
                "city_label": "Lyon",
                "latitude": 45.76,
                "longitude": 4.83,
                "geometry_kind":
                    "commune_contours_by_postal_code",
                "feature_count": 1,
                "feature_collection": {
                    "type": "FeatureCollection",
                    "features": [],
                },
                "source": "geo.api.gouv.fr/communes",
            },
            "69100": {
                "postal_code": "69100",
                "city_label": "Villeurbanne",
                "latitude": 45.77,
                "longitude": 4.88,
                "geometry_kind":
                    "commune_contours_by_postal_code",
                "feature_count": 1,
                "feature_collection": {
                    "type": "FeatureCollection",
                    "features": [],
                },
                "source": "geo.api.gouv.fr/communes",
            },
        },
    }

    reference_path.write_text(
        json.dumps(payload),
        encoding="utf-8",
    )

    first = sync_geographic_areas_from_reference(
        "gonette",
        reference_path=reference_path,
    )

    second = sync_geographic_areas_from_reference(
        "gonette",
        reference_path=reference_path,
    )

    assert first["postal_area_count"] == 2
    assert second["postal_area_count"] == 2

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    try:
        rows = conn.execute(
            """
            SELECT *
            FROM geographic_areas
            ORDER BY area_id
            """
        ).fetchall()

        assert len(rows) == 3

        ids = {
            row["area_id"]
            for row in rows
        }

        assert "FR:mlc:gonette" in ids
        assert "FR:postal:69001" in ids
        assert "FR:postal:69100" in ids

        postal = conn.execute(
            """
            SELECT *
            FROM geographic_areas
            WHERE area_id = 'FR:postal:69001'
            """
        ).fetchone()

        assert postal["area_type"] == "postal_area"
        assert postal["country_code"] == "FR"
        assert postal["area_code"] == "69001"

        # Un territoire MLC est un périmètre fonctionnel,
        # pas le parent administratif du code postal.
        assert postal["parent_area_id"] is None

        assert (
            postal["geometry_kind"]
            == "commune_contours_by_postal_code"
        )

        assert (
            postal["source_provider"]
            == "geo.api.gouv.fr/communes"
        )

    finally:
        conn.close()
