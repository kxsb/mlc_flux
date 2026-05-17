from __future__ import annotations

import json
import math
import re
import sqlite3
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

from server.database import DB_PATH


PROFESSIONAL_REF_RE = re.compile(r"^P\d{4}$")
DEFAULT_MIN_USERS = 5
MAX_MIN_USERS = 50

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
POSTAL_AREAS_PATH = DATA_DIR / "consumption_postal_areas.json"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_professional_ref(value: str | None) -> str:
    ref = str(value or "").strip().upper()
    if not PROFESSIONAL_REF_RE.match(ref):
        raise ValueError(f"Référence professionnelle invalide : {value!r}")
    return ref


def _parse_iso_date(value: str | None, field_name: str) -> str | None:
    text = _clean_text(value)
    if not text:
        return None

    try:
        return date.fromisoformat(text).isoformat()
    except ValueError as exc:
        raise ValueError(
            f"Date invalide pour {field_name}: {value!r}. Format attendu : YYYY-MM-DD."
        ) from exc


def _clean_zip(value: Any) -> str | None:
    text = _clean_text(value)
    if not text:
        return None
    cleaned = text.replace(" ", "")
    return cleaned or None


def _resolve_period(
    conn: sqlite3.Connection,
    requested_start: str | None,
    requested_end: str | None,
) -> dict[str, str | None]:
    start = _parse_iso_date(requested_start, "start")
    end = _parse_iso_date(requested_end, "end")

    bounds = conn.execute(
        """
        SELECT
          MIN(SUBSTR(date, 1, 10)) AS min_date,
          MAX(SUBSTR(date, 1, 10)) AS max_date
        FROM transactions
        """
    ).fetchone()

    effective_start = start or (bounds["min_date"] if bounds else None)
    effective_end = end or (bounds["max_date"] if bounds else None)

    if effective_start and effective_end and effective_start > effective_end:
        raise ValueError(
            f"Période invalide : start={effective_start} est postérieur à end={effective_end}."
        )

    return {
        "requested_start": start,
        "requested_end": end,
        "effective_start": effective_start,
        "effective_end": effective_end,
        "min_date": bounds["min_date"] if bounds else None,
        "max_date": bounds["max_date"] if bounds else None,
    }


def _professional_center(
    conn: sqlite3.Connection,
    professional_ref: str,
) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT
          professional_ref,
          odoo_name,
          industry_name,
          detailed_activity,
          COALESCE(cyclos_zip, zip) AS zip,
          COALESCE(cyclos_city, city) AS city,
          cyclos_latitude AS latitude,
          cyclos_longitude AS longitude,
          geo_match_status
        FROM odoo_professional_enrichment
        WHERE professional_ref = ?
        """,
        (professional_ref,),
    ).fetchone()

    if not row:
        return {
            "professional_ref": professional_ref,
            "name": professional_ref,
            "industry_name": None,
            "detailed_activity": None,
            "zip": None,
            "city": None,
            "latitude": None,
            "longitude": None,
            "geo_match_status": None,
            "has_coordinates": False,
        }

    latitude = _safe_float(row["latitude"], default=float("nan"))
    longitude = _safe_float(row["longitude"], default=float("nan"))
    has_coordinates = math.isfinite(latitude) and math.isfinite(longitude)

    return {
        "professional_ref": row["professional_ref"],
        "name": _clean_text(row["odoo_name"]) or professional_ref,
        "industry_name": _clean_text(row["industry_name"]),
        "detailed_activity": _clean_text(row["detailed_activity"]),
        "zip": _clean_text(row["zip"]),
        "city": _clean_text(row["city"]),
        "latitude": latitude if has_coordinates else None,
        "longitude": longitude if has_coordinates else None,
        "geo_match_status": _clean_text(row["geo_match_status"]),
        "has_coordinates": has_coordinates,
    }


def _iter_coordinates(value: Any) -> Iterable[tuple[float, float]]:
    if not isinstance(value, list):
        return

    if (
        len(value) >= 2
        and isinstance(value[0], (int, float))
        and isinstance(value[1], (int, float))
    ):
        yield float(value[0]), float(value[1])
        return

    for item in value:
        yield from _iter_coordinates(item)


def _rough_centroid_from_feature_collection(feature_collection: Any) -> dict[str, float] | None:
    if not isinstance(feature_collection, dict):
        return None

    points: list[tuple[float, float]] = []

    for feature in feature_collection.get("features") or []:
        geometry = feature.get("geometry") or {}
        coordinates = geometry.get("coordinates")

        for longitude, latitude in _iter_coordinates(coordinates):
            if math.isfinite(longitude) and math.isfinite(latitude):
                points.append((longitude, latitude))

    if not points:
        return None

    return {
        "longitude": sum(lon for lon, _ in points) / len(points),
        "latitude": sum(lat for _, lat in points) / len(points),
    }


@lru_cache(maxsize=1)
def _load_postal_areas() -> dict[str, dict[str, Any]]:
    if not POSTAL_AREAS_PATH.exists():
        return {}

    try:
        payload = json.loads(POSTAL_AREAS_PATH.read_text())
    except (OSError, json.JSONDecodeError):
        return {}

    areas = payload.get("areas") if isinstance(payload, dict) else None
    if not isinstance(areas, dict):
        return {}

    cleaned: dict[str, dict[str, Any]] = {}

    for postal_code, area in areas.items():
        if not isinstance(area, dict):
            continue

        cleaned_postal_code = _clean_zip(postal_code or area.get("postal_code"))
        if not cleaned_postal_code:
            continue

        feature_collection = area.get("feature_collection")
        centroid = _rough_centroid_from_feature_collection(feature_collection)

        if not centroid:
            continue

        cleaned[cleaned_postal_code] = {
            "postal_code": cleaned_postal_code,
            "city_label": _clean_text(area.get("city_label")),
            "feature_collection": feature_collection,
            "longitude": centroid["longitude"],
            "latitude": centroid["latitude"],
        }

    return cleaned


def _period_sql(start: str | None, end: str | None) -> tuple[list[str], list[Any]]:
    clauses: list[str] = []
    params: list[Any] = []

    if start:
        clauses.append("SUBSTR(t.date, 1, 10) >= ?")
        params.append(start)

    if end:
        clauses.append("SUBSTR(t.date, 1, 10) <= ?")
        params.append(end)

    return clauses, params


def _individual_totals(
    conn: sqlite3.Connection,
    *,
    professional_ref: str,
    start: str | None,
    end: str | None,
) -> dict[str, Any]:
    date_clauses, date_params = _period_sql(start, end)

    where_parts = [
        "SUBSTR(TRIM(t.to_label), 1, 5) = ?",
        """(
          SUBSTR(TRIM(t.from_label), 1, 2) = 'U_'
          OR SUBSTR(TRIM(t.from_label), 1, 3) = 'UD_'
        )""",
    ]
    where_parts.extend(date_clauses)

    row = conn.execute(
        f"""
        SELECT
          COUNT(DISTINCT TRIM(t.from_label)) AS payer_count,
          COUNT(*) AS tx_count,
          COALESCE(SUM(t.amount), 0) AS volume
        FROM transactions t
        WHERE {" AND ".join(where_parts)}
        """,
        [professional_ref, *date_params],
    ).fetchone()

    return {
        "payer_count": _safe_int(row["payer_count"] if row else 0),
        "tx_count": _safe_int(row["tx_count"] if row else 0),
        "volume": _safe_float(row["volume"] if row else 0.0),
    }


def _individual_postal_rows(
    conn: sqlite3.Connection,
    *,
    professional_ref: str,
    start: str | None,
    end: str | None,
) -> list[dict[str, Any]]:
    date_clauses, date_params = _period_sql(start, end)

    where_parts = [
        "SUBSTR(TRIM(t.to_label), 1, 5) = ?",
        """(
          SUBSTR(TRIM(t.from_label), 1, 2) = 'U_'
          OR SUBSTR(TRIM(t.from_label), 1, 3) = 'UD_'
        )""",
        "NULLIF(TRIM(i.zip), '') IS NOT NULL",
    ]
    where_parts.extend(date_clauses)

    rows = conn.execute(
        f"""
        SELECT
          REPLACE(TRIM(i.zip), ' ', '') AS postal_code,
          MIN(NULLIF(TRIM(i.city), '')) AS city_label,
          COUNT(DISTINCT TRIM(t.from_label)) AS payer_count,
          COUNT(*) AS tx_count,
          COALESCE(SUM(t.amount), 0) AS volume
        FROM transactions t
        JOIN odoo_individual_enrichment i
          ON i.pseudonym = TRIM(t.from_label)
        WHERE {" AND ".join(where_parts)}
        GROUP BY REPLACE(TRIM(i.zip), ' ', '')
        ORDER BY volume DESC, payer_count DESC, postal_code ASC
        """,
        [professional_ref, *date_params],
    ).fetchall()

    return [
        {
            "postal_code": _clean_zip(row["postal_code"]),
            "city_label": _clean_text(row["city_label"]),
            "payer_count": _safe_int(row["payer_count"]),
            "tx_count": _safe_int(row["tx_count"]),
            "volume": _safe_float(row["volume"]),
        }
        for row in rows
        if _clean_zip(row["postal_code"])
    ]


def _professional_inbound_rows(
    conn: sqlite3.Connection,
    *,
    professional_ref: str,
    start: str | None,
    end: str | None,
) -> list[dict[str, Any]]:
    date_clauses, date_params = _period_sql(start, end)

    where_parts = [
        "SUBSTR(TRIM(t.to_label), 1, 5) = ?",
        "SUBSTR(TRIM(t.from_label), 1, 5) GLOB 'P[0-9][0-9][0-9][0-9]'",
        "SUBSTR(TRIM(t.from_label), 1, 5) NOT IN ('P0000', 'P9999')",
        "SUBSTR(TRIM(t.from_label), 1, 5) <> ?",
    ]
    where_parts.extend(date_clauses)

    rows = conn.execute(
        f"""
        SELECT
          SUBSTR(TRIM(t.from_label), 1, 5) AS professional_ref,
          COALESCE(NULLIF(TRIM(p.odoo_name), ''), SUBSTR(TRIM(t.from_label), 1, 5)) AS name,
          p.industry_name,
          p.detailed_activity,
          COALESCE(p.cyclos_zip, p.zip) AS zip,
          COALESCE(p.cyclos_city, p.city) AS city,
          p.cyclos_latitude AS latitude,
          p.cyclos_longitude AS longitude,
          p.geo_match_status,
          COUNT(*) AS tx_count,
          COALESCE(SUM(t.amount), 0) AS volume
        FROM transactions t
        LEFT JOIN odoo_professional_enrichment p
          ON p.professional_ref = SUBSTR(TRIM(t.from_label), 1, 5)
        WHERE {" AND ".join(where_parts)}
        GROUP BY SUBSTR(TRIM(t.from_label), 1, 5)
        ORDER BY volume DESC, tx_count DESC, professional_ref ASC
        """,
        [professional_ref, professional_ref, *date_params],
    ).fetchall()

    result: list[dict[str, Any]] = []

    for row in rows:
        latitude = _safe_float(row["latitude"], default=float("nan"))
        longitude = _safe_float(row["longitude"], default=float("nan"))
        has_coordinates = (
            _clean_text(row["geo_match_status"]) == "confirmed"
            and math.isfinite(latitude)
            and math.isfinite(longitude)
        )

        result.append({
            "professional_ref": row["professional_ref"],
            "name": _clean_text(row["name"]) or row["professional_ref"],
            "industry_name": _clean_text(row["industry_name"]),
            "detailed_activity": _clean_text(row["detailed_activity"]),
            "zip": _clean_text(row["zip"]),
            "city": _clean_text(row["city"]),
            "latitude": latitude if has_coordinates else None,
            "longitude": longitude if has_coordinates else None,
            "geo_match_status": _clean_text(row["geo_match_status"]),
            "has_coordinates": has_coordinates,
            "tx_count": _safe_int(row["tx_count"]),
            "volume": _safe_float(row["volume"]),
        })

    return result


def _share(part: float, whole: float) -> float | None:
    if whole <= 0:
        return None
    return part / whole


def get_professional_payment_basin_map(
    professional_ref: str,
    *,
    start: str | None = None,
    end: str | None = None,
    min_users: int = DEFAULT_MIN_USERS,
) -> dict[str, Any]:
    normalized_ref = _normalize_professional_ref(professional_ref)
    cleaned_min_users = max(1, min(MAX_MIN_USERS, _safe_int(min_users, DEFAULT_MIN_USERS)))

    with _connect() as conn:
        period = _resolve_period(conn, start, end)
        effective_start = period["effective_start"]
        effective_end = period["effective_end"]

        center = _professional_center(conn, normalized_ref)
        individual_totals = _individual_totals(
            conn,
            professional_ref=normalized_ref,
            start=effective_start,
            end=effective_end,
        )

        individual_postal_rows = _individual_postal_rows(
            conn,
            professional_ref=normalized_ref,
            start=effective_start,
            end=effective_end,
        )

        professional_rows = _professional_inbound_rows(
            conn,
            professional_ref=normalized_ref,
            start=effective_start,
            end=effective_end,
        )

    postal_areas = _load_postal_areas()

    visible_individual_sources: list[dict[str, Any]] = []
    hidden_below_threshold = {
        "source_count": 0,
        "payer_count": 0,
        "tx_count": 0,
        "volume": 0.0,
    }
    missing_postal_geometry = {
        "source_count": 0,
        "payer_count": 0,
        "tx_count": 0,
        "volume": 0.0,
        "postal_codes": [],
    }

    for row in individual_postal_rows:
        postal_code = row["postal_code"]
        area = postal_areas.get(postal_code or "")

        if row["payer_count"] < cleaned_min_users:
            hidden_below_threshold["source_count"] += 1
            hidden_below_threshold["payer_count"] += row["payer_count"]
            hidden_below_threshold["tx_count"] += row["tx_count"]
            hidden_below_threshold["volume"] += row["volume"]
            continue

        if not area:
            missing_postal_geometry["source_count"] += 1
            missing_postal_geometry["payer_count"] += row["payer_count"]
            missing_postal_geometry["tx_count"] += row["tx_count"]
            missing_postal_geometry["volume"] += row["volume"]
            missing_postal_geometry["postal_codes"].append(postal_code)
            continue

        visible_individual_sources.append({
            **row,
            "city_label": row["city_label"] or area.get("city_label"),
            "longitude": area["longitude"],
            "latitude": area["latitude"],
        })

    visible_professional_sources = [
        row for row in professional_rows if row["has_coordinates"]
    ]

    hidden_professional_sources = [
        row for row in professional_rows if not row["has_coordinates"]
    ]

    routes: list[dict[str, Any]] = []

    if center["has_coordinates"]:
        for source in visible_individual_sources:
            routes.append({
                "id": f"u-postal:{source['postal_code']}",
                "kind": "individual_postal",
                "source": source,
                "destination": center,
                "tx_count": source["tx_count"],
                "volume": source["volume"],
                "payer_count": source["payer_count"],
            })

        for source in visible_professional_sources:
            routes.append({
                "id": f"professional:{source['professional_ref']}",
                "kind": "professional_inbound",
                "source": source,
                "destination": center,
                "tx_count": source["tx_count"],
                "volume": source["volume"],
                "payer_count": 1,
            })

    visible_individual_payer_count = sum(
        source["payer_count"] for source in visible_individual_sources
    )
    visible_individual_tx_count = sum(
        source["tx_count"] for source in visible_individual_sources
    )
    visible_individual_volume = sum(
        source["volume"] for source in visible_individual_sources
    )

    visible_professional_tx_count = sum(
        source["tx_count"] for source in visible_professional_sources
    )
    visible_professional_volume = sum(
        source["volume"] for source in visible_professional_sources
    )

    professional_total_tx_count = sum(row["tx_count"] for row in professional_rows)
    professional_total_volume = sum(row["volume"] for row in professional_rows)

    visible_source_area_geojson = {
        source["postal_code"]: postal_areas[source["postal_code"]]["feature_collection"]
        for source in visible_individual_sources
        if source["postal_code"] in postal_areas
    }

    coverage = {
        "min_users": cleaned_min_users,
        "visible_route_count": len(routes),

        "individual_total_payer_count": individual_totals["payer_count"],
        "individual_total_tx_count": individual_totals["tx_count"],
        "individual_total_volume": individual_totals["volume"],

        "individual_visible_postal_source_count": len(visible_individual_sources),
        "individual_visible_payer_count": visible_individual_payer_count,
        "individual_visible_tx_count": visible_individual_tx_count,
        "individual_visible_volume": visible_individual_volume,
        "individual_visible_payer_share": _share(
            visible_individual_payer_count,
            individual_totals["payer_count"],
        ),
        "individual_visible_volume_share": _share(
            visible_individual_volume,
            individual_totals["volume"],
        ),

        "individual_hidden_below_threshold": hidden_below_threshold,
        "individual_missing_postal_geometry": missing_postal_geometry,

        "professional_total_source_count": len(professional_rows),
        "professional_total_tx_count": professional_total_tx_count,
        "professional_total_volume": professional_total_volume,
        "professional_visible_source_count": len(visible_professional_sources),
        "professional_visible_tx_count": visible_professional_tx_count,
        "professional_visible_volume": visible_professional_volume,
        "professional_missing_geometry_source_count": len(hidden_professional_sources),
        "professional_missing_geometry_tx_count": sum(
            row["tx_count"] for row in hidden_professional_sources
        ),
        "professional_missing_geometry_volume": sum(
            row["volume"] for row in hidden_professional_sources
        ),
    }

    status_detail = "ok"
    if not center["has_coordinates"]:
        status_detail = "missing_center_coordinates"

    return {
        "status": "ok",
        "status_detail": status_detail,
        "professional_ref": normalized_ref,
        "requested_period": {
            "start": period["requested_start"],
            "end": period["requested_end"],
        },
        "effective_period": {
            "start": effective_start,
            "end": effective_end,
        },
        "bounds": {
            "min_date": period["min_date"],
            "max_date": period["max_date"],
        },
        "center": center,
        "coverage": coverage,
        "geometry": {
            "visible_source_area_geojson": visible_source_area_geojson,
        },
        "individual_sources": visible_individual_sources,
        "professional_sources": visible_professional_sources,
        "routes": routes,
    }
