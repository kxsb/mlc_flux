from __future__ import annotations

import json
import sqlite3
from typing import Any

from server.database import get_db_path
from server.mlc_context import get_active_mlc_id


REGISTRY_TABLE = "professional_economic_registry"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table'
          AND name = ?
        """,
        (table_name,),
    ).fetchone()
    return row is not None


def _active_mlc_id() -> str | None:
    return get_active_mlc_id(fallback_to_default=True)


def _json_load(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except Exception:
        return fallback


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    item["source_layers"] = _json_load(item.pop("source_layers_json", None), [])
    item["evidence"] = _json_load(item.pop("evidence_json", None), {})
    return item


def _unavailable_payload() -> dict[str, Any]:
    return {
        "available": False,
        "mlc_id": _active_mlc_id(),
        "reason": "professional_economic_registry table not found for active MLC",
        "summary": {
            "total": 0,
            "siret_exact_safe": 0,
            "siret_written": 0,
            "naf_usable": 0,
            "naf_code_written": 0,
            "naf_section_written": 0,
            "manual_review_required": 0,
        },
        "bucket_distribution": [],
    }


def get_professional_economic_registry_summary() -> dict[str, Any]:
    with _connect() as conn:
        if not _table_exists(conn, REGISTRY_TABLE):
            return _unavailable_payload()

        summary = dict(
            conn.execute(
                """
                SELECT
                    COUNT(*) AS total,
                    COALESCE(SUM(siret_exact_safe), 0) AS siret_exact_safe,
                    COALESCE(SUM(CASE WHEN siret IS NOT NULL AND siret <> '' THEN 1 ELSE 0 END), 0) AS siret_written,
                    COALESCE(SUM(naf_usable), 0) AS naf_usable,
                    COALESCE(SUM(CASE WHEN naf_code IS NOT NULL AND naf_code <> '' THEN 1 ELSE 0 END), 0) AS naf_code_written,
                    COALESCE(SUM(CASE WHEN naf_section IS NOT NULL AND naf_section <> '' THEN 1 ELSE 0 END), 0) AS naf_section_written,
                    COALESCE(SUM(manual_review_required), 0) AS manual_review_required
                FROM professional_economic_registry
                """
            ).fetchone()
        )

        bucket_distribution = [
            dict(row)
            for row in conn.execute(
                """
                SELECT
                    decision_bucket,
                    confidence_level,
                    COUNT(*) AS count
                FROM professional_economic_registry
                GROUP BY decision_bucket, confidence_level
                ORDER BY decision_bucket, confidence_level
                """
            ).fetchall()
        ]

        confidence_distribution = [
            dict(row)
            for row in conn.execute(
                """
                SELECT
                    confidence_level,
                    COUNT(*) AS count
                FROM professional_economic_registry
                GROUP BY confidence_level
                ORDER BY confidence_level
                """
            ).fetchall()
        ]

        return {
            "available": True,
            "mlc_id": _active_mlc_id(),
            "summary": summary,
            "bucket_distribution": bucket_distribution,
            "confidence_distribution": confidence_distribution,
        }


def get_professional_economic_naf_sections() -> dict[str, Any]:
    with _connect() as conn:
        if not _table_exists(conn, REGISTRY_TABLE):
            return {
                "available": False,
                "mlc_id": _active_mlc_id(),
                "reason": "professional_economic_registry table not found for active MLC",
                "sections": [],
                "unknown_or_unusable_count": 0,
            }

        sections = [
            dict(row)
            for row in conn.execute(
                """
                SELECT
                    naf_section,
                    naf_section_label,
                    COUNT(*) AS count,
                    COALESCE(SUM(CASE WHEN naf_code IS NOT NULL AND naf_code <> '' THEN 1 ELSE 0 END), 0) AS with_naf_code,
                    COALESCE(SUM(CASE WHEN siret IS NOT NULL AND siret <> '' THEN 1 ELSE 0 END), 0) AS with_exact_siret,
                    COALESCE(SUM(manual_review_required), 0) AS manual_review_required
                FROM professional_economic_registry
                WHERE naf_usable = 1
                  AND naf_section IS NOT NULL
                  AND naf_section <> ''
                GROUP BY naf_section, naf_section_label
                ORDER BY naf_section
                """
            ).fetchall()
        ]

        unknown_or_unusable_count = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM professional_economic_registry
            WHERE naf_usable = 0
               OR naf_section IS NULL
               OR naf_section = ''
            """
        ).fetchone()["count"]

        return {
            "available": True,
            "mlc_id": _active_mlc_id(),
            "sections": sections,
            "unknown_or_unusable_count": unknown_or_unusable_count,
        }



def get_professional_economic_naf_codes() -> dict[str, Any]:
    with _connect() as conn:
        if not _table_exists(conn, REGISTRY_TABLE):
            return {
                "available": False,
                "mlc_id": _active_mlc_id(),
                "reason": "professional_economic_registry table not found for active MLC",
                "codes": [],
                "unknown_or_unusable_count": 0,
            }

        label_table_available = _table_exists(conn, "naf_activity_labels")

        if label_table_available:
            codes = [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT
                        r.naf_code,
                        COALESCE(
                            NULLIF(MAX(r.naf_label), ''),
                            NULLIF(MAX(l.naf_label), ''),
                            ''
                        ) AS naf_label,
                        r.naf_section,
                        r.naf_section_label,
                        COUNT(*) AS count,
                        COALESCE(SUM(CASE WHEN r.siret IS NOT NULL AND r.siret <> '' THEN 1 ELSE 0 END), 0) AS with_exact_siret,
                        COALESCE(SUM(r.manual_review_required), 0) AS manual_review_required
                    FROM professional_economic_registry r
                    LEFT JOIN naf_activity_labels l
                      ON UPPER(REPLACE(TRIM(l.naf_code), ' ', '')) = UPPER(REPLACE(TRIM(r.naf_code), ' ', ''))
                    WHERE r.naf_usable = 1
                      AND r.naf_code IS NOT NULL
                      AND r.naf_code <> ''
                    GROUP BY r.naf_code, r.naf_section, r.naf_section_label
                    ORDER BY r.naf_section, r.naf_code
                    """
                ).fetchall()
            ]
        else:
            codes = [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT
                        naf_code,
                        COALESCE(NULLIF(MAX(naf_label), ''), '') AS naf_label,
                        naf_section,
                        naf_section_label,
                        COUNT(*) AS count,
                        COALESCE(SUM(CASE WHEN siret IS NOT NULL AND siret <> '' THEN 1 ELSE 0 END), 0) AS with_exact_siret,
                        COALESCE(SUM(manual_review_required), 0) AS manual_review_required
                    FROM professional_economic_registry
                    WHERE naf_usable = 1
                      AND naf_code IS NOT NULL
                      AND naf_code <> ''
                    GROUP BY naf_code, naf_section, naf_section_label
                    ORDER BY naf_section, naf_code
                    """
                ).fetchall()
            ]

        unknown_or_unusable_count = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM professional_economic_registry
            WHERE naf_usable = 0
               OR naf_code IS NULL
               OR naf_code = ''
            """
        ).fetchone()["count"]

        return {
            "available": True,
            "mlc_id": _active_mlc_id(),
            "codes": codes,
            "unknown_or_unusable_count": unknown_or_unusable_count,
        }

def get_professional_economic_record(professional_ref: str) -> dict[str, Any]:
    ref = str(professional_ref or "").strip()

    with _connect() as conn:
        if not _table_exists(conn, REGISTRY_TABLE):
            return {
                "available": False,
                "mlc_id": _active_mlc_id(),
                "found": False,
                "reason": "professional_economic_registry table not found for active MLC",
                "professional_ref": ref,
                "record": None,
            }

        row = conn.execute(
            """
            SELECT *
            FROM professional_economic_registry
            WHERE professional_ref = ?
            """,
            (ref,),
        ).fetchone()

        if row is None:
            return {
                "available": True,
                "mlc_id": _active_mlc_id(),
                "found": False,
                "professional_ref": ref,
                "record": None,
            }

        return {
            "available": True,
            "mlc_id": _active_mlc_id(),
            "found": True,
            "professional_ref": ref,
            "record": _row_to_dict(row),
        }
