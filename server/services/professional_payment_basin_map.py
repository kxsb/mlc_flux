from __future__ import annotations

import json
import math
import re
from datetime import date
from typing import Any

from server.database import get_connection
from server.mlc_context import (
    get_default_mlc_id,
)


PROFESSIONAL_REF_RE = re.compile(r"^P\d{4}$")

DEFAULT_MIN_USERS = 1
MAX_MIN_USERS = 50


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None

    text = str(value).strip()
    return text or None


def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return default

    if not math.isfinite(numeric):
        return default

    return numeric


def _safe_int(
    value: Any,
    default: int = 0,
) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _clean_zip(value: Any) -> str | None:
    text = _clean_text(value)

    if not text:
        return None

    return text.replace(" ", "") or None


def _normalize_professional_ref(
    value: str | None,
) -> str:
    ref = str(value or "").strip().upper()

    if not PROFESSIONAL_REF_RE.fullmatch(ref):
        raise ValueError(
            "Référence professionnelle invalide : "
            f"{value!r}"
        )

    return ref


def _parse_iso_date(
    value: str | None,
    field_name: str,
) -> str | None:
    text = _clean_text(value)

    if not text:
        return None

    try:
        return date.fromisoformat(text).isoformat()
    except ValueError as exc:
        raise ValueError(
            f"Date invalide pour {field_name}: "
            f"{value!r}. Format attendu : YYYY-MM-DD."
        ) from exc


def _json_dict(value: Any) -> dict[str, Any]:
    if not value:
        return {}

    try:
        payload = json.loads(str(value))
    except Exception:
        return {}

    return payload if isinstance(payload, dict) else {}


def _resolve_period(
    conn,
    requested_start: str | None,
    requested_end: str | None,
) -> dict[str, str | None]:
    start = _parse_iso_date(
        requested_start,
        "start",
    )
    end = _parse_iso_date(
        requested_end,
        "end",
    )

    bounds = conn.execute(
        """
        SELECT
            MIN(SUBSTR(date, 1, 10)) AS min_date,
            MAX(SUBSTR(date, 1, 10)) AS max_date
        FROM transactions
        """
    ).fetchone()

    min_date = (
        bounds["min_date"]
        if bounds
        else None
    )
    max_date = (
        bounds["max_date"]
        if bounds
        else None
    )

    effective_start = start or min_date
    effective_end = end or max_date

    if (
        effective_start
        and effective_end
        and effective_start > effective_end
    ):
        raise ValueError(
            "Période invalide : "
            f"start={effective_start} "
            f"est postérieur à end={effective_end}."
        )

    return {
        "requested_start": start,
        "requested_end": end,
        "effective_start": effective_start,
        "effective_end": effective_end,
        "min_date": min_date,
        "max_date": max_date,
    }


def _period_sql(
    start: str | None,
    end: str | None,
) -> tuple[list[str], list[Any]]:
    clauses = []
    params = []

    if start:
        clauses.append(
            "SUBSTR(t.date, 1, 10) >= ?"
        )
        params.append(start)

    if end:
        clauses.append(
            "SUBSTR(t.date, 1, 10) <= ?"
        )
        params.append(end)

    return clauses, params


def _share(
    part: float,
    whole: float,
) -> float | None:
    if whole <= 0:
        return None

    return part / whole


def _get_mlc_territory(
    conn,
) -> dict[str, Any]:
    mlc_id = get_default_mlc_id()

    row = conn.execute(
        """
        SELECT *
        FROM geographic_areas
        WHERE area_type = 'mlc_territory'
          AND area_code = ?
        LIMIT 1
        """,
        (mlc_id,),
    ).fetchone()

    if row is None:
        raise RuntimeError(
            "Territoire MLC absent de geographic_areas."
        )

    metadata = _json_dict(
        row["metadata_json"]
    )

    scope = metadata.get(
        "territorial_scope"
    )

    if not isinstance(scope, dict):
        scope = {}

    prefixes = scope.get(
        "postal_code_prefixes"
    )

    if not isinstance(prefixes, list):
        prefixes = []

    prefixes = [
        str(value).strip()
        for value in prefixes
        if str(value).strip()
    ]

    return {
        "area_id": row["area_id"],
        "country_code": row["country_code"],
        "name": row["name"],
        "short_name": row["short_name"],
        "postal_code_prefixes": prefixes,
        "outside_label": (
            _clean_text(
                scope.get("outside_label")
            )
            or "Hors territoire"
        ),
    }


def _postal_is_inside_territory(
    postal_code: str | None,
    territory: dict[str, Any],
) -> bool:
    if not postal_code:
        return False

    prefixes = territory.get(
        "postal_code_prefixes"
    ) or []

    if prefixes:
        return any(
            postal_code.startswith(prefix)
            for prefix in prefixes
        )

    return True



def _territory_feature_identity(
    feature: dict[str, Any],
) -> str:
    """
    Produit une identité stable permettant de dédupliquer les
    contours communaux présents dans plusieurs zones postales.

    Exemple important :
    plusieurs codes postaux lyonnais référencent le même contour
    communal. Le fond de carte ne doit pas le repeindre 9 fois.
    """
    properties = (
        feature.get("properties")
        if isinstance(
            feature.get("properties"),
            dict,
        )
        else {}
    )

    source_code = _clean_text(
        properties.get("code")
    )

    if source_code:
        return f"source-code:{source_code}"

    geometry = feature.get("geometry")

    return (
        "geometry:"
        + json.dumps(
            geometry,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )


def _load_territory_basemap(
    conn,
    territory: dict[str, Any],
) -> dict[str, Any]:
    """
    Construit le fond territorial simplifié depuis geographic_areas.

    Le fond :
    - ne lit aucun fichier JSON historique ;
    - ne dépend d'aucun provider transactionnel ;
    - conserve uniquement des contours territoriaux ;
    - déduplique les communes présentes sous plusieurs codes postaux.
    """
    country_code = _clean_text(
        territory.get("country_code")
    )

    prefixes = [
        str(value).strip()
        for value in (
            territory.get(
                "postal_code_prefixes"
            )
            or []
        )
        if str(value).strip()
    ]

    if country_code:
        rows = conn.execute(
            """
            SELECT
                area_id,
                area_code,
                geometry_geojson
            FROM geographic_areas
            WHERE area_type = 'postal_area'
              AND country_code = ?
              AND geometry_geojson IS NOT NULL
              AND TRIM(geometry_geojson) <> ''
            ORDER BY area_code
            """,
            (country_code,),
        ).fetchall()

    else:
        rows = conn.execute(
            """
            SELECT
                area_id,
                area_code,
                geometry_geojson
            FROM geographic_areas
            WHERE area_type = 'postal_area'
              AND geometry_geojson IS NOT NULL
              AND TRIM(geometry_geojson) <> ''
            ORDER BY area_code
            """
        ).fetchall()

    features = []
    seen_feature_ids = set()

    postal_area_count = 0
    raw_feature_count = 0

    for row in rows:
        postal_code = _clean_zip(
            row["area_code"]
        )

        if prefixes:
            if not postal_code:
                continue

            if not any(
                postal_code.startswith(prefix)
                for prefix in prefixes
            ):
                continue

        feature_collection = _json_dict(
            row["geometry_geojson"]
        )

        source_features = (
            feature_collection.get(
                "features"
            )
        )

        if not isinstance(
            source_features,
            list,
        ):
            continue

        postal_area_count += 1

        for feature in source_features:
            if not isinstance(
                feature,
                dict,
            ):
                continue

            geometry = feature.get(
                "geometry"
            )

            if not isinstance(
                geometry,
                dict,
            ):
                continue

            if geometry.get("type") not in {
                "Polygon",
                "MultiPolygon",
            }:
                continue

            raw_feature_count += 1

            identity = (
                _territory_feature_identity(
                    feature
                )
            )

            if identity in seen_feature_ids:
                continue

            seen_feature_ids.add(
                identity
            )

            features.append(feature)

    return {
        "feature_collection": {
            "type": "FeatureCollection",
            "features": features,
        },
        "postal_area_count":
            postal_area_count,
        "raw_feature_count":
            raw_feature_count,
        "feature_count":
            len(features),
    }


def _professional_center(
    conn,
    professional_ref: str,
) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT
            g.actor_ref,
            g.street,
            g.postal_code,
            g.city,
            g.latitude,
            g.longitude,
            g.precision_level,
            g.confidence_level,
            g.resolution_method,

            p.display_name,
            p.legal_name,
            p.industry_name,
            p.detailed_activity

        FROM actor_geography g

        LEFT JOIN professional_enrichment p
          ON p.professional_ref = g.actor_ref

        WHERE g.actor_ref = ?
          AND g.actor_family = 'P'
        """,
        (professional_ref,),
    ).fetchone()

    if row is None:
        return {
            "professional_ref":
                professional_ref,
            "name":
                professional_ref,
            "industry_name":
                None,
            "detailed_activity":
                None,
            "zip":
                None,
            "city":
                None,
            "latitude":
                None,
            "longitude":
                None,
            "precision_level":
                None,
            "confidence_level":
                None,
            "resolution_method":
                None,
            "has_coordinates":
                False,
        }

    latitude = row["latitude"]
    longitude = row["longitude"]

    has_coordinates = (
        latitude is not None
        and longitude is not None
        and row["confidence_level"] != "low"
    )

    return {
        "professional_ref":
            row["actor_ref"],

        "name": (
            _clean_text(row["display_name"])
            or _clean_text(row["legal_name"])
            or row["actor_ref"]
        ),

        "industry_name":
            _clean_text(
                row["industry_name"]
            ),

        "detailed_activity":
            _clean_text(
                row["detailed_activity"]
            ),

        "zip":
            _clean_zip(
                row["postal_code"]
            ),

        "city":
            _clean_text(
                row["city"]
            ),

        "latitude": (
            float(latitude)
            if has_coordinates
            else None
        ),

        "longitude": (
            float(longitude)
            if has_coordinates
            else None
        ),

        "precision_level":
            row["precision_level"],

        "confidence_level":
            row["confidence_level"],

        "resolution_method":
            row["resolution_method"],

        "has_coordinates":
            has_coordinates,
    }


def _individual_totals(
    conn,
    *,
    professional_ref: str,
    start: str | None,
    end: str | None,
) -> dict[str, Any]:
    date_clauses, date_params = (
        _period_sql(start, end)
    )

    where_parts = [
        "SUBSTR(TRIM(t.to_label), 1, 5) = ?",
        """(
            SUBSTR(TRIM(t.from_label), 1, 2) = 'U_'
            OR
            SUBSTR(TRIM(t.from_label), 1, 3) = 'UD_'
        )""",
    ]

    where_parts.extend(date_clauses)

    row = conn.execute(
        f"""
        SELECT
            COUNT(
                DISTINCT TRIM(t.from_label)
            ) AS payer_count,

            COUNT(*) AS tx_count,

            COALESCE(
                SUM(t.amount),
                0
            ) AS volume

        FROM transactions t

        WHERE {" AND ".join(where_parts)}
        """,
        [
            professional_ref,
            *date_params,
        ],
    ).fetchone()

    return {
        "payer_count":
            _safe_int(
                row["payer_count"]
                if row
                else 0
            ),

        "tx_count":
            _safe_int(
                row["tx_count"]
                if row
                else 0
            ),

        "volume":
            _safe_float(
                row["volume"]
                if row
                else 0,
            ),
    }


def _individual_postal_rows(
    conn,
    *,
    professional_ref: str,
    start: str | None,
    end: str | None,
) -> list[dict[str, Any]]:
    """
    Lit uniquement actor_geography pour la géographie U.

    Tant qu'aucun acteur U n'y est résolu, cette fonction
    renvoie naturellement une liste vide.
    """
    date_clauses, date_params = (
        _period_sql(start, end)
    )

    where_parts = [
        "SUBSTR(TRIM(t.to_label), 1, 5) = ?",
        """(
            SUBSTR(TRIM(t.from_label), 1, 2) = 'U_'
            OR
            SUBSTR(TRIM(t.from_label), 1, 3) = 'UD_'
        )""",
        "NULLIF(TRIM(g.postal_code), '') IS NOT NULL",
    ]

    where_parts.extend(date_clauses)

    rows = conn.execute(
        f"""
        SELECT
            REPLACE(
                TRIM(g.postal_code),
                ' ',
                ''
            ) AS postal_code,

            MAX(
                NULLIF(
                    TRIM(g.city),
                    ''
                )
            ) AS city_label,

            MAX(g.postal_area_id)
                AS postal_area_id,

            MAX(a.latitude)
                AS area_latitude,

            MAX(a.longitude)
                AS area_longitude,

            MAX(a.geometry_geojson)
                AS geometry_geojson,

            COUNT(
                DISTINCT TRIM(t.from_label)
            ) AS payer_count,

            COUNT(*) AS tx_count,

            COALESCE(
                SUM(t.amount),
                0
            ) AS volume

        FROM transactions t

        JOIN actor_geography g
          ON g.actor_ref = TRIM(t.from_label)
         AND g.actor_family = 'U'

        LEFT JOIN geographic_areas a
          ON a.area_id = g.postal_area_id
         AND a.area_type = 'postal_area'

        WHERE {" AND ".join(where_parts)}

        GROUP BY
            REPLACE(
                TRIM(g.postal_code),
                ' ',
                ''
            )

        ORDER BY
            volume DESC,
            payer_count DESC,
            postal_code ASC
        """,
        [
            professional_ref,
            *date_params,
        ],
    ).fetchall()

    result = []

    for row in rows:
        geometry = None

        if row["geometry_geojson"]:
            try:
                decoded = json.loads(
                    row["geometry_geojson"]
                )

                if isinstance(decoded, dict):
                    geometry = decoded

            except Exception:
                geometry = None

        result.append({
            "postal_code":
                _clean_zip(
                    row["postal_code"]
                ),

            "city_label":
                _clean_text(
                    row["city_label"]
                ),

            "postal_area_id":
                _clean_text(
                    row["postal_area_id"]
                ),

            "longitude": (
                float(
                    row["area_longitude"]
                )
                if row["area_longitude"]
                is not None
                else None
            ),

            "latitude": (
                float(
                    row["area_latitude"]
                )
                if row["area_latitude"]
                is not None
                else None
            ),

            "feature_collection":
                geometry,

            "payer_count":
                _safe_int(
                    row["payer_count"]
                ),

            "tx_count":
                _safe_int(
                    row["tx_count"]
                ),

            "volume":
                _safe_float(
                    row["volume"]
                ),
        })

    return result


def _professional_inbound_rows(
    conn,
    *,
    professional_ref: str,
    start: str | None,
    end: str | None,
) -> list[dict[str, Any]]:
    date_clauses, date_params = (
        _period_sql(start, end)
    )

    where_parts = [
        "SUBSTR(TRIM(t.to_label), 1, 5) = ?",
        (
            "SUBSTR(TRIM(t.from_label), 1, 5) "
            "GLOB 'P[0-9][0-9][0-9][0-9]'"
        ),
        (
            "SUBSTR(TRIM(t.from_label), 1, 5) "
            "NOT IN ('P0000', 'P9999')"
        ),
        (
            "SUBSTR(TRIM(t.from_label), 1, 5) "
            "<> ?"
        ),
    ]

    where_parts.extend(date_clauses)

    rows = conn.execute(
        f"""
        SELECT
            SUBSTR(
                TRIM(t.from_label),
                1,
                5
            ) AS professional_ref,

            COALESCE(
                NULLIF(
                    TRIM(p.display_name),
                    ''
                ),
                NULLIF(
                    TRIM(p.legal_name),
                    ''
                ),
                SUBSTR(
                    TRIM(t.from_label),
                    1,
                    5
                )
            ) AS name,

            p.industry_name,
            p.detailed_activity,

            g.postal_code AS zip,
            g.city,
            g.latitude,
            g.longitude,
            g.precision_level,
            g.confidence_level,
            g.resolution_method,

            COUNT(*) AS tx_count,

            COALESCE(
                SUM(t.amount),
                0
            ) AS volume

        FROM transactions t

        LEFT JOIN actor_geography g
          ON g.actor_ref =
             SUBSTR(
                 TRIM(t.from_label),
                 1,
                 5
             )
         AND g.actor_family = 'P'

        LEFT JOIN professional_enrichment p
          ON p.professional_ref =
             SUBSTR(
                 TRIM(t.from_label),
                 1,
                 5
             )

        WHERE {" AND ".join(where_parts)}

        GROUP BY
            SUBSTR(
                TRIM(t.from_label),
                1,
                5
            )

        ORDER BY
            volume DESC,
            tx_count DESC,
            professional_ref ASC
        """,
        [
            professional_ref,
            professional_ref,
            *date_params,
        ],
    ).fetchall()

    result = []

    for row in rows:
        latitude = row["latitude"]
        longitude = row["longitude"]

        has_coordinates = (
            latitude is not None
            and longitude is not None
            and row["confidence_level"]
                != "low"
        )

        result.append({
            "professional_ref":
                row["professional_ref"],

            "name": (
                _clean_text(row["name"])
                or row["professional_ref"]
            ),

            "industry_name":
                _clean_text(
                    row["industry_name"]
                ),

            "detailed_activity":
                _clean_text(
                    row["detailed_activity"]
                ),

            "zip":
                _clean_zip(
                    row["zip"]
                ),

            "city":
                _clean_text(
                    row["city"]
                ),

            "latitude": (
                float(latitude)
                if has_coordinates
                else None
            ),

            "longitude": (
                float(longitude)
                if has_coordinates
                else None
            ),

            "precision_level":
                row["precision_level"],

            "confidence_level":
                row["confidence_level"],

            "resolution_method":
                row["resolution_method"],

            "has_coordinates":
                has_coordinates,

            "tx_count":
                _safe_int(
                    row["tx_count"]
                ),

            "volume":
                _safe_float(
                    row["volume"]
                ),
        })

    return result


def get_professional_payment_basin_map(
    professional_ref: str,
    *,
    start: str | None = None,
    end: str | None = None,
    min_users: int = DEFAULT_MIN_USERS,
) -> dict[str, Any]:
    normalized_ref = (
        _normalize_professional_ref(
            professional_ref
        )
    )

    cleaned_min_users = max(
        1,
        min(
            MAX_MIN_USERS,
            _safe_int(
                min_users,
                DEFAULT_MIN_USERS,
            ),
        ),
    )

    conn = get_connection()

    try:
        period = _resolve_period(
            conn,
            start,
            end,
        )

        effective_start = (
            period["effective_start"]
        )
        effective_end = (
            period["effective_end"]
        )

        territory = _get_mlc_territory(
            conn
        )

        territory_basemap = _load_territory_basemap(
            conn,
            territory,
        )

        center = _professional_center(
            conn,
            normalized_ref,
        )

        individual_totals = (
            _individual_totals(
                conn,
                professional_ref=
                    normalized_ref,
                start=effective_start,
                end=effective_end,
            )
        )

        individual_rows = (
            _individual_postal_rows(
                conn,
                professional_ref=
                    normalized_ref,
                start=effective_start,
                end=effective_end,
            )
        )

        professional_rows = (
            _professional_inbound_rows(
                conn,
                professional_ref=
                    normalized_ref,
                start=effective_start,
                end=effective_end,
            )
        )

    finally:
        conn.close()

    visible_individual_sources = []

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

    mapped_payer_count = sum(
        row["payer_count"]
        for row in individual_rows
    )

    mapped_tx_count = sum(
        row["tx_count"]
        for row in individual_rows
    )

    mapped_volume = sum(
        row["volume"]
        for row in individual_rows
    )

    missing_postal_data = {
        "payer_count": max(
            0,
            individual_totals[
                "payer_count"
            ] - mapped_payer_count,
        ),

        "tx_count": max(
            0,
            individual_totals[
                "tx_count"
            ] - mapped_tx_count,
        ),

        "volume": max(
            0.0,
            individual_totals[
                "volume"
            ] - mapped_volume,
        ),
    }

    territory_sources = []
    outside_sources = []

    for row in individual_rows:
        postal_code = row["postal_code"]

        inside = (
            _postal_is_inside_territory(
                postal_code,
                territory,
            )
        )

        if (
            row["payer_count"]
            < cleaned_min_users
        ):
            hidden_below_threshold[
                "source_count"
            ] += 1

            hidden_below_threshold[
                "payer_count"
            ] += row["payer_count"]

            hidden_below_threshold[
                "tx_count"
            ] += row["tx_count"]

            hidden_below_threshold[
                "volume"
            ] += row["volume"]

            continue

        if not inside:
            outside_sources.append(row)
            continue

        has_area = (
            row["postal_area_id"]
            and row["latitude"]
                is not None
            and row["longitude"]
                is not None
            and isinstance(
                row["feature_collection"],
                dict,
            )
        )

        if not has_area:
            missing_postal_geometry[
                "source_count"
            ] += 1

            missing_postal_geometry[
                "payer_count"
            ] += row["payer_count"]

            missing_postal_geometry[
                "tx_count"
            ] += row["tx_count"]

            missing_postal_geometry[
                "volume"
            ] += row["volume"]

            missing_postal_geometry[
                "postal_codes"
            ].append(postal_code)

            continue

        visible_individual_sources.append(
            row
        )
        territory_sources.append(row)

    outside_route_source = None

    if outside_sources:
        outside_route_source = {
            "postal_code": None,
            "display_label":
                territory[
                    "outside_label"
                ],

            "city_label":
                territory[
                    "outside_label"
                ],

            "longitude": None,
            "latitude": None,

            "payer_count": sum(
                row["payer_count"]
                for row in outside_sources
            ),

            "tx_count": sum(
                row["tx_count"]
                for row in outside_sources
            ),

            "volume": sum(
                row["volume"]
                for row in outside_sources
            ),

            "postal_source_count":
                len(outside_sources),

            "is_outside_territory":
                True,
        }

    mapped_individual_route_sources = [
        *territory_sources,
    ]

    if outside_route_source:
        mapped_individual_route_sources.append(
            outside_route_source
        )

    visible_professional_sources = [
        row
        for row in professional_rows
        if row["has_coordinates"]
    ]

    hidden_professional_sources = [
        row
        for row in professional_rows
        if not row["has_coordinates"]
    ]

    routes = []

    if center["has_coordinates"]:
        for source in (
            mapped_individual_route_sources
        ):
            outside = bool(
                source.get(
                    "is_outside_territory"
                )
            )

            routes.append({
                "id": (
                    "u-outside-territory"
                    if outside
                    else (
                        "u-postal:"
                        f"{source['postal_code']}"
                    )
                ),

                "kind": (
                    "individual_outside_territory"
                    if outside
                    else "individual_postal"
                ),

                "source": source,
                "destination": center,

                "tx_count":
                    source["tx_count"],

                "volume":
                    source["volume"],

                "payer_count":
                    source["payer_count"],
            })

        for source in (
            visible_professional_sources
        ):
            routes.append({
                "id": (
                    "professional:"
                    f"{source['professional_ref']}"
                ),
                "kind":
                    "professional_inbound",

                "source":
                    source,
                "destination":
                    center,

                "tx_count":
                    source["tx_count"],

                "volume":
                    source["volume"],

                "payer_count":
                    1,
            })

    visible_individual_payer_count = sum(
        row["payer_count"]
        for row in visible_individual_sources
    )

    visible_individual_tx_count = sum(
        row["tx_count"]
        for row in visible_individual_sources
    )

    visible_individual_volume = sum(
        row["volume"]
        for row in visible_individual_sources
    )

    professional_total_tx_count = sum(
        row["tx_count"]
        for row in professional_rows
    )

    professional_total_volume = sum(
        row["volume"]
        for row in professional_rows
    )

    visible_professional_tx_count = sum(
        row["tx_count"]
        for row in visible_professional_sources
    )

    visible_professional_volume = sum(
        row["volume"]
        for row in visible_professional_sources
    )

    visible_source_area_geojson = {
        row["postal_code"]:
            row["feature_collection"]

        for row in territory_sources

        if row["postal_code"]
        and isinstance(
            row["feature_collection"],
            dict,
        )
    }

    coverage = {
        "min_users":
            cleaned_min_users,

        "territory_basemap_postal_area_count":
            territory_basemap[
                "postal_area_count"
            ],

        "territory_basemap_raw_feature_count":
            territory_basemap[
                "raw_feature_count"
            ],

        "territory_basemap_feature_count":
            territory_basemap[
                "feature_count"
            ],

        "visible_route_count":
            len(routes),

        "individual_total_payer_count":
            individual_totals[
                "payer_count"
            ],

        "individual_total_tx_count":
            individual_totals[
                "tx_count"
            ],

        "individual_total_volume":
            individual_totals[
                "volume"
            ],

        "individual_visible_postal_source_count":
            len(
                visible_individual_sources
            ),

        "individual_visible_payer_count":
            visible_individual_payer_count,

        "individual_visible_tx_count":
            visible_individual_tx_count,

        "individual_visible_volume":
            visible_individual_volume,

        "individual_visible_payer_share":
            _share(
                visible_individual_payer_count,
                individual_totals[
                    "payer_count"
                ],
            ),

        "individual_visible_volume_share":
            _share(
                visible_individual_volume,
                individual_totals[
                    "volume"
                ],
            ),

        "individual_hidden_below_threshold":
            hidden_below_threshold,

        "individual_missing_postal_geometry":
            missing_postal_geometry,

        "individual_missing_postal_data":
            missing_postal_data,

        "individual_outside_territory": {
            "postal_source_count":
                len(outside_sources),

            "payer_count":
                sum(
                    row["payer_count"]
                    for row in outside_sources
                ),

            "tx_count":
                sum(
                    row["tx_count"]
                    for row in outside_sources
                ),

            "volume":
                sum(
                    row["volume"]
                    for row in outside_sources
                ),

            "aggregated_into_single_route":
                bool(
                    outside_route_source
                ),
        },

        "professional_total_source_count":
            len(professional_rows),

        "professional_total_tx_count":
            professional_total_tx_count,

        "professional_total_volume":
            professional_total_volume,

        "professional_visible_source_count":
            len(
                visible_professional_sources
            ),

        "professional_visible_tx_count":
            visible_professional_tx_count,

        "professional_visible_volume":
            visible_professional_volume,

        "professional_missing_geometry_source_count":
            len(
                hidden_professional_sources
            ),

        "professional_missing_geometry_tx_count":
            sum(
                row["tx_count"]
                for row
                in hidden_professional_sources
            ),

        "professional_missing_geometry_volume":
            sum(
                row["volume"]
                for row
                in hidden_professional_sources
            ),
    }

    status_detail = "ok"

    if not center["has_coordinates"]:
        status_detail = (
            "missing_center_coordinates"
        )

    elif (
        individual_totals["payer_count"] > 0
        and not individual_rows
    ):
        status_detail = (
            "individual_geography_unavailable"
        )

    return {
        "status": "ok",
        "status_detail":
            status_detail,

        "professional_ref":
            normalized_ref,

        "requested_period": {
            "start":
                period["requested_start"],
            "end":
                period["requested_end"],
        },

        "effective_period": {
            "start":
                effective_start,
            "end":
                effective_end,
        },

        "bounds": {
            "min_date":
                period["min_date"],
            "max_date":
                period["max_date"],
        },

        "territory":
            territory,

        "center":
            center,

        "coverage":
            coverage,

        "geometry": {
            "territory_area_geojson": (
                {
                    "territory":
                        territory_basemap[
                            "feature_collection"
                        ]
                }
                if territory_basemap[
                    "feature_count"
                ] > 0
                else {}
            ),

            "visible_source_area_geojson":
                visible_source_area_geojson,
        },

        "individual_sources":
            visible_individual_sources,

        "professional_sources":
            visible_professional_sources,

        "routes":
            routes,
    }
