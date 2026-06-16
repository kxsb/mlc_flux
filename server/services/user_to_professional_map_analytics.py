from __future__ import annotations

import json
import hashlib
import math
import sqlite3
from datetime import date
from pathlib import Path
from typing import Any, Iterable


APP_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = APP_DIR / "server" / "data"
INSTANCES_DIR = DATA_DIR / "instances"
POSTAL_AREAS_PATH = DATA_DIR / "consumption_postal_areas.json"


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"none", "null", "nan", "na", "n/a"}:
        return None
    return text


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_iso_date(value: str | None, field_name: str) -> str | None:
    value = _clean_text(value)
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10]).isoformat()
    except ValueError as exc:
        raise ValueError(f"{field_name} doit être au format YYYY-MM-DD") from exc


def _qident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _db_path(mlc_id: str) -> Path:
    return INSTANCES_DIR / mlc_id / "mlcflux.db"


def _connect(mlc_id: str) -> sqlite3.Connection:
    db_path = _db_path(mlc_id)
    if not db_path.exists():
        raise FileNotFoundError(f"Base SQLite introuvable pour l'instance {mlc_id}: {db_path}")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone() is not None


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    if not _table_exists(conn, table):
        return set()
    return {
        row["name"]
        for row in conn.execute(f"PRAGMA table_info({_qident(table)})")
    }


def _iter_coordinates(node: Any) -> Iterable[tuple[float, float]]:
    if isinstance(node, dict):
        if "coordinates" in node:
            yield from _iter_coordinates(node["coordinates"])
        else:
            for value in node.values():
                yield from _iter_coordinates(value)
    elif isinstance(node, list):
        if len(node) >= 2 and all(isinstance(x, (int, float)) for x in node[:2]):
            lon = float(node[0])
            lat = float(node[1])
            if -180 <= lon <= 180 and -90 <= lat <= 90:
                yield lon, lat
        else:
            for item in node:
                yield from _iter_coordinates(item)


def _centroid_from_geojson(value: Any) -> dict[str, float] | None:
    coords = list(_iter_coordinates(value))
    if not coords:
        return None
    lon = sum(item[0] for item in coords) / len(coords)
    lat = sum(item[1] for item in coords) / len(coords)
    if not (math.isfinite(lat) and math.isfinite(lon)):
        return None
    return {"latitude": lat, "longitude": lon}


def _load_postal_areas() -> dict[str, dict[str, Any]]:
    if not POSTAL_AREAS_PATH.exists():
        return {}

    try:
        payload = json.loads(POSTAL_AREAS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}

    if isinstance(payload, dict):
        items = payload.items()
    elif isinstance(payload, list):
        items = []
        for item in payload:
            if isinstance(item, dict):
                postal_code = (
                    item.get("postal_code")
                    or item.get("code_postal")
                    or item.get("zip")
                    or item.get("id")
                )
                if postal_code:
                    items.append((postal_code, item))
    else:
        items = []

    areas: dict[str, dict[str, Any]] = {}
    for key, area in items:
        if not isinstance(area, dict):
            continue

        if str(key).startswith("__"):
            continue

        postal_code = _clean_text(
            area.get("postal_code")
            or area.get("code_postal")
            or area.get("zip")
            or key
        )
        if not postal_code or len(postal_code) != 5 or not postal_code.isdigit():
            continue

        centroid = None
        for candidate_key in [
            "centroid",
            "center",
            "feature_collection",
            "geojson",
            "geometry",
            "features",
        ]:
            if candidate_key in area:
                centroid = _centroid_from_geojson(area[candidate_key])
                if centroid:
                    break

        if not centroid:
            centroid = _centroid_from_geojson(area)

        areas[postal_code] = {
            "postal_code": postal_code,
            "label": _clean_text(area.get("label") or area.get("name") or area.get("city")),
            "feature_collection": area.get("feature_collection") or area.get("geojson") or area,
            "centroid": centroid,
        }

    return areas


def _load_professional_identity(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}

    if _table_exists(conn, "professional_enrichment"):
        cols = _columns(conn, "professional_enrichment")
        wanted = [
            "professional_ref",
            "display_name",
            "legal_name",
            "industry_name",
            "short_description",
            "detailed_activity",
            "keywords",
            "website",
        ]
        selected = [c for c in wanted if c in cols]
        if "professional_ref" in selected:
            for row in conn.execute(
                f"SELECT {', '.join(_qident(c) for c in selected)} FROM professional_enrichment"
            ):
                data = dict(row)
                ref = _clean_text(data.get("professional_ref"))
                if not ref:
                    continue
                name = (
                    _clean_text(data.get("display_name"))
                    or _clean_text(data.get("legal_name"))
                    or ref
                )
                index[ref] = {
                    "professional_ref": ref,
                    "name": name,
                    "label": f"{ref} - {name}" if name != ref else ref,
                    "industry_name": _clean_text(data.get("industry_name")),
                    "short_description": _clean_text(data.get("short_description")),
                    "detailed_activity": _clean_text(data.get("detailed_activity")),
                    "keywords": _clean_text(data.get("keywords")),
                    "website": _clean_text(data.get("website")),
                    "identity_source": "professional_enrichment",
                }

    if _table_exists(conn, "odoo_professional_enrichment"):
        cols = _columns(conn, "odoo_professional_enrichment")
        wanted = [
            "professional_ref",
            "odoo_name",
            "industry_name",
            "detailed_activity",
            "keywords",
        ]
        selected = [c for c in wanted if c in cols]
        if "professional_ref" in selected:
            for row in conn.execute(
                f"SELECT {', '.join(_qident(c) for c in selected)} FROM odoo_professional_enrichment"
            ):
                data = dict(row)
                ref = _clean_text(data.get("professional_ref"))
                if not ref or ref in index:
                    continue
                name = _clean_text(data.get("odoo_name")) or ref
                index[ref] = {
                    "professional_ref": ref,
                    "name": name,
                    "label": f"{ref} - {name}" if name != ref else ref,
                    "industry_name": _clean_text(data.get("industry_name")),
                    "short_description": None,
                    "detailed_activity": _clean_text(data.get("detailed_activity")),
                    "keywords": _clean_text(data.get("keywords")),
                    "website": None,
                    "identity_source": "odoo_professional_enrichment",
                }

    return index


def _period_bounds(conn: sqlite3.Connection) -> dict[str, str | None]:
    row = conn.execute("""
        SELECT
            MIN(substr(date, 1, 10)) AS min_date,
            MAX(substr(date, 1, 10)) AS max_date
        FROM transaction_semantics
        WHERE is_economic_activity = 1
          AND from_actor_family IN ('individual', 'individual_device')
          AND to_actor_family = 'professional'
    """).fetchone()
    return {
        "min_date": row["min_date"] if row else None,
        "max_date": row["max_date"] if row else None,
    }


def _resolve_period(
    conn: sqlite3.Connection,
    start: str | None,
    end: str | None,
) -> tuple[str | None, str | None, dict[str, str | None]]:
    bounds = _period_bounds(conn)
    start_date = _parse_iso_date(start, "start") or bounds["min_date"]
    end_date = _parse_iso_date(end, "end") or bounds["max_date"]
    return start_date, end_date, bounds


def _route_rows(
    conn: sqlite3.Connection,
    *,
    start: str | None,
    end: str | None,
    limit_routes: int,
) -> list[sqlite3.Row]:
    clauses = [
        "t.is_economic_activity = 1",
        "t.from_actor_family IN ('individual', 'individual_device')",
        "t.to_actor_family = 'professional'",
    ]
    params: list[Any] = []

    if start:
        clauses.append("substr(t.date, 1, 10) >= ?")
        params.append(start)
    if end:
        clauses.append("substr(t.date, 1, 10) <= ?")
        params.append(end)

    where_sql = " AND ".join(clauses)

    return list(conn.execute(
        f"""
        SELECT
            u.postal_code AS source_postal_code,
            MAX(u.city) AS source_city,
            t.to_label AS professional_ref,
            MAX(p.postal_code) AS professional_postal_code,
            MAX(p.city) AS professional_city,
            MAX(p.latitude) AS professional_latitude,
            MAX(p.longitude) AS professional_longitude,
            COUNT(*) AS tx_count,
            COUNT(DISTINCT t.from_label) AS distinct_users,
            ROUND(SUM(t.amount), 2) AS volume,
            MIN(substr(t.date, 1, 10)) AS first_date,
            MAX(substr(t.date, 1, 10)) AS last_date
        FROM transaction_semantics t
        JOIN actor_territorial_enrichment u
          ON u.actor_ref = t.from_label
        JOIN actor_territorial_enrichment p
          ON p.actor_ref = t.to_label
        WHERE {where_sql}
        GROUP BY u.postal_code, t.to_label
        ORDER BY volume DESC, tx_count DESC, source_postal_code ASC, professional_ref ASC
        LIMIT ?
        """,
        [*params, limit_routes],
    ))


def _coverage_stats(
    conn: sqlite3.Connection,
    *,
    start: str | None,
    end: str | None,
) -> dict[str, Any]:
    clauses = [
        "t.is_economic_activity = 1",
        "t.from_actor_family IN ('individual', 'individual_device')",
        "t.to_actor_family = 'professional'",
    ]
    params: list[Any] = []

    if start:
        clauses.append("substr(t.date, 1, 10) >= ?")
        params.append(start)
    if end:
        clauses.append("substr(t.date, 1, 10) <= ?")
        params.append(end)

    where_sql = " AND ".join(clauses)

    row = conn.execute(
        f"""
        SELECT
            COUNT(*) AS tx_count,
            COUNT(DISTINCT t.from_label) AS distinct_users,
            COUNT(DISTINCT t.to_label) AS distinct_professionals,
            ROUND(SUM(t.amount), 2) AS volume,
            SUM(CASE WHEN u.postal_code IS NOT NULL THEN 1 ELSE 0 END) AS tx_with_user_cp,
            SUM(CASE WHEN p.postal_code IS NOT NULL THEN 1 ELSE 0 END) AS tx_with_professional_cp,
            SUM(CASE WHEN u.postal_code IS NOT NULL AND p.postal_code IS NOT NULL THEN 1 ELSE 0 END) AS tx_with_both_cp,
            COUNT(DISTINCT CASE WHEN u.postal_code IS NOT NULL THEN t.from_label END) AS users_with_cp,
            COUNT(DISTINCT CASE WHEN p.postal_code IS NOT NULL THEN t.to_label END) AS professionals_with_cp
        FROM transaction_semantics t
        LEFT JOIN actor_territorial_enrichment u
          ON u.actor_ref = t.from_label
        LEFT JOIN actor_territorial_enrichment p
          ON p.actor_ref = t.to_label
        WHERE {where_sql}
        """,
        params,
    ).fetchone()

    if not row:
        return {}

    tx_count = _safe_int(row["tx_count"])
    volume = _safe_float(row["volume"])
    tx_with_both_cp = _safe_int(row["tx_with_both_cp"])

    return {
        "tx_count": tx_count,
        "distinct_users": _safe_int(row["distinct_users"]),
        "distinct_professionals": _safe_int(row["distinct_professionals"]),
        "volume": volume,
        "tx_with_user_cp": _safe_int(row["tx_with_user_cp"]),
        "tx_with_professional_cp": _safe_int(row["tx_with_professional_cp"]),
        "tx_with_both_cp": tx_with_both_cp,
        "users_with_cp": _safe_int(row["users_with_cp"]),
        "professionals_with_cp": _safe_int(row["professionals_with_cp"]),
        "tx_with_both_cp_pct": round(tx_with_both_cp / tx_count * 100, 2) if tx_count else 0,
    }


def _point_from_postal_code(
    postal_code: str | None,
    postal_areas: dict[str, dict[str, Any]],
) -> tuple[dict[str, float] | None, str]:
    postal_code = _clean_text(postal_code)
    if not postal_code:
        return None, "missing_postal_code"

    area = postal_areas.get(postal_code)
    if not area:
        return None, "missing_postal_geometry"

    centroid = area.get("centroid")
    if not centroid:
        return None, "missing_postal_centroid"

    return {
        "latitude": _safe_float(centroid.get("latitude")),
        "longitude": _safe_float(centroid.get("longitude")),
    }, "postal_centroid"


def _professional_location(
    row: sqlite3.Row,
    postal_areas: dict[str, dict[str, Any]],
) -> tuple[dict[str, float] | None, str]:
    lat = row["professional_latitude"]
    lon = row["professional_longitude"]
    if lat is not None and lon is not None:
        return {
            "latitude": _safe_float(lat),
            "longitude": _safe_float(lon),
        }, "actor_territorial_coordinates"

    return _point_from_postal_code(row["professional_postal_code"], postal_areas)




def _stable_unit(value: str) -> float:
    text = str(value or "")
    h = 2166136261
    for char in text:
        h ^= ord(char)
        h = (h * 16777619) & 0xFFFFFFFF
    return h / 0xFFFFFFFF



def _extract_polygon_rings_from_feature_collection(value: Any) -> list[list[tuple[float, float]]]:
    """
    Extrait les anneaux extérieurs Polygon/MultiPolygon d'un GeoJSON.
    Retourne des points (lon, lat). Les trous sont ignorés pour le placement
    synthétique : l'objectif est visuel, pas cadastral.
    """
    if not isinstance(value, dict):
        return []

    features = []
    if value.get("type") == "FeatureCollection":
        features = value.get("features") or []
    elif value.get("type") == "Feature":
        features = [value]
    elif value.get("type") in {"Polygon", "MultiPolygon"}:
        features = [{"type": "Feature", "geometry": value}]

    rings: list[list[tuple[float, float]]] = []

    for feature in features:
        if not isinstance(feature, dict):
            continue

        geometry = feature.get("geometry")
        if not isinstance(geometry, dict):
            continue

        geometry_type = geometry.get("type")
        coordinates = geometry.get("coordinates")

        if geometry_type == "Polygon" and isinstance(coordinates, list):
            # Polygon = [outer_ring, hole1, hole2...]
            if coordinates and isinstance(coordinates[0], list):
                ring = []
                for point in coordinates[0]:
                    if (
                        isinstance(point, list)
                        and len(point) >= 2
                    ):
                        try:
                            lon = float(point[0])
                            lat = float(point[1])
                        except (TypeError, ValueError):
                            continue
                        if -180 <= lon <= 180 and -90 <= lat <= 90:
                            ring.append((lon, lat))
                if len(ring) >= 3:
                    rings.append(ring)

        elif geometry_type == "MultiPolygon" and isinstance(coordinates, list):
            # MultiPolygon = [[outer_ring, holes...], ...]
            for polygon in coordinates:
                if not polygon or not isinstance(polygon, list):
                    continue
                outer_ring = polygon[0]
                ring = []
                for point in outer_ring:
                    if (
                        isinstance(point, list)
                        and len(point) >= 2
                    ):
                        try:
                            lon = float(point[0])
                            lat = float(point[1])
                        except (TypeError, ValueError):
                            continue
                        if -180 <= lon <= 180 and -90 <= lat <= 90:
                            ring.append((lon, lat))
                if len(ring) >= 3:
                    rings.append(ring)

    return rings


def _point_in_ring(lon: float, lat: float, ring: list[tuple[float, float]]) -> bool:
    inside = False
    j = len(ring) - 1

    for i in range(len(ring)):
        xi, yi = ring[i]
        xj, yj = ring[j]

        intersects = (
            (yi > lat) != (yj > lat)
            and lon < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-12) + xi
        )

        if intersects:
            inside = not inside

        j = i

    return inside


def _point_in_any_ring(lon: float, lat: float, rings: list[list[tuple[float, float]]]) -> bool:
    return any(_point_in_ring(lon, lat, ring) for ring in rings)


def _rings_bbox(rings: list[list[tuple[float, float]]]) -> dict[str, float] | None:
    points = [point for ring in rings for point in ring]
    if not points:
        return None

    lons = [point[0] for point in points]
    lats = [point[1] for point in points]

    return {
        "min_lon": min(lons),
        "max_lon": max(lons),
        "min_lat": min(lats),
        "max_lat": max(lats),
    }


def _synthetic_point_inside_postal_polygon(
    *,
    route_id: str,
    index: int,
    source_area: dict[str, Any] | None,
) -> dict[str, float] | None:
    if not isinstance(source_area, dict):
        return None

    feature_collection = (
        source_area.get("feature_collection")
        or source_area.get("geojson")
        or source_area.get("geometry")
    )

    rings = _extract_polygon_rings_from_feature_collection(feature_collection)
    bbox = _rings_bbox(rings)

    if not rings or not bbox:
        return None

    lon_span = max(bbox["max_lon"] - bbox["min_lon"], 1e-6)
    lat_span = max(bbox["max_lat"] - bbox["min_lat"], 1e-6)

    # Rejection sampling déterministe : stable, mais dispersé dans le polygone.
    for attempt in range(160):
        seed = f"{route_id}|{index}|{attempt}"
        lon = bbox["min_lon"] + _stable_unit(seed + "|lon") * lon_span
        lat = bbox["min_lat"] + _stable_unit(seed + "|lat") * lat_span

        if _point_in_any_ring(lon, lat, rings):
            return {
                "latitude": lat,
                "longitude": lon,
            }

    return None


def _synthetic_source_points(
    *,
    route_id: str,
    center: dict[str, float] | None,
    count: int,
    source_payload: dict[str, Any],
    source_area: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """
    Points graphiques synthétiques pour l'ancien renderer canvas.

    Priorité :
    1. si un polygone postal existe, placer les points dedans ;
    2. sinon, fallback autour du centroïde postal.

    Ces points ne représentent jamais des adresses réelles. Ils sont
    déterministes, stables, et servent uniquement à éviter les pâtés visuels
    et le sur-routage depuis un centroïde unique.
    """
    if not center:
        return []

    base_lat = _safe_float(center.get("latitude"))
    base_lon = _safe_float(center.get("longitude"))

    if not (-90 <= base_lat <= 90 and -180 <= base_lon <= 180):
        return []

    count = max(1, min(12, _safe_int(count, 1)))
    points: list[dict[str, Any]] = []

    for index in range(count):
        polygon_point = _synthetic_point_inside_postal_polygon(
            route_id=route_id,
            index=index,
            source_area=source_area,
        )

        if polygon_point:
            lat = polygon_point["latitude"]
            lon = polygon_point["longitude"]
            placement = "synthetic_inside_postal_polygon"
        else:
            seed = f"{route_id}|{index}"
            angle = _stable_unit(seed + "|angle") * math.tau
            radius = 0.0012 + _stable_unit(seed + "|radius") * 0.0042

            lon_factor = max(0.35, math.cos(base_lat * math.pi / 180))

            lat = base_lat + math.sin(angle) * radius
            lon = base_lon + math.cos(angle) * radius / lon_factor
            placement = "synthetic_around_postal_centroid"

        points.append({
            "id": f"{route_id}|source-point:{index}",
            "kind": "synthetic_postal_source",
            "postal_code": source_payload.get("postal_code"),
            "city": source_payload.get("city"),
            "latitude": lat,
            "longitude": lon,
            "placement": placement,
            "is_synthetic": True,
        })

    return points


def _point_count_for_route(distinct_users: int, tx_count: int) -> int:
    """
    Nombre de brins visuels d'un faisceau.
    Suffisamment lisible, sans transformer une route dense en nuage illisible.
    """
    users = max(1, _safe_int(distinct_users, 1))
    tx = max(1, _safe_int(tx_count, 1))
    return max(1, min(12, int(math.ceil(math.sqrt(users))) + (1 if tx >= 100 else 0)))



def _default_render_center_for_mlc(mlc_id: str) -> dict[str, float] | None:
    """
    Centre de rendu local par défaut.

    Ce centre sert uniquement à éviter que quelques routes excentrées
    déforment la carte principale. Il ne modifie pas les données de fond.
    """
    normalized = str(mlc_id or "").strip().lower()

    if normalized == "gonette":
        return {"latitude": 45.75730398135515, "longitude": 4.845011431199012}

    if normalized == "graine":
        return {"latitude": 43.60559082479778, "longitude": 3.855203944030759}

    return None


def _distance_km(point_a: dict[str, Any] | None, point_b: dict[str, Any] | None) -> float | None:
    if not point_a or not point_b:
        return None

    lat1 = point_a.get("latitude")
    lon1 = point_a.get("longitude")
    lat2 = point_b.get("latitude")
    lon2 = point_b.get("longitude")

    if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
        return None

    lat1 = _safe_float(lat1)
    lon1 = _safe_float(lon1)
    lat2 = _safe_float(lat2)
    lon2 = _safe_float(lon2)

    if not (-90 <= lat1 <= 90 and -90 <= lat2 <= 90 and -180 <= lon1 <= 180 and -180 <= lon2 <= 180):
        return None

    radius = 6371.0
    dlat = (lat2 - lat1) * math.pi / 180
    dlon = (lon2 - lon1) * math.pi / 180

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1 * math.pi / 180)
        * math.cos(lat2 * math.pi / 180)
        * math.sin(dlon / 2) ** 2
    )

    return 2 * radius * math.asin(math.sqrt(a))


def _route_max_distance_from_center(
    *,
    center: dict[str, float] | None,
    source_point: dict[str, float] | None,
    professional_point: dict[str, float] | None,
) -> float | None:
    if not center:
        return None

    distances = [
        value
        for value in [
            _distance_km(center, source_point),
            _distance_km(center, professional_point),
        ]
        if value is not None
    ]

    if not distances:
        return None

    return max(distances)



def _center_from_locations(items: list[dict[str, Any]]) -> dict[str, Any]:
    points = []

    for item in items:
        location = item.get("location") or item
        lat = location.get("latitude")
        lon = location.get("longitude")

        if lat is None or lon is None:
            continue

        lat = _safe_float(lat)
        lon = _safe_float(lon)

        if -90 <= lat <= 90 and -180 <= lon <= 180:
            points.append((lat, lon))

    if not points:
        return {
            "has_coordinates": False,
            "latitude": None,
            "longitude": None,
        }

    return {
        "has_coordinates": True,
        "latitude": sum(p[0] for p in points) / len(points),
        "longitude": sum(p[1] for p in points) / len(points),
    }


def _actor_map_table_summary_for_payload(conn: sqlite3.Connection) -> dict[str, Any]:
    if not _table_exists(conn, "actor_map_locations"):
        return {"available": False}

    row = conn.execute("""
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN actor_family = 'U' THEN 1 ELSE 0 END) AS users,
            SUM(CASE WHEN actor_family = 'P' THEN 1 ELSE 0 END) AS professionals,
            SUM(CASE WHEN cartographiable = 1 THEN 1 ELSE 0 END) AS cartographiable,
            SUM(CASE WHEN actor_family = 'U' AND cartographiable = 1 THEN 1 ELSE 0 END) AS users_cartographiable,
            SUM(CASE WHEN actor_family = 'P' AND cartographiable = 1 THEN 1 ELSE 0 END) AS professionals_cartographiable,
            SUM(CASE WHEN needs_geocoding = 1 THEN 1 ELSE 0 END) AS needs_geocoding,
            SUM(CASE WHEN is_anonymized = 1 THEN 1 ELSE 0 END) AS anonymized
        FROM actor_map_locations
    """).fetchone()

    return {
        "available": True,
        "total": _safe_int(row["total"]) if row else 0,
        "users": _safe_int(row["users"]) if row else 0,
        "professionals": _safe_int(row["professionals"]) if row else 0,
        "cartographiable": _safe_int(row["cartographiable"]) if row else 0,
        "users_cartographiable": _safe_int(row["users_cartographiable"]) if row else 0,
        "professionals_cartographiable": _safe_int(row["professionals_cartographiable"]) if row else 0,
        "needs_geocoding": _safe_int(row["needs_geocoding"]) if row else 0,
        "anonymized": _safe_int(row["anonymized"]) if row else 0,
    }


def _actor_map_route_centroids_for_payload(
    conn: sqlite3.Connection,
    *,
    start: str | None,
    end: str | None,
) -> dict[tuple[str, str], dict[str, Any]]:
    if not _table_exists(conn, "actor_map_locations"):
        return {}

    clauses = [
        "t.is_economic_activity = 1",
        "t.from_actor_family IN ('individual', 'individual_device')",
        "t.to_actor_family = 'professional'",
        "loc.cartographiable = 1",
        "loc.latitude IS NOT NULL",
        "loc.longitude IS NOT NULL",
    ]
    params: list[Any] = []

    if start:
        clauses.append("substr(t.date, 1, 10) >= ?")
        params.append(start)
    if end:
        clauses.append("substr(t.date, 1, 10) <= ?")
        params.append(end)

    rows = conn.execute(
        f"""
        SELECT DISTINCT
            u.postal_code AS source_postal_code,
            t.to_label AS professional_ref,
            t.from_label AS actor_ref,
            loc.latitude AS latitude,
            loc.longitude AS longitude,
            loc.precision_level AS precision_level,
            loc.location_strategy AS location_strategy,
            loc.is_anonymized AS is_anonymized
        FROM transaction_semantics t
        JOIN actor_territorial_enrichment u
          ON u.actor_ref = t.from_label
        JOIN actor_map_locations loc
          ON loc.actor_ref = t.from_label
        WHERE {" AND ".join(clauses)}
          AND u.postal_code IS NOT NULL
          AND t.to_label IS NOT NULL
        """,
        params,
    ).fetchall()

    buckets: dict[tuple[str, str], dict[str, Any]] = {}

    for row in rows:
        source_postal_code = _clean_text(row["source_postal_code"])
        professional_ref = _clean_text(row["professional_ref"])
        actor_ref = _clean_text(row["actor_ref"])
        if not source_postal_code or not professional_ref or not actor_ref:
            continue

        lat = _safe_float(row["latitude"], default=float("nan"))
        lon = _safe_float(row["longitude"], default=float("nan"))
        if not (math.isfinite(lat) and math.isfinite(lon)):
            continue
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            continue

        key = (source_postal_code, professional_ref)
        item = buckets.setdefault(key, {
            "actor_refs": set(),
            "lat_sum": 0.0,
            "lon_sum": 0.0,
            "precision_levels": set(),
            "location_strategies": set(),
            "anonymized_count": 0,
        })

        if actor_ref in item["actor_refs"]:
            continue

        item["actor_refs"].add(actor_ref)
        item["lat_sum"] += lat
        item["lon_sum"] += lon

        precision = _clean_text(row["precision_level"])
        strategy = _clean_text(row["location_strategy"])
        if precision:
            item["precision_levels"].add(precision)
        if strategy:
            item["location_strategies"].add(strategy)
        if _safe_int(row["is_anonymized"]):
            item["anonymized_count"] += 1

    result: dict[tuple[str, str], dict[str, Any]] = {}

    for key, item in buckets.items():
        count = len(item["actor_refs"])
        if count <= 0:
            continue

        result[key] = {
            "latitude": item["lat_sum"] / count,
            "longitude": item["lon_sum"] / count,
            "point_status": "actor_map_user_centroid",
            "location_source": "actor_map_locations",
            "precision_level": "aggregated_user_actor_map_locations",
            "location_strategy": "aggregated_user_locations",
            "is_anonymized": True,
            "mapped_user_count": count,
            "anonymized_user_count": item["anonymized_count"],
            "precision_levels": sorted(item["precision_levels"]),
            "location_strategies": sorted(item["location_strategies"]),
        }

    return result


def _actor_map_professional_locations_for_payload(
    conn: sqlite3.Connection,
) -> dict[str, dict[str, Any]]:
    if not _table_exists(conn, "actor_map_locations"):
        return {}

    rows = conn.execute("""
        SELECT
            actor_ref,
            latitude,
            longitude,
            precision_level,
            location_strategy,
            is_anonymized
        FROM actor_map_locations
        WHERE actor_family = 'P'
          AND cartographiable = 1
          AND latitude IS NOT NULL
          AND longitude IS NOT NULL
    """).fetchall()

    locations: dict[str, dict[str, Any]] = {}

    for row in rows:
        actor_ref = _clean_text(row["actor_ref"])
        if not actor_ref:
            continue

        lat = _safe_float(row["latitude"], default=float("nan"))
        lon = _safe_float(row["longitude"], default=float("nan"))
        if not (math.isfinite(lat) and math.isfinite(lon)):
            continue
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            continue

        precision = _clean_text(row["precision_level"]) or "unknown"

        locations[actor_ref] = {
            "latitude": lat,
            "longitude": lon,
            "point_status": f"actor_map_location:{precision}",
            "location_source": "actor_map_locations",
            "precision_level": precision,
            "location_strategy": _clean_text(row["location_strategy"]),
            "is_anonymized": bool(_safe_int(row["is_anonymized"])),
        }

    return locations


def _recompute_actor_map_point_status_counts(payload: dict[str, Any]) -> None:
    geometry = payload.setdefault("geometry", {})
    source_counts: dict[str, int] = {}
    professional_counts: dict[str, int] = {}

    for route in payload.get("routes") or []:
        source_status = _clean_text(route.get("source_point_status")) or "unknown"
        professional_status = _clean_text(route.get("professional_point_status")) or "unknown"
        source_counts[source_status] = source_counts.get(source_status, 0) + 1
        professional_counts[professional_status] = professional_counts.get(professional_status, 0) + 1

    for route in (payload.get("hidden") or {}).get("missing_geometry") or []:
        source_status = _clean_text(route.get("source_point_status")) or "unknown"
        professional_status = _clean_text(route.get("professional_point_status")) or "unknown"
        source_counts[source_status] = source_counts.get(source_status, 0) + 1
        professional_counts[professional_status] = professional_counts.get(professional_status, 0) + 1

    geometry["source_point_status_counts"] = source_counts
    geometry["professional_point_status_counts"] = professional_counts


def _enhance_sources_summary_from_actor_map_routes(payload: dict[str, Any]) -> None:
    buckets: dict[str, dict[str, Any]] = {}

    for route in payload.get("routes") or []:
        source = route.get("source") or {}
        postal_code = _clean_text(source.get("postal_code"))
        if not postal_code:
            continue

        lat = _safe_float(source.get("latitude"), default=float("nan"))
        lon = _safe_float(source.get("longitude"), default=float("nan"))
        if not (math.isfinite(lat) and math.isfinite(lon)):
            continue

        item = buckets.setdefault(postal_code, {
            "lat_sum": 0.0,
            "lon_sum": 0.0,
            "route_count": 0,
            "statuses": set(),
        })
        item["lat_sum"] += lat
        item["lon_sum"] += lon
        item["route_count"] += 1

        status = _clean_text(route.get("source_point_status"))
        if status:
            item["statuses"].add(status)

    for source in payload.get("sources") or []:
        postal_code = _clean_text(source.get("postal_code"))
        item = buckets.get(postal_code)
        if not item or not item["route_count"]:
            continue

        lat = item["lat_sum"] / item["route_count"]
        lon = item["lon_sum"] / item["route_count"]
        source["latitude"] = lat
        source["longitude"] = lon
        source["location"] = {"latitude": lat, "longitude": lon}
        source["location_source"] = "actor_map_locations_route_aggregate"
        if "actor_map_user_centroid" in item["statuses"]:
            source["point_status"] = "actor_map_user_centroid_aggregate"


def _enhance_destinations_summary_from_actor_map(
    payload: dict[str, Any],
    professional_locations: dict[str, dict[str, Any]],
) -> None:
    for destination in payload.get("destinations") or []:
        professional_ref = _clean_text(destination.get("professional_ref"))
        if not professional_ref:
            continue

        loc = professional_locations.get(professional_ref)
        if not loc:
            continue

        destination["latitude"] = loc["latitude"]
        destination["longitude"] = loc["longitude"]
        destination["location"] = {
            "latitude": loc["latitude"],
            "longitude": loc["longitude"],
        }
        destination["point_status"] = loc["point_status"]
        destination["location_source"] = loc["location_source"]
        destination["precision_level"] = loc["precision_level"]
        destination["location_strategy"] = loc.get("location_strategy")
        destination["is_anonymized"] = loc.get("is_anonymized", False)



def _public_actor_source_key_for_payload(mlc_id: str, actor_ref: str) -> str:
    """
    CARTO_UP005J_ACTOR_SOURCE_POINTS

    Clé stable non réversible pour représenter un acteur U cartographiable
    sans exposer actor_ref / U_* côté API.
    """
    raw = f"{mlc_id}|actor-map-source|{actor_ref}".encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()[:18]
    return f"u_{digest}"


def _actor_map_actor_source_points_for_payload(
    conn,
    *,
    mlc_id: str,
    start: str | None,
    end: str | None,
) -> dict[tuple[str, str], list[dict[str, Any]]]:
    """
    CARTO_UP005J_ACTOR_SOURCE_POINTS

    Retourne, pour chaque route CP source -> professionnel, les points U
    anonymisés réellement contributeurs à cette route.

    Confidentialité :
    - aucun actor_ref brut n'est renvoyé ;
    - source_key = hash stable non réversible ;
    - coordonnées U = coordonnées déjà anonymisées / synthétiques dans
      actor_map_locations ;
    - on conserve les routes déjà filtrées par seuil de confidentialité côté
      payload principal.
    """
    if not _table_exists(conn, "transactions"):
        return {}

    if not _table_exists(conn, "actor_map_locations"):
        return {}

    params: list[Any] = []
    where = [
        "t.from_label LIKE 'U%'",
        "t.to_label LIKE 'P%'",
        "u.cartographiable = 1",
        "p.cartographiable = 1",
        "u.latitude IS NOT NULL",
        "u.longitude IS NOT NULL",
        "p.latitude IS NOT NULL",
        "p.longitude IS NOT NULL",
    ]

    if start:
        where.append("t.date >= ?")
        params.append(start)

    if end:
        where.append("t.date <= ?")
        params.append(end)

    sql = f"""
        SELECT
            t.from_label AS actor_ref,
            t.to_label AS professional_ref,
            COALESCE(u.postal_code, '') AS source_postal_code,
            COALESCE(u.city, '') AS source_city,
            u.latitude AS latitude,
            u.longitude AS longitude,
            u.location_strategy AS location_strategy,
            u.precision_level AS precision_level,
            u.source_provider AS source_provider,
            u.is_anonymized AS is_anonymized,
            COUNT(*) AS tx_count,
            ROUND(SUM(t.amount), 2) AS volume,
            COUNT(DISTINCT substr(t.date, 1, 10)) AS payment_day_count
        FROM transactions t
        JOIN actor_map_locations u
          ON u.actor_ref = t.from_label
        JOIN actor_map_locations p
          ON p.actor_ref = t.to_label
        WHERE {' AND '.join(where)}
        GROUP BY
            t.from_label,
            t.to_label,
            u.postal_code,
            u.city,
            u.latitude,
            u.longitude,
            u.location_strategy,
            u.precision_level,
            u.source_provider,
            u.is_anonymized
    """

    result: dict[tuple[str, str], list[dict[str, Any]]] = {}

    for row in conn.execute(sql, params).fetchall():
        source_postal_code = _clean_text(row["source_postal_code"])
        professional_ref = _clean_text(row["professional_ref"])

        if not source_postal_code or not professional_ref:
            continue

        actor_ref = _clean_text(row["actor_ref"])
        source_key = _public_actor_source_key_for_payload(mlc_id, actor_ref)

        latitude = _safe_float(row["latitude"])
        longitude = _safe_float(row["longitude"])

        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            continue

        key = (source_postal_code, professional_ref)

        result.setdefault(key, []).append({
            "id": f"{source_postal_code}->{professional_ref}|actor-source:{source_key}",
            "kind": "anonymized_actor_source",
            "source_key": source_key,
            "postal_code": source_postal_code,
            "city": _clean_text(row["source_city"]),
            "latitude": latitude,
            "longitude": longitude,
            "placement": "actor_map_locations_anonymized",
            "location_source": "actor_map_locations",
            "location_strategy": _clean_text(row["location_strategy"]),
            "precision_level": _clean_text(row["precision_level"]),
            "source_provider": _clean_text(row["source_provider"]),
            "is_synthetic": False,
            "is_anonymized": bool(row["is_anonymized"]),
            "tx_count": _safe_int(row["tx_count"]),
            "volume": round(_safe_float(row["volume"]), 2),
            "payment_day_count": _safe_int(row["payment_day_count"]),
        })

    for points in result.values():
        points.sort(key=lambda item: (
            -_safe_float(item.get("volume")),
            -_safe_int(item.get("tx_count")),
            item.get("source_key") or "",
        ))

    return result

def _enhance_payload_with_actor_map_locations(
    payload: dict[str, Any],
    *,
    mlc_id: str,
    start: str | None,
    end: str | None,
    min_users: int,
) -> dict[str, Any]:
    conn = _connect(mlc_id)
    try:
        actor_map_summary = _actor_map_table_summary_for_payload(conn)
        route_centroids = _actor_map_route_centroids_for_payload(
            conn,
            start=start,
            end=end,
        )
        professional_locations = _actor_map_professional_locations_for_payload(conn)
        actor_source_points_by_route = _actor_map_actor_source_points_for_payload(
            conn,
            mlc_id=mlc_id,
            start=start,
            end=end,
        )
    finally:
        conn.close()

    if not actor_map_summary.get("available"):
        return payload

    coverage = payload.setdefault("coverage", {})
    coverage["actor_map_locations"] = actor_map_summary

    geometry = payload.setdefault("geometry", {})
    geometry["actor_map_locations_available"] = True
    geometry["actor_map_location_count"] = actor_map_summary.get("total")
    geometry["actor_map_cartographiable_count"] = actor_map_summary.get("cartographiable")
    geometry["actor_map_user_cartographiable_count"] = actor_map_summary.get("users_cartographiable")
    geometry["actor_map_professional_cartographiable_count"] = actor_map_summary.get("professionals_cartographiable")

    payload.setdefault("privacy", {})["source_points"] = (
        "anonymized_actor_sources_with_synthetic_postal_fallback"
    )

    methodology = payload.setdefault("methodology", {})
    methodology["territorial_source"] = (
        "actor_map_locations_with_actor_territorial_enrichment_fallback"
    )
    methodology["privacy"] = (
        "Les particuliers ne sont jamais exposés individuellement. "
        "Les routes restent agrégées par code postal source et masquées "
        "si le nombre d'utilisateurs distincts est inférieur au seuil. "
        "Les points U peuvent provenir d'acteurs anonymisés stables issus "
        "d'actor_map_locations ; les identifiants internes ne sont jamais exposés. "
        "Un fallback postal synthétique reste utilisé si nécessaire."
    )

    routes_using_actor_map_source = 0
    routes_using_actor_map_destination = 0

    for route in payload.get("routes") or []:
        source_postal_code = _clean_text(route.get("source_postal_code"))
        professional_ref = _clean_text(route.get("professional_ref"))
        source = route.get("source") or {}
        destination = route.get("destination") or {}

        centroid = route_centroids.get((source_postal_code, professional_ref))

        if centroid and _safe_int(centroid.get("mapped_user_count")) >= min_users:
            source["latitude"] = centroid["latitude"]
            source["longitude"] = centroid["longitude"]
            source["location_source"] = centroid["location_source"]
            source["precision_level"] = centroid["precision_level"]
            source["location_strategy"] = centroid["location_strategy"]
            source["is_anonymized"] = True
            source["mapped_user_count"] = centroid["mapped_user_count"]
            source["anonymized_user_count"] = centroid["anonymized_user_count"]
            source["source_precision_levels"] = centroid["precision_levels"]
            source["source_location_strategies"] = centroid["location_strategies"]

            route["source"] = source
            route["source_point_status"] = centroid["point_status"]
            routes_using_actor_map_source += 1

            actor_source_points = actor_source_points_by_route.get(
                (source_postal_code, professional_ref),
                [],
            )

            if len(actor_source_points) >= min_users:
                source_points = actor_source_points
                route["source_points_mode"] = "anonymized_actor_sources"
            else:
                source_points = _synthetic_source_points(
                    route_id=_clean_text(route.get("id")) or f"{source_postal_code}->{professional_ref}",
                    center={
                        "latitude": centroid["latitude"],
                        "longitude": centroid["longitude"],
                    },
                    count=_point_count_for_route(
                        _safe_int(route.get("distinct_users")),
                        _safe_int(route.get("tx_count")),
                    ),
                    source_payload=source,
                    source_area=None,
                )
                route["source_points_mode"] = "synthetic_postal_fallback"

            route["source_points"] = source_points

            for step in route.get("timeline") or []:
                if isinstance(step, dict):
                    step["source_points"] = source_points

        loc = professional_locations.get(professional_ref)
        if loc:
            destination["latitude"] = loc["latitude"]
            destination["longitude"] = loc["longitude"]
            destination["location_source"] = loc["location_source"]
            destination["precision_level"] = loc["precision_level"]
            destination["location_strategy"] = loc.get("location_strategy")
            destination["is_anonymized"] = loc.get("is_anonymized", False)

            route["destination"] = destination
            route["professional_point_status"] = loc["point_status"]
            routes_using_actor_map_destination += 1

    geometry["routes_using_actor_map_source"] = routes_using_actor_map_source
    geometry["routes_using_actor_map_destination"] = routes_using_actor_map_destination

    _enhance_sources_summary_from_actor_map_routes(payload)
    _enhance_destinations_summary_from_actor_map(payload, professional_locations)
    _recompute_actor_map_point_status_counts(payload)

    return payload


def get_user_to_professional_map_payload(
    *,
    mlc_id: str,
    start: str | None = None,
    end: str | None = None,
    min_users: int = 3,
    limit_routes: int = 800,
    max_render_distance_km: float | None = 20.0,
) -> dict[str, Any]:
    min_users = max(1, _safe_int(min_users, 3))
    limit_routes = max(1, min(_safe_int(limit_routes, 800), 5000))

    try:
        render_distance = float(max_render_distance_km) if max_render_distance_km is not None else 0.0
    except (TypeError, ValueError):
        render_distance = 20.0

    if render_distance <= 0:
        render_center = None
        render_distance = None
    else:
        render_center = _default_render_center_for_mlc(mlc_id)

    conn = _connect(mlc_id)
    try:
        if not _table_exists(conn, "transaction_semantics"):
            raise RuntimeError("Table transaction_semantics absente.")
        if not _table_exists(conn, "actor_territorial_enrichment"):
            raise RuntimeError("Table actor_territorial_enrichment absente.")

        start_date, end_date, available_bounds = _resolve_period(conn, start, end)
        postal_areas = _load_postal_areas()
        identity_index = _load_professional_identity(conn)

        rows = _route_rows(
            conn,
            start=start_date,
            end=end_date,
            limit_routes=limit_routes,
        )
        coverage = _coverage_stats(conn, start=start_date, end=end_date)

    finally:
        conn.close()

    routes: list[dict[str, Any]] = []
    hidden_privacy: list[dict[str, Any]] = []
    hidden_geographic_outliers: list[dict[str, Any]] = []
    missing_geometry: list[dict[str, Any]] = []
    source_stats: dict[str, dict[str, Any]] = {}
    destination_stats: dict[str, dict[str, Any]] = {}

    for row in rows:
        source_postal_code = _clean_text(row["source_postal_code"])
        professional_ref = _clean_text(row["professional_ref"])
        if not source_postal_code or not professional_ref:
            continue

        tx_count = _safe_int(row["tx_count"])
        distinct_users = _safe_int(row["distinct_users"])
        volume = _safe_float(row["volume"])

        identity = identity_index.get(professional_ref, {
            "professional_ref": professional_ref,
            "name": professional_ref,
            "label": professional_ref,
            "industry_name": None,
            "identity_source": "fallback_ref",
        })

        source_point, source_point_status = _point_from_postal_code(
            source_postal_code,
            postal_areas,
        )
        professional_point, professional_point_status = _professional_location(
            row,
            postal_areas,
        )

        base = {
            "id": f"{source_postal_code}->{professional_ref}",
            "source_postal_code": source_postal_code,
            "source_city": _clean_text(row["source_city"]),
            "professional_ref": professional_ref,
            "professional_name": identity.get("name"),
            "professional_label": identity.get("label"),
            "professional_city": _clean_text(row["professional_city"]),
            "professional_postal_code": _clean_text(row["professional_postal_code"]),
            "industry_name": identity.get("industry_name"),
            "tx_count": tx_count,
            "distinct_users": distinct_users,
            "volume": volume,
            "first_date": row["first_date"],
            "last_date": row["last_date"],
            "source_point_status": source_point_status,
            "professional_point_status": professional_point_status,
            "identity_source": identity.get("identity_source"),
        }

        if distinct_users < min_users:
            hidden_privacy.append(base)
            continue

        if not source_point or not professional_point:
            missing_geometry.append(base)
            continue

        route_id = base["id"]

        source_payload = {
            "kind": "postal_code",
            "postal_code": source_postal_code,
            "city": _clean_text(row["source_city"]),
            **source_point,
        }

        destination_payload = {
            "kind": "professional",
            "professional_ref": professional_ref,
            "name": identity.get("name"),
            "label": identity.get("label"),
            "postal_code": _clean_text(row["professional_postal_code"]),
            "city": _clean_text(row["professional_city"]),
            **professional_point,
        }

        route_max_distance_km = _route_max_distance_from_center(
            center=render_center,
            source_point=source_point,
            professional_point=professional_point,
        )

        if (
            render_distance is not None
            and route_max_distance_km is not None
            and route_max_distance_km > render_distance
        ):
            hidden_geographic_outliers.append({
                **base,
                "source": source_payload,
                "destination": destination_payload,
                "route_max_distance_km": round(route_max_distance_km, 2),
                "max_render_distance_km": render_distance,
                "exclusion_reason": "outside_local_render_scope",
            })
            continue

        source_points = _synthetic_source_points(
            route_id=route_id,
            center=source_point,
            count=_point_count_for_route(distinct_users, tx_count),
            source_payload=source_payload,
            source_area=postal_areas.get(source_postal_code),
        )

        rendered = {
            **base,
            "kind": "individual_postal",
            "payer_count": distinct_users,
            "source": source_payload,
            "destination": destination_payload,
            "source_points": source_points,
            "timeline": [
                {
                    "step": 0,
                    "label": "Période complète",
                    "tx_count": tx_count,
                    "volume": volume,
                    "cumulative_tx_count": tx_count,
                    "cumulative_volume": volume,
                    "cumulative_distinct_users": distinct_users,
                    "distinct_users": distinct_users,
                    "payer_count": distinct_users,
                    "cumulative_payer_count": distinct_users,
                    "source_points": source_points,
                }
            ],
            "final_tx_count": tx_count,
            "final_volume": volume,
            "cumulative_tx_count": tx_count,
            "cumulative_volume": volume,
        }
        routes.append(rendered)

        src = source_stats.setdefault(source_postal_code, {
            "postal_code": source_postal_code,
            "city": _clean_text(row["source_city"]),
            "route_count": 0,
            "tx_count": 0,
            "distinct_professionals": set(),
            "volume": 0.0,
            "point_status": source_point_status,
            "location": source_point,
        })
        src["route_count"] += 1
        src["tx_count"] += tx_count
        src["distinct_professionals"].add(professional_ref)
        src["volume"] += volume

        dest = destination_stats.setdefault(professional_ref, {
            "professional_ref": professional_ref,
            "name": identity.get("name"),
            "label": identity.get("label"),
            "postal_code": _clean_text(row["professional_postal_code"]),
            "city": _clean_text(row["professional_city"]),
            "industry_name": identity.get("industry_name"),
            "route_count": 0,
            "tx_count": 0,
            "distinct_source_postal_codes": set(),
            "volume": 0.0,
            "point_status": professional_point_status,
            "location": professional_point,
        })
        dest["route_count"] += 1
        dest["tx_count"] += tx_count
        dest["distinct_source_postal_codes"].add(source_postal_code)
        dest["volume"] += volume

    sources = []
    for item in source_stats.values():
        location = item.get("location") or {}
        sources.append({
            **item,
            "distinct_professionals": len(item["distinct_professionals"]),
            "volume": round(item["volume"], 2),
            "latitude": location.get("latitude"),
            "longitude": location.get("longitude"),
        })
    sources.sort(key=lambda item: (-item["volume"], -item["tx_count"], item["postal_code"]))

    destinations = []
    for item in destination_stats.values():
        location = item.get("location") or {}
        destinations.append({
            **item,
            "distinct_source_postal_codes": len(item["distinct_source_postal_codes"]),
            "volume": round(item["volume"], 2),
            "latitude": location.get("latitude"),
            "longitude": location.get("longitude"),
        })
    destinations.sort(key=lambda item: (-item["volume"], -item["tx_count"], item["professional_ref"]))

    center_payload = _center_from_locations([
        *sources,
        *destinations,
    ])

    visible_tx = sum(item["tx_count"] for item in routes)
    visible_volume = round(sum(item["volume"] for item in routes), 2)
    hidden_privacy_tx = sum(item["tx_count"] for item in hidden_privacy)
    hidden_privacy_volume = round(sum(item["volume"] for item in hidden_privacy), 2)
    hidden_geographic_tx = sum(item["tx_count"] for item in hidden_geographic_outliers)
    hidden_geographic_volume = round(sum(item["volume"] for item in hidden_geographic_outliers), 2)
    missing_geometry_tx = sum(item["tx_count"] for item in missing_geometry)
    missing_geometry_volume = round(sum(item["volume"] for item in missing_geometry), 2)

    cartographiable_tx = visible_tx + hidden_geographic_tx + missing_geometry_tx
    cartographiable_volume = visible_volume + hidden_geographic_volume + missing_geometry_volume

    coverage_payload = {
        **coverage,
        # Alias compatibles avec l'ancien front professionalConsumptionMap.
        "visible_route_count": len(routes),
        "visible_tx_count": visible_tx,
        "visible_volume": visible_volume,
        "hidden_route_count": len(hidden_privacy),
        "hidden_tx_count": hidden_privacy_tx,
        "hidden_volume": hidden_privacy_volume,
        "hidden_geographic_route_count": len(hidden_geographic_outliers),
        "hidden_geographic_tx_count": hidden_geographic_tx,
        "hidden_geographic_volume": hidden_geographic_volume,
        "missing_geometry_route_count": len(missing_geometry),
        "missing_geometry_tx_count": missing_geometry_tx,
        "missing_geometry_volume": missing_geometry_volume,
        "cartographiable_tx_count": cartographiable_tx,
        "cartographiable_volume": round(cartographiable_volume, 2),
        "visible_tx_share_of_cartographiable": (
            round(visible_tx / cartographiable_tx, 6)
            if cartographiable_tx
            else None
        ),
        "visible_volume_share_of_cartographiable": (
            round(visible_volume / cartographiable_volume, 6)
            if cartographiable_volume
            else None
        ),
    }

    visible_source_area_geojson = {}
    for route in routes:
        source_cp = _clean_text(route.get("source_postal_code"))
        area = postal_areas.get(source_cp) if source_cp else None
        feature_collection = area.get("feature_collection") if isinstance(area, dict) else None

        if (
            source_cp
            and isinstance(feature_collection, dict)
            and isinstance(feature_collection.get("features"), list)
            and feature_collection.get("features")
        ):
            visible_source_area_geojson[source_cp] = feature_collection

    geometry_payload = {
        "postal_area_file_available": POSTAL_AREAS_PATH.exists(),
        "postal_area_count_loaded": len(postal_areas),
        "visible_source_area_geojson": visible_source_area_geojson,
        "visible_source_area_count": len(visible_source_area_geojson),
        "route_area_status_counts": {
            "available": len(routes),
            "missing_geometry": len(missing_geometry),
        },
        "source_point_status_counts": {},
        "professional_point_status_counts": {},
    }

    for route in routes:
        geometry_payload["source_point_status_counts"][route["source_point_status"]] = (
            geometry_payload["source_point_status_counts"].get(route["source_point_status"], 0) + 1
        )
        geometry_payload["professional_point_status_counts"][route["professional_point_status"]] = (
            geometry_payload["professional_point_status_counts"].get(route["professional_point_status"], 0) + 1
        )

    for route in missing_geometry:
        geometry_payload["source_point_status_counts"][route["source_point_status"]] = (
            geometry_payload["source_point_status_counts"].get(route["source_point_status"], 0) + 1
        )
        geometry_payload["professional_point_status_counts"][route["professional_point_status"]] = (
            geometry_payload["professional_point_status_counts"].get(route["professional_point_status"], 0) + 1
        )

    # L'ancien front sait manipuler une timeline. La nouvelle API démarre sans
    # animation temporelle fine : on expose une timeline neutre, non bloquante.
    timeline_payload = {
        "granularity": "all_period",
        "steps": [
            {
                "index": 0,
                "label": "Période complète",
                "start": start_date,
                "end": end_date,
            }
        ],
    }

    payload = {
        "mlc_id": mlc_id,
        "center": center_payload,
        "period": {
            "start": start_date,
            "end": end_date,
            "available_start": available_bounds.get("min_date"),
            "available_end": available_bounds.get("max_date"),
        },
        "parameters": {
            "min_users": min_users,
            "limit_routes": limit_routes,
            "max_render_distance_km": render_distance,
            "render_center": render_center,
        },
        "privacy": {
            "min_distinct_users_per_route": min_users,
            "aggregation": "postal_code_to_professional",
            "individual_exposure": "none",
            "source_points": "synthetic_deterministic",
        },
        "methodology": {
            "flow": "U→P economic activity",
            "transaction_filter": {
                "from_actor_family": ["individual", "individual_device"],
                "to_actor_family": "professional",
                "is_economic_activity": 1,
            },
            "territorial_source": "actor_territorial_enrichment",
            "privacy": (
                "Les particuliers ne sont jamais exposés individuellement. "
                "Les routes sont agrégées par code postal source et masquées "
                "si le nombre d'utilisateurs distincts est inférieur au seuil."
            ),
        },
        "coverage": coverage_payload,
        "geometry": geometry_payload,
        "timeline": timeline_payload,
        "summary": {
            "route_count": len(routes),
            "source_postal_code_count": len(sources),
            "destination_professional_count": len(destinations),
            "visible_route_count": len(routes),
            "visible_tx_count": visible_tx,
            "visible_volume": visible_volume,
            "hidden_privacy_route_count": len(hidden_privacy),
            "hidden_privacy_tx_count": hidden_privacy_tx,
            "hidden_privacy_volume": hidden_privacy_volume,
            "hidden_geographic_route_count": len(hidden_geographic_outliers),
            "hidden_geographic_tx_count": hidden_geographic_tx,
            "hidden_geographic_volume": hidden_geographic_volume,
            "missing_geometry_route_count": len(missing_geometry),
            "missing_geometry_tx_count": missing_geometry_tx,
            "missing_geometry_volume": missing_geometry_volume,
            "postal_area_file_available": POSTAL_AREAS_PATH.exists(),
            "postal_area_count_loaded": len(postal_areas),
        },
        "routes": routes,
        "sources": sources,
        "destinations": destinations,
        "hidden": {
            "privacy": hidden_privacy[:200],
            "geographic_outliers": hidden_geographic_outliers[:200],
            "missing_geometry": missing_geometry[:200],
        },
    }

    return _enhance_payload_with_actor_map_locations(
        payload,
        mlc_id=mlc_id,
        start=start_date,
        end=end_date,
        min_users=min_users,
    )


# ---------------------------------------------------------------------------
# CARTO_UP008B_EXTRA_FLOW_FAMILIES_PAYLOAD
# Couches cartographiques supplémentaires P→P et P→U.
#
# Ce bloc est volontairement non destructif :
# - il conserve get_user_to_professional_map_payload existant ;
# - il l'enrichit ensuite avec payload["extra_flow_families"] ;
# - le frontend actuel U→P continue de fonctionner sans changement.
# ---------------------------------------------------------------------------

def _carto_up008b_db_path(mlc_id: str) -> Path:
    mlc_id = str(mlc_id or "").strip()

    candidates = [
        Path("server/data/instances") / mlc_id / "mlcflux.db",
    ]

    if mlc_id == "gonette_sample":
        candidates.append(Path("server/data/instances/gonette/mlcflux.db"))

    candidates.append(Path("server/data/mlcflux.db"))

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return candidates[0]


def _carto_up008b_public_actor_key(mlc_id: str, actor_ref: str, prefix: str) -> str:
    raw = f"{mlc_id}|carto-extra-flow|{prefix}|{actor_ref}".encode("utf-8")
    return f"{prefix}_{hashlib.sha256(raw).hexdigest()[:18]}"


def _carto_up008b_family_for_labels(source: str, destination: str) -> str | None:
    source = str(source or "")
    destination = str(destination or "")

    if source.startswith("P") and destination.startswith("P"):
        return "P_TO_P"

    if source.startswith("P") and destination.startswith("U"):
        return "P_TO_U"

    return None


def _carto_up008b_actor_label(actor_ref: str, family: str) -> str:
    # Ne pas exposer les U_* ; les P* sont déjà des références publiques analytiques.
    actor_ref = str(actor_ref or "").strip()

    if family == "U":
        return "Particulier anonymisé"

    return actor_ref


def _carto_up008b_fetch_extra_flow_routes(
    *,
    mlc_id: str,
    start: str | None,
    end: str | None,
    limit_per_family: int = 1200,
) -> dict[str, dict[str, Any]]:
    db_path = _carto_up008b_db_path(mlc_id)

    if not db_path.exists():
        return {
            "available": False,
            "reason": f"db_not_found:{db_path}",
            "families": {},
        }

    params: list[Any] = []
    where = [
        "src.cartographiable = 1",
        "dst.cartographiable = 1",
        "src.latitude IS NOT NULL",
        "src.longitude IS NOT NULL",
        "dst.latitude IS NOT NULL",
        "dst.longitude IS NOT NULL",
        "("
        "  (t.from_label LIKE 'P%' AND t.to_label LIKE 'P%')"
        "  OR"
        "  (t.from_label LIKE 'P%' AND t.to_label LIKE 'U%')"
        ")",
    ]

    if start:
        where.append("t.date >= ?")
        params.append(start)

    if end:
        where.append("t.date <= ?")
        params.append(end)

    sql = f"""
        SELECT
            t.from_label AS source_ref,
            t.to_label AS destination_ref,
            src.latitude AS source_latitude,
            src.longitude AS source_longitude,
            src.postal_code AS source_postal_code,
            src.city AS source_city,
            src.location_strategy AS source_location_strategy,
            src.precision_level AS source_precision_level,
            src.is_anonymized AS source_is_anonymized,
            dst.latitude AS destination_latitude,
            dst.longitude AS destination_longitude,
            dst.postal_code AS destination_postal_code,
            dst.city AS destination_city,
            dst.location_strategy AS destination_location_strategy,
            dst.precision_level AS destination_precision_level,
            dst.is_anonymized AS destination_is_anonymized,
            COUNT(*) AS tx_count,
            ROUND(SUM(t.amount), 2) AS volume,
            COUNT(DISTINCT substr(t.date, 1, 10)) AS payment_day_count
        FROM transactions t
        JOIN actor_map_locations src
          ON src.actor_ref = t.from_label
        JOIN actor_map_locations dst
          ON dst.actor_ref = t.to_label
        WHERE {' AND '.join(where)}
        GROUP BY
            t.from_label,
            t.to_label,
            src.latitude,
            src.longitude,
            src.postal_code,
            src.city,
            src.location_strategy,
            src.precision_level,
            src.is_anonymized,
            dst.latitude,
            dst.longitude,
            dst.postal_code,
            dst.city,
            dst.location_strategy,
            dst.precision_level,
            dst.is_anonymized
        ORDER BY volume DESC, tx_count DESC
    """

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    try:
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()

    families: dict[str, dict[str, Any]] = {
        "P_TO_P": {
            "label": "Professionnel → professionnel",
            "routes": [],
            "tx_count": 0,
            "volume": 0.0,
            "source_count": 0,
            "destination_count": 0,
            "pair_count": 0,
        },
        "P_TO_U": {
            "label": "Professionnel → particulier",
            "routes": [],
            "tx_count": 0,
            "volume": 0.0,
            "source_count": 0,
            "destination_count": 0,
            "pair_count": 0,
        },
    }

    sources_by_family: dict[str, set[str]] = {
        "P_TO_P": set(),
        "P_TO_U": set(),
    }
    destinations_by_family: dict[str, set[str]] = {
        "P_TO_P": set(),
        "P_TO_U": set(),
    }

    for row in rows:
        source_ref = str(row["source_ref"] or "").strip()
        destination_ref = str(row["destination_ref"] or "").strip()
        flow_family = _carto_up008b_family_for_labels(source_ref, destination_ref)

        if flow_family not in families:
            continue

        if len(families[flow_family]["routes"]) >= limit_per_family:
            continue

        source_family = "P"
        destination_family = "P" if flow_family == "P_TO_P" else "U"

        source_key = _carto_up008b_public_actor_key(mlc_id, source_ref, "p")
        destination_key = _carto_up008b_public_actor_key(
            mlc_id,
            destination_ref,
            "p" if destination_family == "P" else "u",
        )

        tx_count = int(row["tx_count"] or 0)
        volume = float(row["volume"] or 0.0)
        payment_day_count = int(row["payment_day_count"] or 0)

        route = {
            "id": f"{flow_family}:{source_key}->{destination_key}",
            "flow_family": flow_family,
            "flow_direction": "P_TO_P" if flow_family == "P_TO_P" else "P_TO_U",
            "source_key": source_key,
            "destination_key": destination_key,
            "source_family": source_family,
            "destination_family": destination_family,
            "tx_count": tx_count,
            "volume": round(volume, 2),
            "payment_day_count": payment_day_count,
            "average_payment": round(volume / tx_count, 2) if tx_count else 0,
            "source": {
                "type": "professional",
                "key": source_key,
                "label": _carto_up008b_actor_label(source_ref, "P"),
                "postal_code": row["source_postal_code"] or "",
                "city": row["source_city"] or "",
                "latitude": float(row["source_latitude"]),
                "longitude": float(row["source_longitude"]),
                "location_strategy": row["source_location_strategy"] or "",
                "precision_level": row["source_precision_level"] or "",
                "is_anonymized": bool(row["source_is_anonymized"]),
            },
            "destination": {
                "type": "professional" if destination_family == "P" else "individual",
                "key": destination_key,
                "label": _carto_up008b_actor_label(destination_ref, destination_family),
                "postal_code": row["destination_postal_code"] or "",
                "city": row["destination_city"] or "",
                "latitude": float(row["destination_latitude"]),
                "longitude": float(row["destination_longitude"]),
                "location_strategy": row["destination_location_strategy"] or "",
                "precision_level": row["destination_precision_level"] or "",
                "is_anonymized": bool(row["destination_is_anonymized"]),
            },
        }

        families[flow_family]["routes"].append(route)
        families[flow_family]["tx_count"] += tx_count
        families[flow_family]["volume"] = round(families[flow_family]["volume"] + volume, 2)

        sources_by_family[flow_family].add(source_key)
        destinations_by_family[flow_family].add(destination_key)

    for flow_family, family_payload in families.items():
        family_payload["source_count"] = len(sources_by_family[flow_family])
        family_payload["destination_count"] = len(destinations_by_family[flow_family])
        family_payload["pair_count"] = len(family_payload["routes"])

    return {
        "available": True,
        "source": "transactions_join_actor_map_locations",
        "privacy": {
            "professional_refs_exposed": True,
            "individual_refs_exposed": False,
            "individual_keys": "stable_sha256_prefix_non_reversible",
            "individual_locations": "actor_map_locations_anonymized_or_synthetic",
        },
        "families": families,
    }



# CARTO_UP008D_RESTORE_NODE_COLORS_LABELS
# Réutilise les noms professionnels déjà présents dans le payload U→P
# pour améliorer les labels des routes P→P / P→U.
def _carto_up008d_professional_label_index_from_payload(payload: dict[str, Any]) -> dict[str, str]:
    labels: dict[str, str] = {}

    def register(ref: Any, *candidates: Any) -> None:
        ref = _clean_text(ref)
        if not ref or not ref.startswith("P"):
            return

        for candidate in candidates:
            label = _clean_text(candidate)
            if label and label != ref:
                labels.setdefault(ref, label)
                return

    for destination in payload.get("destinations") or []:
        register(
            destination.get("professional_ref"),
            destination.get("label"),
            destination.get("name"),
            destination.get("display_name"),
        )

    for route in payload.get("routes") or []:
        destination = route.get("destination") or {}
        register(
            route.get("professional_ref") or destination.get("professional_ref"),
            destination.get("label"),
            destination.get("name"),
            route.get("professional_name"),
        )

    return labels


def _carto_up008d_apply_professional_labels_to_extra_flow_families(
    payload: dict[str, Any],
    extra: dict[str, Any],
) -> None:
    labels = _carto_up008d_professional_label_index_from_payload(payload)

    if not labels:
        return

    for family_payload in (extra.get("families") or {}).values():
        for route in family_payload.get("routes") or []:
            for endpoint_name in ("source", "destination"):
                endpoint = route.get(endpoint_name) or {}

                if endpoint.get("type") != "professional":
                    continue

                current_label = _clean_text(endpoint.get("label"))
                ref = current_label if current_label.startswith("P") else ""

                if not ref:
                    continue

                better_label = labels.get(ref)
                if not better_label:
                    continue

                endpoint["professional_ref"] = ref
                endpoint["label"] = better_label
                endpoint["name"] = better_label

                if endpoint_name == "source":
                    route["source_label"] = better_label
                else:
                    route["destination_label"] = better_label


_carto_up008b_base_get_user_to_professional_map_payload = get_user_to_professional_map_payload


def get_user_to_professional_map_payload(*args, **kwargs):
    payload = _carto_up008b_base_get_user_to_professional_map_payload(*args, **kwargs)

    mlc_id = kwargs.get("mlc_id")
    start = kwargs.get("start")
    end = kwargs.get("end")

    if mlc_id is None and args:
        mlc_id = args[0]

    extra_flow_families = _carto_up008b_fetch_extra_flow_routes(
        mlc_id=str(mlc_id or ""),
        start=start,
        end=end,
    )

    _carto_up008d_apply_professional_labels_to_extra_flow_families(
        payload,
        extra_flow_families,
    )

    payload["extra_flow_families"] = extra_flow_families

    payload.setdefault("methodology", {})["extra_flow_families"] = (
        "CARTO_UP008B: P→P and P→U routes are computed from transactions "
        "joined with actor_map_locations. Individual destinations are hashed "
        "and never expose U_* identifiers."
    )

    return payload


# ---------------------------------------------------------------------------
# CARTO_UP008F_DEDUP_PRO_LABEL_PREFIX
# Nettoyage final des labels professionnels dans le payload cartographique.
# Corrige les cas "P0001 - P0001 - Nom".
# ---------------------------------------------------------------------------

def _carto_up008f_extract_professional_ref_from_label(value: Any) -> str:
    import re
    text = _clean_text(value)
    match = re.match(r"^(P[0-9]{4,})\b", text)
    return match.group(1) if match else ""


def _carto_up008f_deduplicate_professional_label(value: Any, ref: str = "") -> str:
    import re
    label = _clean_text(value)
    ref = _clean_text(ref) or _carto_up008f_extract_professional_ref_from_label(label)

    if not label:
        return ref

    if not ref:
        return label

    # Cas : P0001 - P0001 - Nom
    pattern = re.compile(
        rf"^({re.escape(ref)})\s*[-–—]\s*{re.escape(ref)}\s*[-–—]\s*",
        re.IGNORECASE,
    )

    while pattern.search(label):
        label = pattern.sub(rf"{ref} - ", label).strip()

    # Cas : P0001 P0001 - Nom
    pattern_space = re.compile(
        rf"^({re.escape(ref)})\s+{re.escape(ref)}\s*[-–—]\s*",
        re.IGNORECASE,
    )

    while pattern_space.search(label):
        label = pattern_space.sub(rf"{ref} - ", label).strip()

    return label


def _carto_up008f_cleanup_endpoint_label(endpoint: dict[str, Any]) -> None:
    if not isinstance(endpoint, dict):
        return

    if endpoint.get("type") != "professional":
        return

    ref = (
        _clean_text(endpoint.get("professional_ref"))
        or _carto_up008f_extract_professional_ref_from_label(endpoint.get("label"))
        or _carto_up008f_extract_professional_ref_from_label(endpoint.get("name"))
        or _carto_up008f_extract_professional_ref_from_label(endpoint.get("display_label"))
    )

    if ref:
        endpoint["professional_ref"] = ref

    for key in ("label", "name", "display_label"):
        if key in endpoint:
            endpoint[key] = _carto_up008f_deduplicate_professional_label(endpoint.get(key), ref)


def _carto_up008f_cleanup_payload_labels(payload: dict[str, Any]) -> None:
    # Destinations/sources du payload principal.
    for destination in payload.get("destinations") or []:
        _carto_up008f_cleanup_endpoint_label(destination)

    for source in payload.get("sources") or []:
        _carto_up008f_cleanup_endpoint_label(source)

    for route in payload.get("routes") or []:
        destination = route.get("destination")
        source = route.get("source")

        if isinstance(source, dict):
            _carto_up008f_cleanup_endpoint_label(source)
            if source.get("label"):
                route["source_label"] = source["label"]

        if isinstance(destination, dict):
            _carto_up008f_cleanup_endpoint_label(destination)
            if destination.get("label"):
                route["destination_label"] = destination["label"]

        for key in ("source_label", "destination_label"):
            if key in route:
                route[key] = _carto_up008f_deduplicate_professional_label(route.get(key))

    # Familles P→P / P→U.
    extra = payload.get("extra_flow_families") or {}

    for family_payload in (extra.get("families") or {}).values():
        for route in family_payload.get("routes") or []:
            source = route.get("source")
            destination = route.get("destination")

            if isinstance(source, dict):
                _carto_up008f_cleanup_endpoint_label(source)
                if source.get("label"):
                    route["source_label"] = source["label"]

            if isinstance(destination, dict):
                _carto_up008f_cleanup_endpoint_label(destination)
                if destination.get("label"):
                    route["destination_label"] = destination["label"]

            for key in ("source_label", "destination_label"):
                if key in route:
                    route[key] = _carto_up008f_deduplicate_professional_label(route.get(key))


_carto_up008f_base_get_user_to_professional_map_payload = get_user_to_professional_map_payload


def get_user_to_professional_map_payload(*args, **kwargs):
    payload = _carto_up008f_base_get_user_to_professional_map_payload(*args, **kwargs)
    _carto_up008f_cleanup_payload_labels(payload)
    return payload


# ---------------------------------------------------------------------------
# CARTO_UP010A_PRO_SEARCH_FILTER
# Catalogue de recherche des professionnels pour la carte U/P/P.
# ---------------------------------------------------------------------------

def _carto_up010a_clean_label(value: Any) -> str:
    # CARTO_UP010A_FIX_NONE_CLEAN_LABEL
    # _clean_text(None) peut retourner None selon les helpers historiques.
    return str(_clean_text(value) or "").replace("\ufeff", "").strip()


def _carto_up010a_quote_identifier(name: str) -> str:
    return '"' + str(name).replace('"', '""') + '"'


def _carto_up010a_extract_professional_ref(value: Any) -> str:
    import re
    text = _carto_up010a_clean_label(value)
    match = re.match(r"^(P[0-9]{4,})\b", text)
    return match.group(1) if match else ""


def _carto_up010a_normalize_professional_label(ref: str, label: str) -> str:
    ref = _carto_up010a_clean_label(ref)
    label = _carto_up010a_clean_label(label)

    if not label:
        return ref

    if label.startswith(ref + " - "):
        return label

    if label == ref:
        return ref

    return f"{ref} - {label}"


def _carto_up010a_fetch_professional_label_index(mlc_id: str, refs: set[str]) -> dict[str, str]:
    import sqlite3

    db_path = _carto_up008b_db_path(mlc_id) if "_carto_up008b_db_path" in globals() else Path("server/data/instances") / mlc_id / "mlcflux.db"

    if not db_path.exists() or not refs:
        return {}

    ref_columns = [
        "actor_ref",
        "professional_ref",
        "ref",
        "code",
        "account_number",
        "number",
        "label",
    ]

    label_columns = [
        "display_name",
        "commercial_name",
        "business_name",
        "name",
        "label",
        "actor_name",
        "professional_name",
        "shop_name",
        "legal_name",
        "raison_sociale",
        "nom",
        "title",
    ]

    labels: dict[str, str] = {}

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    try:
        tables = [
            row["name"]
            for row in conn.execute("""
                SELECT name
                FROM sqlite_master
                WHERE type='table'
                ORDER BY name
            """).fetchall()
        ]

        for table in tables:
            if table in {"transactions"}:
                continue

            columns = [
                row["name"]
                for row in conn.execute(f"PRAGMA table_info({_carto_up010a_quote_identifier(table)})").fetchall()
            ]

            available_ref_columns = [col for col in ref_columns if col in columns]
            available_label_columns = [col for col in label_columns if col in columns]

            if not available_ref_columns or not available_label_columns:
                continue

            for ref_col in available_ref_columns:
                selected = [
                    f"{_carto_up010a_quote_identifier(ref_col)} AS ref_value",
                ] + [
                    f"{_carto_up010a_quote_identifier(col)} AS {_carto_up010a_quote_identifier(col)}"
                    for col in available_label_columns
                ]

                sql = (
                    "SELECT "
                    + ", ".join(selected)
                    + " FROM "
                    + _carto_up010a_quote_identifier(table)
                )

                try:
                    rows = conn.execute(sql).fetchall()
                except Exception:
                    continue

                for row in rows:
                    ref = _carto_up010a_extract_professional_ref(row["ref_value"]) or _carto_up010a_clean_label(row["ref_value"])

                    if ref not in refs or ref in labels:
                        continue

                    for label_col in available_label_columns:
                        candidate = _carto_up010a_clean_label(row[label_col])

                        if not candidate or candidate == ref or candidate.startswith("u_") or candidate.startswith("p_"):
                            continue

                        labels[ref] = _carto_up010a_normalize_professional_label(ref, candidate)
                        break
    finally:
        conn.close()

    return labels


def _carto_up010a_active_professional_index(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    active: dict[str, dict[str, Any]] = {}

    def bump(ref: Any, tx_count: Any = 0, volume: Any = 0, route_count: int = 1) -> None:
        professional_ref = _carto_up010a_extract_professional_ref(ref) or _carto_up010a_clean_label(ref)

        if not professional_ref.startswith("P"):
            return

        item = active.setdefault(professional_ref, {
            "active_route_count": 0,
            "active_tx_count": 0,
            "active_volume": 0.0,
        })

        item["active_route_count"] += route_count
        item["active_tx_count"] += _safe_int(tx_count)
        item["active_volume"] = round(item["active_volume"] + _safe_float(volume), 2)

    for route in payload.get("routes") or []:
        destination = route.get("destination") or {}
        bump(
            route.get("professional_ref") or destination.get("professional_ref") or destination.get("label"),
            route.get("tx_count"),
            route.get("volume"),
        )

    for family_payload in ((payload.get("extra_flow_families") or {}).get("families") or {}).values():
        for route in family_payload.get("routes") or []:
            source = route.get("source") or {}
            destination = route.get("destination") or {}

            if source.get("type") == "professional":
                bump(source.get("professional_ref") or source.get("label"), route.get("tx_count"), route.get("volume"))

            if destination.get("type") == "professional":
                bump(destination.get("professional_ref") or destination.get("label"), route.get("tx_count"), route.get("volume"))

    return active


def _carto_up010a_build_professional_search_catalog(
    *,
    mlc_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    import sqlite3

    db_path = _carto_up008b_db_path(mlc_id) if "_carto_up008b_db_path" in globals() else Path("server/data/instances") / mlc_id / "mlcflux.db"

    if not db_path.exists():
        return {
            "available": False,
            "professionals": [],
            "reason": f"db_not_found:{db_path}",
        }

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    try:
        rows = conn.execute("""
            SELECT
                actor_ref,
                latitude,
                longitude,
                postal_code,
                city,
                location_strategy,
                precision_level,
                cartographiable
            FROM actor_map_locations
            WHERE actor_ref LIKE 'P%'
            ORDER BY actor_ref
        """).fetchall()
    except Exception as exc:
        conn.close()
        return {
            "available": False,
            "professionals": [],
            "reason": f"query_error:{exc}",
        }
    finally:
        try:
            conn.close()
        except Exception:
            pass

    refs = {
        _carto_up010a_clean_label(row["actor_ref"])
        for row in rows
        if _carto_up010a_clean_label(row["actor_ref"]).startswith("P")
    }

    labels = _carto_up010a_fetch_professional_label_index(mlc_id, refs)
    active = _carto_up010a_active_professional_index(payload)

    professionals = []

    for row in rows:
        ref = _carto_up010a_clean_label(row["actor_ref"])

        if not ref.startswith("P"):
            continue

        latitude = _safe_float(row["latitude"])
        longitude = _safe_float(row["longitude"])
        cartographiable = bool(row["cartographiable"]) and -90 <= latitude <= 90 and -180 <= longitude <= 180

        active_item = active.get(ref, {})
        label = labels.get(ref, ref)

        professionals.append({
            "professional_ref": ref,
            "label": label,
            "search_label": label,
            "postal_code": _carto_up010a_clean_label(row["postal_code"]),
            "city": _carto_up010a_clean_label(row["city"]),
            "latitude": latitude if cartographiable else None,
            "longitude": longitude if cartographiable else None,
            "cartographiable": cartographiable,
            "location_strategy": _carto_up010a_clean_label(row["location_strategy"]),
            "precision_level": _carto_up010a_clean_label(row["precision_level"]),
            "active_on_period": bool(active_item),
            "active_route_count": _safe_int(active_item.get("active_route_count")),
            "active_tx_count": _safe_int(active_item.get("active_tx_count")),
            "active_volume": round(_safe_float(active_item.get("active_volume")), 2),
        })

    return {
        "available": True,
        "source": "actor_map_locations_plus_professional_label_lookup",
        "count": len(professionals),
        "active_count": sum(1 for item in professionals if item["active_on_period"]),
        "cartographiable_count": sum(1 for item in professionals if item["cartographiable"]),
        "professionals": professionals,
    }


_carto_up010a_base_get_user_to_professional_map_payload = get_user_to_professional_map_payload


def get_user_to_professional_map_payload(*args, **kwargs):
    payload = _carto_up010a_base_get_user_to_professional_map_payload(*args, **kwargs)

    mlc_id = kwargs.get("mlc_id")
    if mlc_id is None and args:
        mlc_id = args[0]

    payload["professional_search_catalog"] = _carto_up010a_build_professional_search_catalog(
        mlc_id=str(mlc_id or ""),
        payload=payload,
    )

    payload.setdefault("methodology", {})["professional_search_catalog"] = (
        "CARTO_UP010A: catalogue des professionnels cartographiables pour filtrage rapide. "
        "Les professionnels sans transaction active restent affichables en point grisé."
    )

    return payload


# ---------------------------------------------------------------------------
# CARTO_UP010H_SEARCH_BAR_PRO_STATS
# Enrichissement du catalogue de recherche avec statistiques reçu / émis.
# ---------------------------------------------------------------------------

def _carto_up010h_extract_ref(value):
    try:
        ref = _carto_up010a_extract_professional_ref(value)
    except Exception:
        ref = ""

    if ref:
        return ref

    try:
        text = _carto_up010a_clean_label(value)
    except Exception:
        text = str(value or "").strip()

    if text.startswith("P") and len(text) >= 5:
        return text.split(" ", 1)[0].split(" - ", 1)[0].strip()

    return ""


def _carto_up010h_route_tx_count(route):
    return _safe_int(
        route.get("tx_count")
        or route.get("transaction_count")
        or route.get("payment_count")
        or route.get("payments_count")
        or route.get("visual_tx_count")
        or 0
    )


def _carto_up010h_route_volume(route):
    return _safe_float(
        route.get("volume")
        or route.get("amount")
        or route.get("total_volume")
        or route.get("visual_volume")
        or 0
    )


def _carto_up010h_empty_stats():
    return {
        "active_route_count": 0,
        "active_tx_count": 0,
        "active_volume": 0.0,
        "received_route_count": 0,
        "received_tx_count": 0,
        "received_volume": 0.0,
        "emitted_route_count": 0,
        "emitted_tx_count": 0,
        "emitted_volume": 0.0,
    }


def _carto_up010h_bump(index, ref, direction, tx_count, volume):
    ref = _carto_up010h_extract_ref(ref)

    if not ref.startswith("P"):
        return

    item = index.setdefault(ref, _carto_up010h_empty_stats())

    item["active_route_count"] += 1
    item["active_tx_count"] += _safe_int(tx_count)
    item["active_volume"] = round(item["active_volume"] + _safe_float(volume), 2)

    if direction == "received":
        item["received_route_count"] += 1
        item["received_tx_count"] += _safe_int(tx_count)
        item["received_volume"] = round(item["received_volume"] + _safe_float(volume), 2)

    if direction == "emitted":
        item["emitted_route_count"] += 1
        item["emitted_tx_count"] += _safe_int(tx_count)
        item["emitted_volume"] = round(item["emitted_volume"] + _safe_float(volume), 2)


def _carto_up010h_compute_professional_flow_stats(payload):
    index = {}

    # U→P : le professionnel est destination, donc reçu.
    for route in payload.get("routes") or []:
        destination = route.get("destination") or {}
        ref = (
            route.get("professional_ref")
            or route.get("professionalRef")
            or destination.get("professional_ref")
            or destination.get("professionalRef")
            or destination.get("label")
            or route.get("destination_label")
            or route.get("professional_name")
        )

        _carto_up010h_bump(
            index,
            ref,
            "received",
            _carto_up010h_route_tx_count(route),
            _carto_up010h_route_volume(route),
        )

    # P→P / P→U : source pro = émis ; destination pro = reçu.
    families = ((payload.get("extra_flow_families") or {}).get("families") or {})

    for family_payload in families.values():
        for route in family_payload.get("routes") or []:
            source = route.get("source") or {}
            destination = route.get("destination") or {}

            tx_count = _carto_up010h_route_tx_count(route)
            volume = _carto_up010h_route_volume(route)

            if source.get("type") == "professional":
                _carto_up010h_bump(
                    index,
                    source.get("professional_ref") or source.get("label") or source.get("name"),
                    "emitted",
                    tx_count,
                    volume,
                )

            if destination.get("type") == "professional":
                _carto_up010h_bump(
                    index,
                    destination.get("professional_ref") or destination.get("label") or destination.get("name"),
                    "received",
                    tx_count,
                    volume,
                )

    return index


def _carto_up010h_enrich_professional_search_catalog(payload):
    catalog = payload.get("professional_search_catalog") or {}
    professionals = catalog.get("professionals") or []

    if not professionals:
        return

    stats = _carto_up010h_compute_professional_flow_stats(payload)

    for professional in professionals:
        ref = professional.get("professional_ref")
        item = stats.get(ref) or _carto_up010h_empty_stats()

        professional.update({
            "active_on_period": bool(item["active_route_count"]) or bool(professional.get("active_on_period")),
            "active_route_count": item["active_route_count"] or _safe_int(professional.get("active_route_count")),
            "active_tx_count": item["active_tx_count"] or _safe_int(professional.get("active_tx_count")),
            "active_volume": round(item["active_volume"] or _safe_float(professional.get("active_volume")), 2),

            "received_route_count": item["received_route_count"],
            "received_tx_count": item["received_tx_count"],
            "received_volume": round(item["received_volume"], 2),

            "emitted_route_count": item["emitted_route_count"],
            "emitted_tx_count": item["emitted_tx_count"],
            "emitted_volume": round(item["emitted_volume"], 2),
        })

    catalog["active_count"] = sum(1 for p in professionals if p.get("active_on_period"))
    catalog["stats_enriched"] = True
    catalog["stats_source"] = "CARTO_UP010H_SEARCH_BAR_PRO_STATS"


_carto_up010h_base_get_user_to_professional_map_payload = get_user_to_professional_map_payload


def get_user_to_professional_map_payload(*args, **kwargs):
    payload = _carto_up010h_base_get_user_to_professional_map_payload(*args, **kwargs)
    _carto_up010h_enrich_professional_search_catalog(payload)
    return payload
