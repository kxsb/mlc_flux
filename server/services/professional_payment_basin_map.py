from __future__ import annotations

import json
import math
import os
import re
import sqlite3
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

from server.database import get_db_path


PROFESSIONAL_REF_RE = re.compile(r"^P\d{4}$")
DEFAULT_MIN_USERS = 1
MAX_MIN_USERS = 50

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
POSTAL_AREAS_PATH = DATA_DIR / "consumption_postal_areas.json"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(get_db_path())
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



# PRO_BASIN001A_ADAPTIVE_MAP_PAYLOAD
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


def _first_text(*values: Any) -> str | None:
    for value in values:
        cleaned = _clean_text(value)
        if cleaned:
            return cleaned
    return None


def _finite_pair(latitude: Any, longitude: Any) -> tuple[float | None, float | None, bool]:
    lat = _safe_float(latitude, default=float("nan"))
    lon = _safe_float(longitude, default=float("nan"))
    has_coordinates = math.isfinite(lat) and math.isfinite(lon)
    return (
        lat if has_coordinates else None,
        lon if has_coordinates else None,
        has_coordinates,
    )


def _synthetic_source_area_feature_collection(source: dict[str, Any]) -> dict[str, Any] | None:
    latitude = _safe_float(source.get("latitude"), default=float("nan"))
    longitude = _safe_float(source.get("longitude"), default=float("nan"))

    if not math.isfinite(latitude) or not math.isfinite(longitude):
        return None

    payer_count = max(1, _safe_int(source.get("payer_count"), 1))
    radius_km = max(0.45, min(2.2, 0.45 + math.sqrt(payer_count) * 0.16))

    lat_delta = radius_km / 111.32
    cos_lat = max(0.25, math.cos(math.radians(latitude)))
    lon_delta = radius_km / (111.32 * cos_lat)

    points = []
    for index in range(28):
        angle = (2 * math.pi * index) / 28
        points.append([
            longitude + math.cos(angle) * lon_delta,
            latitude + math.sin(angle) * lat_delta,
        ])

    points.append(points[0])

    postal_code = _clean_text(source.get("postal_code"))

    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "postal_code": postal_code,
                    "city_label": _clean_text(source.get("city_label")),
                    "synthetic": True,
                    "source": "actor_map_locations_centroid_buffer",
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [points],
                },
            }
        ],
    }



# PRO_BASIN002A_SCOPE_OUTSIDE_AGGREGATE

def _payment_basin_active_mlc_id() -> str:
    """
    Résout l'instance MLC réellement active.

    Ordre volontaire :
    1. contexte HTTP multi-MLC : query string / session / g ;
    2. variables d'environnement : scripts, tests directs, tâches CLI ;
    3. fallback historique.
    """
    try:
        from flask import g, has_request_context, request, session

        if has_request_context():
            candidates = [
                request.args.get("mlc"),
                session.get("active_mlc_id"),
                session.get("pending_mlc_id"),
                getattr(g, "active_mlc_id", None),
                request.headers.get("X-MLC-Id"),
                request.headers.get("X-MLCFlux-MLC-Id"),
            ]

            for candidate in candidates:
                cleaned = str(candidate or "").strip()
                if cleaned:
                    return cleaned
    except Exception:
        pass

    return (
        os.environ.get("MLCFLUX_DEFAULT_MLC_ID")
        or os.environ.get("MLCFLUX_ACTIVE_MLC_ID")
        or "gonette"
    )


def _payment_basin_load_profile() -> dict[str, Any]:
    mlc_id = _payment_basin_active_mlc_id()
    profile_path = Path(__file__).resolve().parents[1] / "data" / "mlc_profiles" / f"{mlc_id}.json"

    try:
        return json.loads(profile_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _payment_basin_territorial_scope() -> dict[str, Any]:
    profile = _payment_basin_load_profile()
    scope = profile.get("territorial_scope")

    if isinstance(scope, dict):
        prefixes = [
            str(prefix).strip()
            for prefix in scope.get("postal_code_prefixes", [])
            if str(prefix).strip()
        ]
        if prefixes:
            result = dict(scope)
            result["postal_code_prefixes"] = prefixes
            return result

    mlc_id = _payment_basin_active_mlc_id()

    if mlc_id == "graine":
        return {
            "kind": "department_postal_prefixes",
            "label": "département de l’Hérault",
            "short_label": "34",
            "postal_code_prefixes": ["34"],
            "outside_label": "Hors département 34",
        }

    if mlc_id == "gonette":
        return {
            "kind": "department_postal_prefixes",
            "label": "département du Rhône",
            "short_label": "69",
            "postal_code_prefixes": ["69"],
            "outside_label": "Hors département 69",
        }

    return {
        "kind": "none",
        "label": "territoire principal",
        "short_label": "",
        "postal_code_prefixes": [],
        "outside_label": "Hors territoire",
    }


def _postal_code_in_payment_scope(postal_code: Any, scope: dict[str, Any]) -> bool:
    cleaned = _clean_zip(postal_code)
    prefixes = [
        str(prefix).strip()
        for prefix in (scope or {}).get("postal_code_prefixes", [])
        if str(prefix).strip()
    ]

    if not prefixes:
        return True

    # Si le périmètre local est défini mais que la source n'a pas de code postal
    # exploitable, elle ne doit pas faire planter le service : elle sort du
    # périmètre cartographique local et pourra être agrégée.
    if not cleaned:
        return False

    return any(cleaned.startswith(prefix) for prefix in prefixes)


def _split_sources_by_payment_scope(
    sources: list[dict[str, Any]],
    scope: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    in_scope = []
    outside_scope = []

    for source in sources:
        if _postal_code_in_payment_scope(source.get("postal_code") or source.get("zip"), scope):
            in_scope.append(source)
        else:
            outside_scope.append(source)

    return in_scope, outside_scope


def _outside_scope_anchor_coordinates(
    *,
    center: dict[str, Any],
    visible_sources: list[dict[str, Any]],
) -> tuple[float | None, float | None]:
    center_latitude, center_longitude, center_ok = _finite_pair(
        center.get("latitude"),
        center.get("longitude"),
    )

    if center_ok:
        # Point volontairement proche du bassin local : il représente un agrégat,
        # pas une localisation réelle des hors-département.
        return center_latitude, center_longitude - 0.075

    weighted_latitude = 0.0
    weighted_longitude = 0.0
    total_weight = 0

    for source in visible_sources:
        latitude, longitude, ok = _finite_pair(
            source.get("latitude"),
            source.get("longitude"),
        )
        if not ok:
            continue

        weight = max(1, _safe_int(source.get("payer_count") or source.get("tx_count"), 1))
        weighted_latitude += latitude * weight
        weighted_longitude += longitude * weight
        total_weight += weight

    if total_weight <= 0:
        return None, None

    return weighted_latitude / total_weight, weighted_longitude / total_weight


def _aggregate_outside_scope_sources(
    sources: list[dict[str, Any]],
    *,
    center: dict[str, Any],
    in_scope_sources: list[dict[str, Any]],
    scope: dict[str, Any],
    source_kind: str,
) -> dict[str, Any] | None:
    if not sources:
        return None

    latitude, longitude = _outside_scope_anchor_coordinates(
        center=center,
        visible_sources=[*in_scope_sources, *sources],
    )

    if latitude is None or longitude is None:
        return None

    outside_label = (
        _clean_text((scope or {}).get("outside_label"))
        or "Hors département"
    )

    details = []
    for source in sorted(
        sources,
        key=lambda item: (
            -_safe_float(item.get("volume")),
            -_safe_int(item.get("tx_count")),
            str(item.get("postal_code") or item.get("zip") or ""),
        ),
    ):
        details.append({
            "postal_code": _clean_text(source.get("postal_code") or source.get("zip")),
            "city_label": _clean_text(source.get("city_label") or source.get("city")),
            "professional_ref": _clean_text(source.get("professional_ref")),
            "name": _clean_text(source.get("name")),
            "payer_count": _safe_int(source.get("payer_count"), 0),
            "tx_count": _safe_int(source.get("tx_count"), 0),
            "volume": _safe_float(source.get("volume")),
        })

    aggregate = {
        "postal_code": None,
        "zip": None,
        "display_label": outside_label,
        "city_label": outside_label,
        "name": outside_label,
        "longitude": longitude,
        "latitude": latitude,
        "payer_count": sum(
            max(1, _safe_int(source.get("payer_count"), 0))
            for source in sources
        ),
        "tx_count": sum(_safe_int(source.get("tx_count"), 0) for source in sources),
        "volume": sum(_safe_float(source.get("volume")) for source in sources),
        "postal_source_count": len(sources),
        "is_outside_territory": True,
        "is_outside_scope": True,
        "outside_scope_label": outside_label,
        "outside_scope_details": details,
        "outside_scope_postal_codes": [
            value for value in sorted({
                _clean_text(source.get("postal_code") or source.get("zip"))
                for source in sources
                if _clean_text(source.get("postal_code") or source.get("zip"))
            })
        ],
        "source_kind": source_kind,
        "has_coordinates": True,
    }

    if source_kind == "professional":
        aggregate["professional_ref"] = "P_OUTSIDE_SCOPE"

    return aggregate


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
    location = None
    if _table_exists(conn, "actor_map_locations"):
        location = conn.execute(
            """
            SELECT
              actor_ref,
              postal_code,
              city,
              latitude,
              longitude,
              cartographiable,
              location_strategy,
              source_provider
            FROM actor_map_locations
            WHERE actor_ref = ?
            LIMIT 1
            """,
            (professional_ref,),
        ).fetchone()

    generic = None
    if _table_exists(conn, "professional_enrichment"):
        generic = conn.execute(
            """
            SELECT
              professional_ref,
              display_name,
              legal_name,
              industry_name,
              detailed_activity,
              short_description,
              zip,
              city,
              latitude,
              longitude
            FROM professional_enrichment
            WHERE professional_ref = ?
              AND (
                    cyclos_group_set LIKE 'B %'
                    OR LOWER(COALESCE(cyclos_group, '')) LIKE '%prestataire%'
                    OR actor_type_internal IN ('MonComptePro', 'compteProBillets')
              )
            LIMIT 1
            """,
            (professional_ref,),
        ).fetchone()

    legacy = None
    if _table_exists(conn, "odoo_professional_enrichment"):
        legacy = conn.execute(
            """
            SELECT
              professional_ref,
              odoo_name,
              industry_name,
              detailed_activity,
              COALESCE(cyclos_zip, zip) AS zip,
              COALESCE(cyclos_city, city) AS city,
              COALESCE(cyclos_latitude, latitude) AS latitude,
              COALESCE(cyclos_longitude, longitude) AS longitude,
              geo_match_status
            FROM odoo_professional_enrichment
            WHERE professional_ref = ?
            LIMIT 1
            """,
            (professional_ref,),
        ).fetchone()

    latitude = None
    longitude = None
    has_coordinates = False

    coordinate_candidates = []
    if location is not None and _safe_int(location["cartographiable"], 0) == 1:
        coordinate_candidates.append((location["latitude"], location["longitude"]))
    if generic is not None:
        coordinate_candidates.append((generic["latitude"], generic["longitude"]))
    if legacy is not None:
        coordinate_candidates.append((legacy["latitude"], legacy["longitude"]))

    for raw_latitude, raw_longitude in coordinate_candidates:
        latitude, longitude, has_coordinates = _finite_pair(raw_latitude, raw_longitude)
        if has_coordinates:
            break

    name = _first_text(
        generic["display_name"] if generic is not None else None,
        generic["legal_name"] if generic is not None else None,
        legacy["odoo_name"] if legacy is not None else None,
        professional_ref,
    )

    industry_name = _first_text(
        generic["industry_name"] if generic is not None else None,
        legacy["industry_name"] if legacy is not None else None,
    )

    detailed_activity = _first_text(
        generic["short_description"] if generic is not None else None,
        generic["detailed_activity"] if generic is not None else None,
        legacy["detailed_activity"] if legacy is not None else None,
    )

    zip_code = _first_text(
        location["postal_code"] if location is not None else None,
        generic["zip"] if generic is not None else None,
        legacy["zip"] if legacy is not None else None,
    )

    city = _first_text(
        location["city"] if location is not None else None,
        generic["city"] if generic is not None else None,
        legacy["city"] if legacy is not None else None,
    )

    geo_match_status = _first_text(
        location["location_strategy"] if location is not None else None,
        legacy["geo_match_status"] if legacy is not None else None,
        "actor_map_location" if has_coordinates else None,
    )

    return {
        "professional_ref": professional_ref,
        "name": name or professional_ref,
        "industry_name": industry_name,
        "detailed_activity": detailed_activity,
        "zip": zip_code,
        "city": city,
        "latitude": latitude,
        "longitude": longitude,
        "geo_match_status": geo_match_status,
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

# PRO_BASIN003A_INSTANCE_POSTAL_AREAS
def _postal_areas_candidate_paths() -> list[Path]:
    mlc_id = _payment_basin_active_mlc_id()

    return [
        DATA_DIR / "instances" / mlc_id / "consumption_postal_areas.json",
        POSTAL_AREAS_PATH,
    ]


def _load_postal_areas() -> dict[str, dict[str, Any]]:
    for path in _postal_areas_candidate_paths():
        if not path.exists():
            continue

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue

        areas = payload.get("areas")
        if not isinstance(areas, dict):
            continue

        return {
            str(postal_code): area
            for postal_code, area in areas.items()
            if isinstance(area, dict)
        }

    return {}



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
    ]
    where_parts.extend(date_clauses)

    if _table_exists(conn, "actor_map_locations"):
        rows = conn.execute(
            f"""
            SELECT
              REPLACE(TRIM(l.postal_code), ' ', '') AS postal_code,
              MIN(NULLIF(TRIM(l.city), '')) AS city_label,
              COUNT(DISTINCT TRIM(t.from_label)) AS payer_count,
              COUNT(*) AS tx_count,
              COALESCE(SUM(t.amount), 0) AS volume,
              AVG(l.latitude) AS latitude,
              AVG(l.longitude) AS longitude
            FROM transactions t
            JOIN actor_map_locations l
              ON l.actor_ref = TRIM(t.from_label)
            WHERE {" AND ".join(where_parts)}
              AND l.cartographiable = 1
              AND NULLIF(TRIM(l.postal_code), '') IS NOT NULL
              AND l.latitude IS NOT NULL
              AND l.longitude IS NOT NULL
            GROUP BY REPLACE(TRIM(l.postal_code), ' ', '')
            ORDER BY volume DESC, payer_count DESC, postal_code ASC
            """,
            [professional_ref, *date_params],
        ).fetchall()

        if rows:
            return [
                {
                    "postal_code": _clean_zip(row["postal_code"]),
                    "city_label": _clean_text(row["city_label"]),
                    "payer_count": _safe_int(row["payer_count"]),
                    "tx_count": _safe_int(row["tx_count"]),
                    "volume": _safe_float(row["volume"]),
                    "latitude": _safe_float(row["latitude"], default=None),
                    "longitude": _safe_float(row["longitude"], default=None),
                    "location_source": "actor_map_locations",
                }
                for row in rows
                if _clean_zip(row["postal_code"])
            ]

    if not _table_exists(conn, "odoo_individual_enrichment"):
        return []

    fallback_where_parts = [
        *where_parts,
        "NULLIF(TRIM(i.zip), '') IS NOT NULL",
    ]

    rows = conn.execute(
        f"""
        SELECT
          REPLACE(TRIM(i.zip), ' ', '') AS postal_code,
          MIN(NULLIF(TRIM(i.city), '')) AS city_label,
          COUNT(DISTINCT TRIM(t.from_label)) AS payer_count,
          COUNT(*) AS tx_count,
          COALESCE(SUM(t.amount), 0) AS volume,
          AVG(i.latitude) AS latitude,
          AVG(i.longitude) AS longitude
        FROM transactions t
        JOIN odoo_individual_enrichment i
          ON i.pseudonym = TRIM(t.from_label)
        WHERE {" AND ".join(fallback_where_parts)}
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
            "latitude": _safe_float(row["latitude"], default=None),
            "longitude": _safe_float(row["longitude"], default=None),
            "location_source": "odoo_individual_enrichment",
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
        WITH source_flows AS (
            SELECT
              SUBSTR(TRIM(t.from_label), 1, 5) AS professional_ref,
              COUNT(*) AS tx_count,
              COALESCE(SUM(t.amount), 0) AS volume
            FROM transactions t
            WHERE {" AND ".join(where_parts)}
            GROUP BY SUBSTR(TRIM(t.from_label), 1, 5)
        )
        SELECT
          sf.professional_ref,
          COALESCE(
            NULLIF(TRIM(pe.display_name), ''),
            NULLIF(TRIM(pe.legal_name), ''),
            NULLIF(TRIM(oe.odoo_name), ''),
            sf.professional_ref
          ) AS name,
          COALESCE(
            NULLIF(TRIM(pe.industry_name), ''),
            NULLIF(TRIM(oe.industry_name), '')
          ) AS industry_name,
          COALESCE(
            NULLIF(TRIM(pe.short_description), ''),
            NULLIF(TRIM(pe.detailed_activity), ''),
            NULLIF(TRIM(oe.detailed_activity), '')
          ) AS detailed_activity,
          COALESCE(
            NULLIF(TRIM(l.postal_code), ''),
            NULLIF(TRIM(pe.zip), ''),
            NULLIF(TRIM(oe.cyclos_zip), ''),
            NULLIF(TRIM(oe.zip), '')
          ) AS zip,
          COALESCE(
            NULLIF(TRIM(l.city), ''),
            NULLIF(TRIM(pe.city), ''),
            NULLIF(TRIM(oe.cyclos_city), ''),
            NULLIF(TRIM(oe.city), '')
          ) AS city,
          COALESCE(l.latitude, pe.latitude, oe.cyclos_latitude, oe.latitude) AS latitude,
          COALESCE(l.longitude, pe.longitude, oe.cyclos_longitude, oe.longitude) AS longitude,
          COALESCE(
            NULLIF(TRIM(l.location_strategy), ''),
            NULLIF(TRIM(oe.geo_match_status), ''),
            'adaptive_location'
          ) AS geo_match_status,
          sf.tx_count,
          sf.volume
        FROM source_flows sf
        LEFT JOIN actor_map_locations l
          ON l.actor_ref = sf.professional_ref
         AND l.cartographiable = 1
        LEFT JOIN professional_enrichment pe
          ON pe.professional_ref = sf.professional_ref
         AND (
              pe.cyclos_group_set LIKE 'B %'
              OR LOWER(COALESCE(pe.cyclos_group, '')) LIKE '%prestataire%'
              OR pe.actor_type_internal IN ('MonComptePro', 'compteProBillets')
         )
        LEFT JOIN odoo_professional_enrichment oe
          ON oe.professional_ref = sf.professional_ref
        ORDER BY sf.volume DESC, sf.tx_count DESC, sf.professional_ref ASC
        """,
        [professional_ref, professional_ref, *date_params],
    ).fetchall()

    result: list[dict[str, Any]] = []

    for row in rows:
        latitude, longitude, has_coordinates = _finite_pair(
            row["latitude"],
            row["longitude"],
        )

        result.append({
            "professional_ref": row["professional_ref"],
            "name": _clean_text(row["name"]) or row["professional_ref"],
            "industry_name": _clean_text(row["industry_name"]),
            "detailed_activity": _clean_text(row["detailed_activity"]),
            "zip": _clean_text(row["zip"]),
            "city": _clean_text(row["city"]),
            "latitude": latitude,
            "longitude": longitude,
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
    missing_postal_data = {
        "payer_count": max(
            0,
            individual_totals["payer_count"]
            - sum(row["payer_count"] for row in individual_postal_rows),
        ),
        "tx_count": max(
            0,
            individual_totals["tx_count"]
            - sum(row["tx_count"] for row in individual_postal_rows),
        ),
        "volume": max(
            0.0,
            individual_totals["volume"]
            - sum(row["volume"] for row in individual_postal_rows),
        ),
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

        row_latitude = _safe_float(row.get("latitude"), default=float("nan"))
        row_longitude = _safe_float(row.get("longitude"), default=float("nan"))
        row_has_coordinates = math.isfinite(row_latitude) and math.isfinite(row_longitude)

        if row_has_coordinates:
            visible_individual_sources.append({
                **row,
                "city_label": row["city_label"] or (area or {}).get("city_label"),
                "longitude": row_longitude,
                "latitude": row_latitude,
            })
            continue

        if area:
            visible_individual_sources.append({
                **row,
                "city_label": row["city_label"] or area.get("city_label"),
                "longitude": area["longitude"],
                "latitude": area["latitude"],
                "location_source": row.get("location_source") or "postal_area_geometry",
            })
            continue

        missing_postal_geometry["source_count"] += 1
        missing_postal_geometry["payer_count"] += row["payer_count"]
        missing_postal_geometry["tx_count"] += row["tx_count"]
        missing_postal_geometry["volume"] += row["volume"]
        missing_postal_geometry["postal_codes"].append(postal_code)


    payment_scope = _payment_basin_territorial_scope()

    territory_individual_sources, outside_territory_individual_sources = (
        _split_sources_by_payment_scope(visible_individual_sources, payment_scope)
    )

    outside_territory_route_source = _aggregate_outside_scope_sources(
        outside_territory_individual_sources,
        center=center,
        in_scope_sources=territory_individual_sources,
        scope=payment_scope,
        source_kind="individual",
    )

    mapped_individual_route_sources = [
        *territory_individual_sources,
        *(
            [outside_territory_route_source]
            if outside_territory_route_source
            else []
        ),
    ]

    cartographiable_professional_sources = [
        row for row in professional_rows if row["has_coordinates"]
    ]

    hidden_professional_sources = [
        row for row in professional_rows if not row["has_coordinates"]
    ]

    territory_professional_sources, outside_territory_professional_sources = (
        _split_sources_by_payment_scope(cartographiable_professional_sources, payment_scope)
    )

    outside_professional_route_source = _aggregate_outside_scope_sources(
        outside_territory_professional_sources,
        center=center,
        in_scope_sources=territory_professional_sources,
        scope=payment_scope,
        source_kind="professional",
    )

    visible_professional_sources = [
        *territory_professional_sources,
        *(
            [outside_professional_route_source]
            if outside_professional_route_source
            else []
        ),
    ]

    routes: list[dict[str, Any]] = []

    if center["has_coordinates"]:
        for source in mapped_individual_route_sources:
            is_outside_territory = bool(source.get("is_outside_territory"))

            routes.append({
                "id": (
                    "u-outside-territory"
                    if is_outside_territory
                    else f"u-postal:{source['postal_code']}"
                ),
                "kind": (
                    "individual_outside_territory"
                    if is_outside_territory
                    else "individual_postal"
                ),
                "source": source,
                "destination": center,
                "tx_count": source["tx_count"],
                "volume": source["volume"],
                "payer_count": source["payer_count"],
            })

        for source in visible_professional_sources:
            source_ref = source.get("professional_ref") or "P_OUTSIDE_SCOPE"
            is_outside_scope = bool(source.get("is_outside_scope"))

            routes.append({
                "id": f"professional:{source_ref}",
                "kind": (
                    "professional_outside_territory"
                    if is_outside_scope
                    else "professional_inbound"
                ),
                "source": source,
                "destination": center,
                "tx_count": source["tx_count"],
                "volume": source["volume"],
                "payer_count": (
                    max(1, _safe_int(source.get("payer_count"), 1))
                    if is_outside_scope
                    else 1
                ),
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

    visible_source_area_geojson = {}

    for source in territory_individual_sources:
        postal_code = source.get("postal_code")
        area = postal_areas.get(postal_code or "")
        feature_collection = area.get("feature_collection") if area else None

        if not feature_collection:
            feature_collection = _synthetic_source_area_feature_collection(source)

        if feature_collection:
            visible_source_area_geojson[
                postal_code or f"source:{len(visible_source_area_geojson) + 1}"
            ] = feature_collection

    coverage = {
        "min_users": cleaned_min_users,
        "visible_route_count": len(routes),

        "individual_total_payer_count": individual_totals["payer_count"],
        "individual_total_tx_count": individual_totals["tx_count"],
        "individual_total_volume": individual_totals["volume"],

        "individual_visible_postal_source_count": len(mapped_individual_route_sources),
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
        "individual_missing_postal_data": missing_postal_data,
        "individual_outside_territory": {
            "postal_source_count": len(outside_territory_individual_sources),
            "payer_count": sum(
                _safe_int(source.get("payer_count"), 0)
                for source in outside_territory_individual_sources
            ),
            "tx_count": sum(
                _safe_int(source.get("tx_count"), 0)
                for source in outside_territory_individual_sources
            ),
            "volume": sum(
                _safe_float(source.get("volume"))
                for source in outside_territory_individual_sources
            ),
            "aggregated_into_single_route": bool(outside_territory_route_source),
        },

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
        "professional_outside_territory": {
            "source_count": len(outside_territory_professional_sources),
            "tx_count": sum(
                _safe_int(source.get("tx_count"), 0)
                for source in outside_territory_professional_sources
            ),
            "volume": sum(
                _safe_float(source.get("volume"))
                for source in outside_territory_professional_sources
            ),
            "aggregated_into_single_route": bool(outside_professional_route_source),
        },
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
        "territorial_scope": payment_scope,
        "geometry": {
            "visible_source_area_geojson": visible_source_area_geojson,
        },
        "individual_sources": mapped_individual_route_sources,
        "professional_sources": visible_professional_sources,
        "routes": routes,
    }
