import json
import sqlite3

import pytest

from server.services.geography_individual_migration import (
    IndividualGeographyMigrationError,
    RESOLUTION_METHOD,
    apply_individual_geography_migration,
    build_individual_geography_migration_plan,
)


def make_current_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    conn.executescript("""
        CREATE TABLE transactions (
            transaction_number TEXT,
            from_label TEXT,
            to_label TEXT
        );

        CREATE TABLE geographic_areas (
            area_id TEXT PRIMARY KEY,
            area_type TEXT NOT NULL,
            area_code TEXT
        );

        CREATE TABLE actor_geography (
            actor_ref TEXT PRIMARY KEY,
            actor_family TEXT,
            mlc_territory_area_id TEXT,
            postal_area_id TEXT,
            commune_area_id TEXT,
            street TEXT,
            postal_code TEXT,
            city TEXT,
            latitude REAL,
            longitude REAL,
            precision_level TEXT,
            confidence_level TEXT,
            resolution_method TEXT,
            resolution_sources_json TEXT,
            resolution_trace_json TEXT,
            resolved_at TEXT,
            updated_at TEXT
        );
    """)

    conn.executemany("""
        INSERT INTO transactions (
            transaction_number,
            from_label,
            to_label
        )
        VALUES (?, ?, ?)
    """, [
        ("T1", "U_NewA", "P0001"),
        ("T2", "P0001", "U_NewB"),
    ])

    conn.executemany("""
        INSERT INTO geographic_areas (
            area_id,
            area_type,
            area_code
        )
        VALUES (?, ?, ?)
    """, [
        (
            "FR:mlc:test",
            "mlc_territory",
            "test",
        ),
        (
            "FR:postal:69007",
            "postal_area",
            "69007",
        ),
    ])

    return conn


def make_sources(tmp_path):
    historical = (
        tmp_path / "historical.db"
    )

    conn = sqlite3.connect(
        historical
    )

    conn.execute("""
        CREATE TABLE odoo_individual_enrichment (
            pseudonym TEXT PRIMARY KEY,
            odoo_match_status TEXT,
            zip TEXT,
            city TEXT,
            fetched_at TEXT,
            source TEXT
        )
    """)

    conn.executemany("""
        INSERT INTO odoo_individual_enrichment (
            pseudonym,
            odoo_match_status,
            zip,
            city,
            fetched_at,
            source
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """, [
        (
            "U_OldA",
            "matched",
            "69007",
            "Lyon",
            "2026-09-01T00:00:00+00:00",
            "legacy",
        ),
        (
            "U_OldB",
            "no_odoo_partner",
            None,
            None,
            "2026-09-01T00:00:00+00:00",
            "legacy",
        ),
    ])

    conn.commit()
    conn.close()

    actor_links = (
        tmp_path / "actor_user_links.json"
    )

    actor_links.write_text(
        json.dumps({
            "links": {
                "actor-a": {
                    "pseudonym": "U_OldA",
                    "user_id": "user-a",
                },
                "actor-b": {
                    "pseudonym": "U_OldB",
                    "user_id": "user-b",
                },
            }
        }),
        encoding="utf-8",
    )

    user_mapping = (
        tmp_path / "user_mapping.json"
    )

    user_mapping.write_text(
        json.dumps({
            "actor:actor-a": "U_NewA",
            "actor:actor-b": "U_NewB",
        }),
        encoding="utf-8",
    )

    return (
        historical,
        actor_links,
        user_mapping,
    )


def test_build_plan_uses_exact_actor_bridge(
    tmp_path,
):
    current = make_current_db()

    (
        historical,
        actor_links,
        user_mapping,
    ) = make_sources(tmp_path)

    plan = (
        build_individual_geography_migration_plan(
            current,
            historical_db_path=historical,
            actor_user_links_path=actor_links,
            user_mapping_path=user_mapping,
        )
    )

    assert plan["stats"]["exact_pairs"] == 2
    assert plan["stats"]["migratable"] == 2
    assert plan["stats"]["with_area"] == 1
    assert plan["stats"]["without_zip"] == 1

    rows = {
        item["actor_ref"]: item
        for item in plan["items"]
    }

    assert (
        rows["U_NewA"]["postal_area_id"]
        == "FR:postal:69007"
    )

    assert (
        rows["U_NewA"]["precision_level"]
        == "postal_area"
    )

    assert (
        rows["U_NewA"]["confidence_level"]
        == "high"
    )

    assert (
        rows["U_NewA"]["latitude"]
        is None
    )

    assert (
        rows["U_NewA"]["longitude"]
        is None
    )

    assert (
        rows["U_NewB"]["precision_level"]
        == "mlc_territory"
    )

    current.close()


def test_apply_is_idempotent(
    tmp_path,
):
    current = make_current_db()

    (
        historical,
        actor_links,
        user_mapping,
    ) = make_sources(tmp_path)

    plan = (
        build_individual_geography_migration_plan(
            current,
            historical_db_path=historical,
            actor_user_links_path=actor_links,
            user_mapping_path=user_mapping,
        )
    )

    first = (
        apply_individual_geography_migration(
            current,
            plan,
        )
    )

    second = (
        apply_individual_geography_migration(
            current,
            plan,
        )
    )

    count = current.execute("""
        SELECT COUNT(*)
        FROM actor_geography
        WHERE actor_family = 'U'
    """).fetchone()[0]

    assert first["written"] == 2
    assert second["written"] == 2
    assert second["existing_managed"] == 2
    assert count == 2

    current.close()


def test_apply_refuses_to_overwrite_other_source(
    tmp_path,
):
    current = make_current_db()

    (
        historical,
        actor_links,
        user_mapping,
    ) = make_sources(tmp_path)

    plan = (
        build_individual_geography_migration_plan(
            current,
            historical_db_path=historical,
            actor_user_links_path=actor_links,
            user_mapping_path=user_mapping,
        )
    )

    current.execute("""
        INSERT INTO actor_geography (
            actor_ref,
            actor_family,
            resolution_method
        )
        VALUES (
            'U_NewA',
            'U',
            'future_live_provider'
        )
    """)

    current.commit()

    with pytest.raises(
        IndividualGeographyMigrationError
    ):
        apply_individual_geography_migration(
            current,
            plan,
        )

    current.close()
