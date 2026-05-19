from __future__ import annotations

import json
import math
import sqlite3
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

from server.database import DB_PATH


DATA_DIR = Path(__file__).resolve().parents[1] / "data"
POSTAL_AREAS_PATH = DATA_DIR / "consumption_postal_areas.json"

DEFAULT_MIN_INDIVIDUALS = 5


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _clean_zip(value: Any) -> str | None:
    text = _clean_text(value)
    if not text:
        return None
    normalized = text.replace(" ", "")
    return normalized or None


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(numeric):
        return default
    return numeric


def _parse_iso_date(raw: str | None) -> date | None:
    text = _clean_text(raw)
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _available_balance_bounds(conn: sqlite3.Connection) -> dict[str, str | None]:
    individual_row = conn.execute(
        """
        SELECT
          MIN(balance_date) AS min_date,
          MAX(balance_date) AS max_date
        FROM cyclos_individual_daily_balances
        """
    ).fetchone()

    professional_row = conn.execute(
        """
        SELECT
          MIN(balance_date) AS min_date,
          MAX(balance_date) AS max_date
        FROM cyclos_professional_daily_balances
        """
    ).fetchone()

    min_candidates = [
        item
        for item in [
            individual_row["min_date"] if individual_row else None,
            professional_row["min_date"] if professional_row else None,
        ]
        if item
    ]
    max_candidates = [
        item
        for item in [
            individual_row["max_date"] if individual_row else None,
            professional_row["max_date"] if professional_row else None,
        ]
        if item
    ]

    return {
        "min_date": max(min_candidates) if min_candidates else None,
        "max_date": min(max_candidates) if max_candidates else None,
    }


def _resolve_period(
    conn: sqlite3.Connection,
    requested_start: str | None,
    requested_end: str | None,
) -> dict[str, str | None]:
    bounds = _available_balance_bounds(conn)

    min_date = bounds["min_date"]
    max_date = bounds["max_date"]

    parsed_start = _parse_iso_date(requested_start)
    parsed_end = _parse_iso_date(requested_end)

    effective_start = parsed_start.isoformat() if parsed_start else min_date
    effective_end = parsed_end.isoformat() if parsed_end else max_date

    if min_date and effective_start and effective_start < min_date:
        effective_start = min_date

    if max_date and effective_end and effective_end > max_date:
        effective_end = max_date

    if effective_start and effective_end and effective_start > effective_end:
        effective_start, effective_end = effective_end, effective_start

    return {
        "requested_start": _clean_text(requested_start),
        "requested_end": _clean_text(requested_end),
        "effective_start": effective_start,
        "effective_end": effective_end,
        "balance_min_date": min_date,
        "balance_max_date": max_date,
    }


def _iter_coordinates(coords: Any):
    if not isinstance(coords, list):
        return

    if (
        len(coords) >= 2
        and isinstance(coords[0], (int, float))
        and isinstance(coords[1], (int, float))
    ):
        yield float(coords[0]), float(coords[1])
        return

    for item in coords:
        yield from _iter_coordinates(item)


def _rough_centroid_from_feature_collection(
    feature_collection: dict[str, Any] | None,
) -> dict[str, float | int] | None:
    if not isinstance(feature_collection, dict):
        return None

    features = feature_collection.get("features")
    if not isinstance(features, list):
        return None

    points: list[tuple[float, float]] = []

    for feature in features:
        if not isinstance(feature, dict):
            continue

        geometry = feature.get("geometry")
        if not isinstance(geometry, dict):
            continue

        coordinates = geometry.get("coordinates")

        for longitude, latitude in _iter_coordinates(coordinates):
            if math.isfinite(longitude) and math.isfinite(latitude):
                points.append((longitude, latitude))

    if not points:
        return None

    return {
        "longitude": sum(lon for lon, _ in points) / len(points),
        "latitude": sum(lat for _, lat in points) / len(points),
        "vertex_count": len(points),
    }


@lru_cache(maxsize=1)
def _load_postal_centroids() -> dict[str, dict[str, Any]]:
    if not POSTAL_AREAS_PATH.exists():
        return {}

    try:
        payload = json.loads(POSTAL_AREAS_PATH.read_text())
    except Exception:
        return {}

    areas = payload.get("areas") if isinstance(payload, dict) else None
    if not isinstance(areas, dict):
        return {}

    centroids: dict[str, dict[str, Any]] = {}

    for postal_code, area in areas.items():
        if not isinstance(area, dict):
            continue

        cleaned_postal_code = _clean_zip(postal_code or area.get("postal_code"))
        if not cleaned_postal_code:
            continue

        centroid = _rough_centroid_from_feature_collection(
            area.get("feature_collection")
        )
        if not centroid:
            continue

        centroids[cleaned_postal_code] = {
            "postal_code": cleaned_postal_code,
            "longitude": centroid["longitude"],
            "latitude": centroid["latitude"],
            "vertex_count": centroid["vertex_count"],
            "feature_count": _safe_int(area.get("feature_count"), 0),
        }

    return centroids


def _table_rows(
    conn: sqlite3.Connection,
    *,
    start: str,
    end: str,
    min_individuals: int,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        WITH
        individual_zip AS (
          SELECT
            pseudonym,
            REPLACE(TRIM(zip), ' ', '') AS postal_code,
            MAX(NULLIF(TRIM(city), '')) AS city_label
          FROM odoo_individual_enrichment
          WHERE NULLIF(TRIM(zip), '') IS NOT NULL
          GROUP BY pseudonym, REPLACE(TRIM(zip), ' ', '')
        ),
        professional_zip AS (
          SELECT
            professional_ref,
            REPLACE(TRIM(COALESCE(cyclos_zip, zip)), ' ', '') AS postal_code,
            MAX(NULLIF(TRIM(COALESCE(cyclos_city, city)), '')) AS city_label
          FROM odoo_professional_enrichment
          WHERE NULLIF(TRIM(COALESCE(cyclos_zip, zip)), '') IS NOT NULL
          GROUP BY professional_ref, REPLACE(TRIM(COALESCE(cyclos_zip, zip)), ' ', '')
        ),
        eligible_zip AS (
          SELECT
            postal_code,
            MAX(city_label) AS city_label,
            COUNT(DISTINCT pseudonym) AS individual_count
          FROM individual_zip
          GROUP BY postal_code
          HAVING COUNT(DISTINCT pseudonym) >= ?
        ),
        professional_counts AS (
          SELECT
            postal_code,
            COUNT(DISTINCT professional_ref) AS professional_count
          FROM professional_zip
          GROUP BY postal_code
        ),
        individual_balances AS (
          SELECT
            iz.postal_code,
            SUM(CASE WHEN b.balance_date = ? THEN b.balance ELSE 0 END) AS individual_opening_balance,
            SUM(CASE WHEN b.balance_date = ? THEN b.balance ELSE 0 END) AS individual_closing_balance,
            COUNT(DISTINCT CASE WHEN b.balance_date = ? THEN b.pseudonym END) AS individual_opening_balance_users,
            COUNT(DISTINCT CASE WHEN b.balance_date = ? THEN b.pseudonym END) AS individual_closing_balance_users
          FROM individual_zip iz
          LEFT JOIN cyclos_individual_daily_balances b
            ON b.pseudonym = iz.pseudonym
           AND b.balance_date IN (?, ?)
          GROUP BY iz.postal_code
        ),
        professional_balances AS (
          SELECT
            pz.postal_code,
            SUM(CASE WHEN b.balance_date = ? THEN b.balance ELSE 0 END) AS professional_opening_balance,
            SUM(CASE WHEN b.balance_date = ? THEN b.balance ELSE 0 END) AS professional_closing_balance,
            COUNT(DISTINCT CASE WHEN b.balance_date = ? THEN b.professional_ref END) AS professional_opening_balance_users,
            COUNT(DISTINCT CASE WHEN b.balance_date = ? THEN b.professional_ref END) AS professional_closing_balance_users
          FROM professional_zip pz
          LEFT JOIN cyclos_professional_daily_balances b
            ON b.professional_ref = pz.professional_ref
           AND b.balance_date IN (?, ?)
          GROUP BY pz.postal_code
        ),
        individual_emissions AS (
          SELECT
            iz.postal_code,
            COUNT(DISTINCT CASE WHEN t.cyclos_id IS NOT NULL THEN iz.pseudonym END) AS individual_distinct_emitters,
            COUNT(t.cyclos_id) AS individual_emitted_tx_count,
            COALESCE(SUM(t.amount), 0) AS individual_emitted_volume
          FROM individual_zip iz
          LEFT JOIN transactions t
            ON t.from_label = iz.pseudonym
           AND substr(t.date, 1, 10) >= ?
           AND substr(t.date, 1, 10) <= ?
          GROUP BY iz.postal_code
        ),
        professional_transaction_emissions AS (
          SELECT
            substr(t.from_label, 1, 5) AS professional_ref,
            COUNT(t.cyclos_id) AS professional_emitted_tx_count,
            COALESCE(SUM(t.amount), 0) AS professional_emitted_volume
          FROM transactions t
          WHERE substr(t.date, 1, 10) >= ?
            AND substr(t.date, 1, 10) <= ?
            AND substr(t.from_label, 1, 5) LIKE 'P____'
          GROUP BY substr(t.from_label, 1, 5)
        ),
        professional_emissions AS (
          SELECT
            pz.postal_code,
            COUNT(DISTINCT CASE
              WHEN pte.professional_emitted_tx_count > 0
              THEN pz.professional_ref
            END) AS professional_distinct_emitters,
            COALESCE(SUM(pte.professional_emitted_tx_count), 0) AS professional_emitted_tx_count,
            COALESCE(SUM(pte.professional_emitted_volume), 0) AS professional_emitted_volume
          FROM professional_zip pz
          LEFT JOIN professional_transaction_emissions pte
            ON pte.professional_ref = pz.professional_ref
          GROUP BY pz.postal_code
        )
        SELECT
          ez.postal_code,
          ez.city_label,
          COALESCE(pc.professional_count, 0) AS professional_count,
          ez.individual_count,

          COALESCE(pb.professional_opening_balance, 0) AS professional_opening_balance,
          COALESCE(pb.professional_closing_balance, 0) AS professional_closing_balance,
          COALESCE(ib.individual_opening_balance, 0) AS individual_opening_balance,
          COALESCE(ib.individual_closing_balance, 0) AS individual_closing_balance,

          COALESCE(pb.professional_opening_balance_users, 0) AS professional_opening_balance_users,
          COALESCE(pb.professional_closing_balance_users, 0) AS professional_closing_balance_users,
          COALESCE(ib.individual_opening_balance_users, 0) AS individual_opening_balance_users,
          COALESCE(ib.individual_closing_balance_users, 0) AS individual_closing_balance_users,

          COALESCE(pe.professional_distinct_emitters, 0) AS professional_distinct_emitters,
          COALESCE(ie.individual_distinct_emitters, 0) AS individual_distinct_emitters,

          COALESCE(pe.professional_emitted_tx_count, 0) AS professional_emitted_tx_count,
          COALESCE(ie.individual_emitted_tx_count, 0) AS individual_emitted_tx_count,

          COALESCE(pe.professional_emitted_volume, 0) AS professional_emitted_volume,
          COALESCE(ie.individual_emitted_volume, 0) AS individual_emitted_volume,

          CASE
            WHEN COALESCE(pe.professional_distinct_emitters, 0) > 0
            THEN pe.professional_emitted_volume * 1.0 / pe.professional_distinct_emitters
            ELSE NULL
          END AS avg_emitted_volume_per_professional_emitter,

          CASE
            WHEN COALESCE(ie.individual_distinct_emitters, 0) > 0
            THEN ie.individual_emitted_volume * 1.0 / ie.individual_distinct_emitters
            ELSE NULL
          END AS avg_emitted_volume_per_individual_emitter,

          CASE
            WHEN COALESCE(pe.professional_distinct_emitters, 0) > 0
            THEN pe.professional_emitted_tx_count * 1.0 / pe.professional_distinct_emitters
            ELSE NULL
          END AS avg_emitted_tx_count_per_professional_emitter,

          CASE
            WHEN COALESCE(ie.individual_distinct_emitters, 0) > 0
            THEN ie.individual_emitted_tx_count * 1.0 / ie.individual_distinct_emitters
            ELSE NULL
          END AS avg_emitted_tx_count_per_individual_emitter

        FROM eligible_zip ez
        LEFT JOIN professional_counts pc USING (postal_code)
        LEFT JOIN individual_balances ib USING (postal_code)
        LEFT JOIN professional_balances pb USING (postal_code)
        LEFT JOIN individual_emissions ie USING (postal_code)
        LEFT JOIN professional_emissions pe USING (postal_code)
        ORDER BY ez.individual_count DESC, ez.postal_code ASC
        """,
        (
            min_individuals,

            # individual_balances :
            # SUM ouverture, SUM clôture,
            # COUNT utilisateurs ouverture, COUNT utilisateurs clôture,
            # filtre IN(start, end)
            start,
            end,
            start,
            end,
            start,
            end,

            # professional_balances :
            # SUM ouverture, SUM clôture,
            # COUNT utilisateurs ouverture, COUNT utilisateurs clôture,
            # filtre IN(start, end)
            start,
            end,
            start,
            end,
            start,
            end,

            # individual_emissions
            start,
            end,

            # professional_emissions
            start,
            end,
        ),
    ).fetchall()

    return [
        {
            "postal_code": row["postal_code"],
            "city_label": row["city_label"],
            "professional_count": _safe_int(row["professional_count"]),
            "individual_count": _safe_int(row["individual_count"]),
            "professional_opening_balance": _safe_float(row["professional_opening_balance"]),
            "professional_closing_balance": _safe_float(row["professional_closing_balance"]),
            "individual_opening_balance": _safe_float(row["individual_opening_balance"]),
            "individual_closing_balance": _safe_float(row["individual_closing_balance"]),
            "professional_opening_balance_users": _safe_int(row["professional_opening_balance_users"]),
            "professional_closing_balance_users": _safe_int(row["professional_closing_balance_users"]),
            "individual_opening_balance_users": _safe_int(row["individual_opening_balance_users"]),
            "individual_closing_balance_users": _safe_int(row["individual_closing_balance_users"]),
            "professional_distinct_emitters": _safe_int(row["professional_distinct_emitters"]),
            "individual_distinct_emitters": _safe_int(row["individual_distinct_emitters"]),
            "professional_emitted_tx_count": _safe_int(row["professional_emitted_tx_count"]),
            "individual_emitted_tx_count": _safe_int(row["individual_emitted_tx_count"]),
            "professional_emitted_volume": _safe_float(row["professional_emitted_volume"]),
            "individual_emitted_volume": _safe_float(row["individual_emitted_volume"]),
            "avg_emitted_volume_per_professional_emitter": (
                None
                if row["avg_emitted_volume_per_professional_emitter"] is None
                else _safe_float(row["avg_emitted_volume_per_professional_emitter"])
            ),
            "avg_emitted_volume_per_individual_emitter": (
                None
                if row["avg_emitted_volume_per_individual_emitter"] is None
                else _safe_float(row["avg_emitted_volume_per_individual_emitter"])
            ),
            "avg_emitted_tx_count_per_professional_emitter": (
                None
                if row["avg_emitted_tx_count_per_professional_emitter"] is None
                else _safe_float(row["avg_emitted_tx_count_per_professional_emitter"])
            ),
            "avg_emitted_tx_count_per_individual_emitter": (
                None
                if row["avg_emitted_tx_count_per_individual_emitter"] is None
                else _safe_float(row["avg_emitted_tx_count_per_individual_emitter"])
            ),
        }
        for row in rows
    ]


def _heatmap_points(
    postal_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    centroids = _load_postal_centroids()
    points: list[dict[str, Any]] = []
    missing_geometry_postal_codes: list[str] = []

    for row in postal_rows:
        postal_code = row["postal_code"]
        centroid = centroids.get(postal_code)

        if not centroid:
            missing_geometry_postal_codes.append(postal_code)
            continue

        points.append(
            {
                "postal_code": postal_code,
                "city_label": row.get("city_label"),
                "longitude": centroid["longitude"],
                "latitude": centroid["latitude"],
                "weight": row["individual_count"],
                "individual_count": row["individual_count"],
                "professional_count": row["professional_count"],
            }
        )

    return points, missing_geometry_postal_codes


def get_user_postal_clusters(
    *,
    start: str | None = None,
    end: str | None = None,
    min_individuals: int = DEFAULT_MIN_INDIVIDUALS,
) -> dict[str, Any]:
    cleaned_min_individuals = max(1, _safe_int(min_individuals, DEFAULT_MIN_INDIVIDUALS))

    with _connect() as conn:
        period = _resolve_period(conn, start, end)

        effective_start = period["effective_start"]
        effective_end = period["effective_end"]

        if not effective_start or not effective_end:
            return {
                "status": "empty",
                "requested_period": {
                    "start": period["requested_start"],
                    "end": period["requested_end"],
                },
                "effective_period": {
                    "start": effective_start,
                    "end": effective_end,
                },
                "summary": {
                    "min_individuals": cleaned_min_individuals,
                    "postal_code_count": 0,
                    "heatmap_point_count": 0,
                },
                "heatmap_points": [],
                "postal_codes": [],
            }

        postal_rows = _table_rows(
            conn,
            start=effective_start,
            end=effective_end,
            min_individuals=cleaned_min_individuals,
        )

    heatmap_points, missing_geometry_postal_codes = _heatmap_points(postal_rows)

    summary = {
        "min_individuals": cleaned_min_individuals,
        "postal_code_count": len(postal_rows),
        "heatmap_point_count": len(heatmap_points),
        "missing_geometry_postal_code_count": len(missing_geometry_postal_codes),
        "missing_geometry_postal_codes": missing_geometry_postal_codes,
        "individual_count_included": sum(row["individual_count"] for row in postal_rows),
        "professional_count_included": sum(row["professional_count"] for row in postal_rows),
        "individual_emitter_count_included": sum(row["individual_distinct_emitters"] for row in postal_rows),
        "professional_emitter_count_included": sum(row["professional_distinct_emitters"] for row in postal_rows),
        "individual_opening_balance_total": sum(row["individual_opening_balance"] for row in postal_rows),
        "individual_closing_balance_total": sum(row["individual_closing_balance"] for row in postal_rows),
        "professional_opening_balance_total": sum(row["professional_opening_balance"] for row in postal_rows),
        "professional_closing_balance_total": sum(row["professional_closing_balance"] for row in postal_rows),
    }

    return {
        "status": "ok",
        "requested_period": {
            "start": period["requested_start"],
            "end": period["requested_end"],
        },
        "effective_period": {
            "start": effective_start,
            "end": effective_end,
        },
        "balance_bounds": {
            "min_date": period["balance_min_date"],
            "max_date": period["balance_max_date"],
        },
        "summary": summary,
        "heatmap_points": heatmap_points,
        "postal_codes": postal_rows,
    }
