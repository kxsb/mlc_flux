from __future__ import annotations

import json
import math
from collections import Counter
from typing import Any

from server import database
from server.mlc_context import (
    get_default_mlc_id,
    normalize_mlc_id,
)


def _clean_text(value: Any) -> str | None:
    value = str(value or "").strip()
    return value or None


def _safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _load_json_dict(value: Any) -> dict[str, Any]:
    if not value:
        return {}

    try:
        decoded = json.loads(str(value))
    except Exception:
        return {}

    return decoded if isinstance(decoded, dict) else {}


def _json_dump(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _valid_coordinate_pair(
    latitude: Any,
    longitude: Any,
) -> tuple[float | None, float | None]:
    if latitude is None or longitude is None:
        return None, None

    try:
        lat = float(latitude)
        lon = float(longitude)
    except (TypeError, ValueError):
        return None, None

    if not (
        math.isfinite(lat)
        and math.isfinite(lon)
    ):
        return None, None

    if not (-90 <= lat <= 90):
        return None, None

    if not (-180 <= lon <= 180):
        return None, None

    return lat, lon


def _coordinates_match(
    lat_a: Any,
    lon_a: Any,
    lat_b: Any,
    lon_b: Any,
    *,
    tolerance: float = 1e-6,
) -> bool:
    a_lat, a_lon = _valid_coordinate_pair(
        lat_a,
        lon_a,
    )
    b_lat, b_lon = _valid_coordinate_pair(
        lat_b,
        lon_b,
    )

    if None in (a_lat, a_lon, b_lat, b_lon):
        return False

    return (
        abs(a_lat - b_lat) <= tolerance
        and abs(a_lon - b_lon) <= tolerance
    )


def _coordinate_origin(
    latitude: float | None,
    longitude: float | None,
    raw: dict[str, Any],
) -> str | None:
    if latitude is None or longitude is None:
        return None

    source_a = _safe_dict(
        raw.get("odoo_address")
    )
    source_b = _safe_dict(
        raw.get("legacy_cyclos_address")
    )

    matches_a = _coordinates_match(
        latitude,
        longitude,
        source_a.get("latitude"),
        source_a.get("longitude"),
    )

    matches_b = _coordinates_match(
        latitude,
        longitude,
        source_b.get("latitude"),
        source_b.get("longitude"),
    )

    if matches_a and matches_b:
        return "multiple_legacy_sources"

    if matches_a:
        return "legacy_odoo_address"

    if matches_b:
        return "legacy_cyclos_address"

    return "professional_enrichment"


def _confidence_level(
    status: str,
    *,
    has_geography: bool,
) -> str:
    """
    Confiance dans la résolution, indépendante de sa précision.
    """
    if status == "confirmed":
        return "high"

    if status == "mismatch":
        return "low"

    if status in {
        "no_odoo_coordinates",
        "no_cyclos_coordinates",
        "no_cyclos_address",
        "cyclos_error",
    }:
        return "medium"

    return "medium" if has_geography else "low"


def _precision_level(
    *,
    latitude: float | None,
    longitude: float | None,
    street: str | None,
    postal_code: str | None,
    city: str | None,
    mlc_territory_area_id: str | None,
) -> str:
    if latitude is not None and longitude is not None:
        return "exact_point"

    if street:
        return "address"

    if postal_code:
        return "postal_area"

    if city:
        return "commune"

    if mlc_territory_area_id:
        return "mlc_territory"

    return "unknown"


def _resolution_method(
    *,
    status: str,
    latitude: float | None,
    longitude: float | None,
    street: str | None,
    postal_code: str | None,
    city: str | None,
) -> str:
    if status == "confirmed":
        return "cross_source_confirmed"

    if status == "mismatch":
        return "cross_source_mismatch"

    if latitude is not None and longitude is not None:
        return "single_source_or_unverified_point"

    if street:
        return "address_without_point"

    if postal_code:
        return "postal_code_only"

    if city:
        return "city_only"

    return "mlc_territory_only"


def _get_mlc_territory(
    conn,
    mlc_id: str,
):
    row = conn.execute(
        """
        SELECT
            area_id,
            country_code
        FROM geographic_areas
        WHERE area_type = 'mlc_territory'
          AND area_code = ?
        LIMIT 1
        """,
        (mlc_id,),
    ).fetchone()

    if row is None:
        raise RuntimeError(
            "Territoire MLC absent de geographic_areas. "
            "GEO001B doit être exécuté avant GEO001C."
        )

    return row


def _resolve_postal_area_id(
    conn,
    *,
    country_code: str | None,
    postal_code: str | None,
) -> str | None:
    if not postal_code:
        return None

    row = conn.execute(
        """
        SELECT area_id
        FROM geographic_areas
        WHERE area_type = 'postal_area'
          AND area_code = ?
          AND (
              country_code = ?
              OR (
                  country_code IS NULL
                  AND ? IS NULL
              )
          )
        LIMIT 1
        """,
        (
            postal_code,
            country_code,
            country_code,
        ),
    ).fetchone()

    return row["area_id"] if row else None


def resolve_professional_geography_from_enrichment(
    mlc_id: str | None = None,
) -> dict[str, Any]:
    """
    Migration/résolution des professionnels du registre interne actuel
    vers le contrat géographique neutre actor_geography.

    professional_enrichment est ici une source de migration.
    Les futurs analytics géographiques ne doivent pas la lire directement.
    """
    normalized_mlc_id = normalize_mlc_id(
        mlc_id or get_default_mlc_id()
    )

    conn = database.get_connection()

    try:
        territory = _get_mlc_territory(
            conn,
            normalized_mlc_id,
        )

        mlc_territory_area_id = territory["area_id"]
        country_code = territory["country_code"]

        rows = conn.execute(
            """
            SELECT
                professional_ref,
                source_provider,
                street,
                zip,
                city,
                latitude,
                longitude,
                raw_safe_json,
                fetched_at,
                updated_at
            FROM professional_enrichment
            ORDER BY professional_ref
            """
        ).fetchall()

        precision_counts = Counter()
        confidence_counts = Counter()
        method_counts = Counter()
        status_counts = Counter()

        postal_area_resolved_count = 0

        for row in rows:
            professional_ref = _clean_text(
                row["professional_ref"]
            )

            if not professional_ref:
                continue

            raw = _load_json_dict(
                row["raw_safe_json"]
            )

            status = (
                _clean_text(
                    raw.get("geo_match_status")
                )
                or "unknown"
            )

            street = _clean_text(row["street"])
            postal_code = _clean_text(row["zip"])
            city = _clean_text(row["city"])

            latitude, longitude = (
                _valid_coordinate_pair(
                    row["latitude"],
                    row["longitude"],
                )
            )

            postal_area_id = _resolve_postal_area_id(
                conn,
                country_code=country_code,
                postal_code=postal_code,
            )

            if postal_area_id:
                postal_area_resolved_count += 1

            precision_level = _precision_level(
                latitude=latitude,
                longitude=longitude,
                street=street,
                postal_code=postal_code,
                city=city,
                mlc_territory_area_id=(
                    mlc_territory_area_id
                ),
            )

            has_geography = (
                precision_level != "unknown"
            )

            confidence_level = _confidence_level(
                status,
                has_geography=has_geography,
            )

            resolution_method = _resolution_method(
                status=status,
                latitude=latitude,
                longitude=longitude,
                street=street,
                postal_code=postal_code,
                city=city,
            )

            coordinate_origin = _coordinate_origin(
                latitude,
                longitude,
                raw,
            )

            source_a = _safe_dict(
                raw.get("odoo_address")
            )
            source_b = _safe_dict(
                raw.get("legacy_cyclos_address")
            )

            sources = []

            source_provider = _clean_text(
                row["source_provider"]
            )

            if source_provider:
                sources.append({
                    "source": source_provider,
                    "role": "canonical_enrichment",
                })

            if source_a:
                sources.append({
                    "source": "legacy_odoo_address",
                    "role": "migration_evidence",
                    "has_coordinates": (
                        source_a.get("latitude") is not None
                        and source_a.get("longitude") is not None
                    ),
                })

            if source_b:
                sources.append({
                    "source": "legacy_cyclos_address",
                    "role": "migration_evidence",
                    "has_coordinates": (
                        source_b.get("latitude") is not None
                        and source_b.get("longitude") is not None
                    ),
                })

            trace = {
                "migration_contract": "GEO001C",
                "legacy_geo_match_status": status,
                "legacy_geo_distance_meters": raw.get(
                    "geo_distance_meters"
                ),
                "coordinate_origin": coordinate_origin,
                "postal_area_resolved": bool(
                    postal_area_id
                ),
                "country_code": country_code,
            }

            source_timestamp = (
                _clean_text(row["updated_at"])
                or _clean_text(row["fetched_at"])
            )

            if not source_timestamp:
                raise ValueError(
                    "Professionnel sans timestamp source : "
                    f"{professional_ref}"
                )

            conn.execute(
                """
                INSERT INTO actor_geography (
                    actor_ref,
                    actor_family,
                    mlc_territory_area_id,
                    postal_area_id,
                    commune_area_id,
                    street,
                    postal_code,
                    city,
                    latitude,
                    longitude,
                    precision_level,
                    confidence_level,
                    resolution_method,
                    resolution_sources_json,
                    resolution_trace_json,
                    resolved_at,
                    updated_at
                )
                VALUES (
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?
                )

                ON CONFLICT(actor_ref) DO UPDATE SET
                    actor_family =
                        excluded.actor_family,
                    mlc_territory_area_id =
                        excluded.mlc_territory_area_id,
                    postal_area_id =
                        excluded.postal_area_id,
                    commune_area_id =
                        excluded.commune_area_id,
                    street =
                        excluded.street,
                    postal_code =
                        excluded.postal_code,
                    city =
                        excluded.city,
                    latitude =
                        excluded.latitude,
                    longitude =
                        excluded.longitude,
                    precision_level =
                        excluded.precision_level,
                    confidence_level =
                        excluded.confidence_level,
                    resolution_method =
                        excluded.resolution_method,
                    resolution_sources_json =
                        excluded.resolution_sources_json,
                    resolution_trace_json =
                        excluded.resolution_trace_json,
                    resolved_at =
                        excluded.resolved_at,
                    updated_at =
                        excluded.updated_at
                """,
                (
                    professional_ref,
                    "P",
                    mlc_territory_area_id,
                    postal_area_id,
                    None,
                    street,
                    postal_code,
                    city,
                    latitude,
                    longitude,
                    precision_level,
                    confidence_level,
                    resolution_method,
                    _json_dump(sources),
                    _json_dump(trace),
                    source_timestamp,
                    source_timestamp,
                ),
            )

            precision_counts[precision_level] += 1
            confidence_counts[confidence_level] += 1
            method_counts[resolution_method] += 1
            status_counts[status] += 1

        conn.commit()

        return {
            "mlc_id": normalized_mlc_id,
            "professional_count": len(rows),
            "resolved_count": sum(
                precision_counts.values()
            ),
            "postal_area_resolved_count":
                postal_area_resolved_count,
            "precision_counts":
                dict(sorted(precision_counts.items())),
            "confidence_counts":
                dict(sorted(confidence_counts.items())),
            "resolution_method_counts":
                dict(sorted(method_counts.items())),
            "legacy_status_counts":
                dict(sorted(status_counts.items())),
        }

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()
