#!/usr/bin/env python3
"""
CARTO_LOC002 — Génération de points postaux synthétiques pour actor_map_locations.

But :
- rendre cartographiables les acteurs ayant seulement CP / ville ;
- utiliser les géométries ou centroïdes de server/data/consumption_postal_areas.json ;
- produire un point déterministe par acteur dans / autour du code postal ;
- ne manipuler aucune adresse individuelle ;
- ne modifier que les lignes precision_level = 'needs_postal_point'.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import math
import os
import random
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
POSTAL_AREAS_PATH = ROOT / "server/data/consumption_postal_areas.json"

DB_BY_MLC = {
    "graine": ROOT / "server/data/instances/graine/mlcflux.db",
    "gonette": ROOT / "server/data/instances/gonette/mlcflux.db",
}
MLC_IDS = tuple(DB_BY_MLC.keys())


def load_dotenv(path: Path = ROOT / ".env") -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def clean(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s or None


def clean_postal_code(value: Any) -> str | None:
    s = clean(value)
    if not s:
        return None
    s = s.replace(" ", "")
    if s.endswith(".0"):
        s = s[:-2]
    if s.isdigit() and len(s) < 5:
        s = s.zfill(5)
    return s or None


def qident(name: str) -> str:
    return '"' + str(name).replace('"', '""') + '"'


def to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        x = float(str(value).strip().replace(",", "."))
    except Exception:
        return None
    if not math.isfinite(x):
        return None
    return x


def valid_lat_lon(lat: Any, lon: Any) -> tuple[float, float] | None:
    la = to_float(lat)
    lo = to_float(lon)
    if la is None or lo is None:
        return None
    if -90 <= la <= 90 and -180 <= lo <= 180:
        return la, lo
    return None


def stable_rng(secret: str, key: str) -> random.Random:
    digest = hmac.new(
        secret.encode("utf-8"),
        key.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return random.Random(int.from_bytes(digest[:16], "big"))


def jitter_around_lat_lon(
    lat: float,
    lon: float,
    rng: random.Random,
    radius_m: float = 1200.0,
) -> tuple[float, float]:
    angle = rng.uniform(0, 2 * math.pi)
    radius = radius_m * math.sqrt(rng.random())

    dx_m = math.cos(angle) * radius
    dy_m = math.sin(angle) * radius

    meters_per_deg_lat = 111_320.0
    meters_per_deg_lon = max(1.0, 111_320.0 * math.cos(math.radians(lat)))

    return (
        lat + dy_m / meters_per_deg_lat,
        lon + dx_m / meters_per_deg_lon,
    )


def extract_center(area: dict[str, Any]) -> tuple[float, float] | None:
    candidates: list[tuple[Any, Any]] = []

    # format direct
    for lon_key in ("longitude", "lon", "lng", "center_lon", "centroid_lon"):
        if area.get(lon_key) is not None:
            for lat_key in ("latitude", "lat", "center_lat", "centroid_lat"):
                if area.get(lat_key) is not None:
                    candidates.append((area.get(lat_key), area.get(lon_key)))

    # formats imbriqués
    for key in ("center", "centroid", "fallback_center"):
        value = area.get(key)
        if isinstance(value, dict):
            lon = value.get("longitude", value.get("lon", value.get("lng")))
            lat = value.get("latitude", value.get("lat"))
            if lat is not None and lon is not None:
                candidates.append((lat, lon))
        elif isinstance(value, (list, tuple)) and len(value) >= 2:
            # GeoJSON convention habituelle : [lon, lat]
            candidates.append((value[1], value[0]))

    for lat, lon in candidates:
        point = valid_lat_lon(lat, lon)
        if point:
            return point

    return None


def iter_polygon_rings(geometry: dict[str, Any]):
    geo_type = geometry.get("type")
    coords = geometry.get("coordinates") or []

    if geo_type == "Polygon":
        yield coords
    elif geo_type == "MultiPolygon":
        for polygon in coords:
            yield polygon


def iter_geometries(area: dict[str, Any]):
    for key in ("geometry", "geojson"):
        value = area.get(key)
        if isinstance(value, dict):
            if value.get("type") in {"Polygon", "MultiPolygon"}:
                yield value
            elif value.get("type") == "FeatureCollection":
                for feature in value.get("features") or []:
                    geometry = feature.get("geometry") or {}
                    if geometry.get("type") in {"Polygon", "MultiPolygon"}:
                        yield geometry
            elif value.get("type") == "Feature":
                geometry = value.get("geometry") or {}
                if geometry.get("type") in {"Polygon", "MultiPolygon"}:
                    yield geometry

    fc = area.get("feature_collection")
    if isinstance(fc, dict):
        for feature in fc.get("features") or []:
            geometry = feature.get("geometry") or {}
            if geometry.get("type") in {"Polygon", "MultiPolygon"}:
                yield geometry

    features = area.get("features")
    if isinstance(features, list):
        for feature in features:
            if isinstance(feature, dict):
                geometry = feature.get("geometry") or {}
                if geometry.get("type") in {"Polygon", "MultiPolygon"}:
                    yield geometry


def geometry_bbox(area: dict[str, Any]) -> tuple[float, float, float, float] | None:
    points: list[tuple[float, float]] = []

    for geometry in iter_geometries(area):
        for polygon in iter_polygon_rings(geometry):
            for ring in polygon:
                for pair in ring:
                    if not isinstance(pair, (list, tuple)) or len(pair) < 2:
                        continue
                    lon = to_float(pair[0])
                    lat = to_float(pair[1])
                    if lon is not None and lat is not None:
                        points.append((lon, lat))

    if not points:
        return None

    lons = [p[0] for p in points]
    lats = [p[1] for p in points]
    return min(lons), min(lats), max(lons), max(lats)


def point_in_ring(lon: float, lat: float, ring: list[list[float]]) -> bool:
    inside = False
    if len(ring) < 3:
        return False

    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]

        intersects = ((yi > lat) != (yj > lat))
        if intersects:
            denom = yj - yi
            if abs(denom) > 1e-12:
                x_intersection = (xj - xi) * (lat - yi) / denom + xi
                if lon < x_intersection:
                    inside = not inside
        j = i

    return inside


def point_in_polygon(lon: float, lat: float, polygon: list[list[list[float]]]) -> bool:
    if not polygon:
        return False

    outer = polygon[0]
    holes = polygon[1:]

    if not point_in_ring(lon, lat, outer):
        return False

    return not any(point_in_ring(lon, lat, hole) for hole in holes)


def point_in_area(lon: float, lat: float, area: dict[str, Any]) -> bool:
    for geometry in iter_geometries(area):
        geo_type = geometry.get("type")
        coords = geometry.get("coordinates") or []

        if geo_type == "Polygon":
            if point_in_polygon(lon, lat, coords):
                return True
        elif geo_type == "MultiPolygon":
            for polygon in coords:
                if point_in_polygon(lon, lat, polygon):
                    return True

    return False


def synthetic_point_for_area(
    *,
    area: dict[str, Any],
    postal_code: str,
    actor_ref: str,
    mlc_id: str,
    actor_family: str,
    secret: str,
) -> dict[str, Any] | None:
    rng = stable_rng(
        secret,
        f"{mlc_id}|{postal_code}|{actor_family}|{actor_ref}|CARTO_LOC002",
    )

    bbox = geometry_bbox(area)
    if bbox:
        min_lon, min_lat, max_lon, max_lat = bbox

        for _ in range(750):
            lon = rng.uniform(min_lon, max_lon)
            lat = rng.uniform(min_lat, max_lat)
            if point_in_area(lon, lat, area):
                return {
                    "latitude": round(lat, 7),
                    "longitude": round(lon, 7),
                    "placement": "synthetic_inside_postal_area",
                }

        # Fallback dans la bbox si la géométrie est complexe ou invalide.
        lon = rng.uniform(min_lon, max_lon)
        lat = rng.uniform(min_lat, max_lat)
        return {
            "latitude": round(lat, 7),
            "longitude": round(lon, 7),
            "placement": "synthetic_inside_postal_bbox_fallback",
        }

    center = extract_center(area)
    if center:
        lat, lon = center
        lat2, lon2 = jitter_around_lat_lon(lat, lon, rng)
        return {
            "latitude": round(lat2, 7),
            "longitude": round(lon2, 7),
            "placement": "synthetic_near_postal_centroid",
        }

    return None


def load_postal_areas(path: Path = POSTAL_AREAS_PATH) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}

    payload = json.loads(path.read_text(encoding="utf-8"))
    records: list[dict[str, Any]] = []

    if isinstance(payload, list):
        records = [x for x in payload if isinstance(x, dict)]
    elif isinstance(payload, dict):
        for key in ("areas", "postal_areas", "items", "records", "centroids"):
            value = payload.get(key)
            if isinstance(value, list):
                records.extend(x for x in value if isinstance(x, dict))

        # Cas dict directement indexé par code postal.
        for key, value in payload.items():
            if isinstance(value, dict):
                pc = clean_postal_code(value.get("postal_code") or value.get("zip") or key)
                if pc and pc.isdigit():
                    item = dict(value)
                    item.setdefault("postal_code", pc)
                    records.append(item)

    areas: dict[str, dict[str, Any]] = {}
    for item in records:
        pc = clean_postal_code(
            item.get("postal_code")
            or item.get("code_postal")
            or item.get("zip")
            or item.get("postcode")
        )
        if not pc:
            continue

        # Conserver la première occurrence complète ; compléter si doublons partiels.
        if pc not in areas:
            areas[pc] = item
        else:
            existing = areas[pc]
            for k, v in item.items():
                if existing.get(k) in (None, "", [], {}) and v not in (None, "", [], {}):
                    existing[k] = v

    return areas


def fetch_candidates(con: sqlite3.Connection) -> list[sqlite3.Row]:
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    return cur.execute(
        """
        SELECT
            actor_ref,
            actor_family,
            postal_code,
            city,
            location_strategy,
            precision_level,
            latitude,
            longitude
        FROM actor_map_locations
        WHERE precision_level = 'needs_postal_point'
          AND cartographiable = 0
          AND NULLIF(TRIM(COALESCE(postal_code, '')), '') IS NOT NULL
        ORDER BY actor_family, location_strategy, actor_ref
        """
    ).fetchall()


def update_postal_point(
    con: sqlite3.Connection,
    *,
    actor_ref: str,
    lat: float,
    lon: float,
    actor_family: str,
    placement: str,
) -> None:
    precision = "postal_synthetic"

    con.execute(
        """
        UPDATE actor_map_locations
        SET
            cartographiable = 1,
            latitude = ?,
            longitude = ?,
            precision_level = ?,
            is_anonymized = CASE WHEN actor_family = 'U' THEN 1 ELSE is_anonymized END,
            source_status = CASE
                WHEN source_status IS NULL OR source_status = ''
                THEN ?
                ELSE source_status
            END,
            method_version = 'CARTO_LOC002',
            updated_at = ?
        WHERE actor_ref = ?
        """,
        (
            lat,
            lon,
            precision,
            f"postal_point:{placement}",
            now_iso(),
            actor_ref,
        ),
    )


def sync_mlc(mlc_id: str, *, dry_run: bool) -> dict[str, Any]:
    db_path = DB_BY_MLC[mlc_id]
    if not db_path.exists():
        raise FileNotFoundError(db_path)

    secret = (
        os.environ.get("MLCFLUX_LOCATION_ANON_SECRET")
        or os.environ.get("MLCFLUX_SECRET_KEY")
        or "mlcflux-dev-location-secret"
    )

    postal_areas = load_postal_areas()
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row

    candidates = fetch_candidates(con)

    counters = Counter()
    by_strategy = Counter()
    by_family = Counter()
    by_placement = Counter()
    missing_postal_codes = Counter()

    for row in candidates:
        counters["candidates"] += 1
        actor_ref = clean(row["actor_ref"])
        actor_family = clean(row["actor_family"]) or "?"
        postal_code = clean_postal_code(row["postal_code"])
        strategy = clean(row["location_strategy"]) or "unknown"

        by_strategy[strategy] += 1
        by_family[actor_family] += 1

        if not actor_ref or not postal_code:
            counters["skipped_missing_actor_or_postal_code"] += 1
            continue

        area = postal_areas.get(postal_code)
        if not area:
            counters["missing_area_record"] += 1
            missing_postal_codes[postal_code] += 1
            continue

        point = synthetic_point_for_area(
            area=area,
            postal_code=postal_code,
            actor_ref=actor_ref,
            mlc_id=mlc_id,
            actor_family=actor_family,
            secret=secret,
        )

        if not point:
            counters["no_point_generated"] += 1
            missing_postal_codes[postal_code] += 1
            continue

        counters["generated"] += 1
        by_placement[point["placement"]] += 1

        if not dry_run:
            update_postal_point(
                con,
                actor_ref=actor_ref,
                lat=point["latitude"],
                lon=point["longitude"],
                actor_family=actor_family,
                placement=point["placement"],
            )

    if not dry_run:
        con.commit()

    cur = con.cursor()
    table_counts = {
        "actor_map_locations": cur.execute(
            "SELECT COUNT(*) FROM actor_map_locations"
        ).fetchone()[0],
        "cartographiable": cur.execute(
            "SELECT COUNT(*) FROM actor_map_locations WHERE cartographiable = 1"
        ).fetchone()[0],
        "needs_postal_point_remaining": cur.execute(
            """
            SELECT COUNT(*)
            FROM actor_map_locations
            WHERE precision_level = 'needs_postal_point'
              AND cartographiable = 0
            """
        ).fetchone()[0],
        "postal_synthetic": cur.execute(
            """
            SELECT COUNT(*)
            FROM actor_map_locations
            WHERE precision_level = 'postal_synthetic'
            """
        ).fetchone()[0],
        "needs_geocoding": cur.execute(
            """
            SELECT COUNT(*)
            FROM actor_map_locations
            WHERE needs_geocoding = 1
            """
        ).fetchone()[0],
    }

    con.close()

    return {
        "mlc_id": mlc_id,
        "db_path": str(db_path),
        "dry_run": dry_run,
        "postal_area_file": str(POSTAL_AREAS_PATH),
        "postal_area_count_loaded": len(postal_areas),
        "counters": dict(sorted(counters.items())),
        "by_family": dict(sorted(by_family.items())),
        "by_strategy": dict(sorted(by_strategy.items())),
        "by_placement": dict(sorted(by_placement.items())),
        "missing_postal_codes": dict(sorted(missing_postal_codes.items())),
        "table_counts": table_counts,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mlc", choices=MLC_IDS, action="append")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json-out")
    args = parser.parse_args()

    load_dotenv()

    mlc_ids = args.mlc or list(MLC_IDS)
    dry_run = not args.write

    summaries = []
    for mlc_id in mlc_ids:
        print()
        print("========================================================================")
        print(f"sync_actor_map_postal_points — {mlc_id} — dry_run={dry_run}")
        print("========================================================================")
        summary = sync_mlc(mlc_id, dry_run=dry_run)
        summaries.append(summary)
        print(json.dumps(summary, indent=2, ensure_ascii=False))

    payload = {
        "generated_at": now_iso(),
        "dry_run": dry_run,
        "summaries": summaries,
    }

    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
