import sqlite3

from server import database


def test_geography_schema_is_neutral_and_idempotent(
    tmp_path,
    monkeypatch,
):
    db_path = tmp_path / "geography.db"

    monkeypatch.setattr(
        database,
        "get_db_path",
        lambda: db_path,
    )

    # Deux appels pour caractériser l'idempotence du DDL.
    database.init_geography_db()
    database.init_geography_db()

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    try:
        tables = {
            row["name"]
            for row in conn.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                """
            ).fetchall()
        }

        assert "geographic_areas" in tables
        assert "actor_geography" in tables

        area_columns = {
            row["name"]
            for row in conn.execute(
                "PRAGMA table_info(geographic_areas)"
            ).fetchall()
        }

        assert {
            "area_id",
            "area_type",
            "country_code",
            "area_code",
            "name",
            "parent_area_id",
            "latitude",
            "longitude",
            "geometry_kind",
            "geometry_geojson",
            "source_provider",
            "metadata_json",
        } <= area_columns

        actor_columns = {
            row["name"]
            for row in conn.execute(
                "PRAGMA table_info(actor_geography)"
            ).fetchall()
        }

        assert {
            "actor_ref",
            "actor_family",
            "mlc_territory_area_id",
            "postal_area_id",
            "commune_area_id",
            "street",
            "postal_code",
            "city",
            "latitude",
            "longitude",
            "precision_level",
            "confidence_level",
            "resolution_method",
            "resolution_sources_json",
            "resolution_trace_json",
            "resolved_at",
            "updated_at",
        } <= actor_columns

        # Le modèle géographique interne ne doit pas exposer
        # de colonne nommée d'après un provider.
        all_columns = area_columns | actor_columns

        assert not any(
            token in column.lower()
            for column in all_columns
            for token in (
                "lokavaluto",
                "cyclos",
                "odoo",
                "comchain",
            )
        )

        foreign_keys = {
            row["from"]: row["table"]
            for row in conn.execute(
                "PRAGMA foreign_key_list(actor_geography)"
            ).fetchall()
        }

        assert foreign_keys[
            "mlc_territory_area_id"
        ] == "geographic_areas"

        assert foreign_keys[
            "postal_area_id"
        ] == "geographic_areas"

        assert foreign_keys[
            "commune_area_id"
        ] == "geographic_areas"

    finally:
        conn.close()
