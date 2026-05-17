from __future__ import annotations

import hashlib
import json
import math
import random
import sqlite3
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any


SERVER_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = SERVER_DIR / "data"
DB_PATH = DATA_DIR / "mlcflux.db"
POSTAL_AREAS_PATH = DATA_DIR / "consumption_postal_areas.json"


def _money(value: Any) -> float:
    return round(float(value or 0.0), 2)


def _ratio(value: float, base: float, digits: int = 6) -> float | None:
    if not base:
        return None
    return round(float(value) / float(base), digits)


def _clean_zip(value: Any) -> str | None:
    raw = str(value or "").strip().replace(" ", "")
    return raw or None


def _safe_date(value: str | None) -> str | None:
    raw = str(value or "").strip()
    if len(raw) >= 10 and raw[:10].count("-") == 2:
        return raw[:10]
    return None




MONTH_LABELS_FR = [
    "janv.",
    "févr.",
    "mars",
    "avr.",
    "mai",
    "juin",
    "juil.",
    "août",
    "sept.",
    "oct.",
    "nov.",
    "déc.",
]


def _parse_iso_date(value: str | None) -> date | None:
    raw = _safe_date(value)
    if not raw:
        return None

    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _format_day_label(day: date) -> str:
    return day.strftime("%d/%m/%Y")


def _format_month_label(day: date) -> str:
    return f"{MONTH_LABELS_FR[day.month - 1]} {day.year}"


def _choose_timeline_granularity(start_day: date, end_day: date) -> str:
    duration_days = max(0, (end_day - start_day).days) + 1

    if duration_days <= 120:
        return "day"

    if duration_days <= 730:
        return "week"

    return "month"


def _build_consumption_map_timeline(
    start_value: str | None,
    end_value: str | None,
) -> tuple[str, list[dict]]:
    start_day = _parse_iso_date(start_value)
    end_day = _parse_iso_date(end_value)

    if not start_day or not end_day or end_day < start_day:
        return "month", []

    granularity = _choose_timeline_granularity(start_day, end_day)
    steps: list[dict] = []

    if granularity == "day":
        cursor = start_day
        index = 0

        while cursor <= end_day:
            steps.append({
                "index": index,
                "start": cursor.isoformat(),
                "end": cursor.isoformat(),
                "label": _format_day_label(cursor),
            })
            cursor += timedelta(days=1)
            index += 1

        return granularity, steps

    if granularity == "week":
        cursor = start_day
        index = 0

        while cursor <= end_day:
            step_end = min(end_day, cursor + timedelta(days=6))
            steps.append({
                "index": index,
                "start": cursor.isoformat(),
                "end": step_end.isoformat(),
                "label": f"{_format_day_label(cursor)} → {_format_day_label(step_end)}",
            })
            cursor = step_end + timedelta(days=1)
            index += 1

        return granularity, steps

    cursor = date(start_day.year, start_day.month, 1)
    index = 0

    while cursor <= end_day:
        if cursor.month == 12:
            next_month = date(cursor.year + 1, 1, 1)
        else:
            next_month = date(cursor.year, cursor.month + 1, 1)

        month_end = next_month - timedelta(days=1)
        step_start = max(start_day, cursor)
        step_end = min(end_day, month_end)

        if step_start <= step_end:
            steps.append({
                "index": index,
                "start": step_start.isoformat(),
                "end": step_end.isoformat(),
                "label": _format_month_label(cursor),
            })
            index += 1

        cursor = next_month

    return granularity, steps


def _timeline_step_index(
    transaction_day: date,
    start_day: date,
    granularity: str,
) -> int:
    if granularity == "day":
        return max(0, (transaction_day - start_day).days)

    if granularity == "week":
        return max(0, (transaction_day - start_day).days // 7)

    return max(
        0,
        (transaction_day.year - start_day.year) * 12
        + transaction_day.month
        - start_day.month,
    )


def _build_route_timeline(step_buckets: dict[int, dict]) -> list[dict]:
    timeline = []
    cumulative_tx_count = 0
    cumulative_volume = 0.0
    cumulative_users: set[str] = set()

    for step_index in sorted(step_buckets):
        bucket = step_buckets[step_index]

        step_tx_count = int(bucket["tx_count"])
        step_volume = float(bucket["volume"])
        step_users = set(bucket["users"])

        cumulative_tx_count += step_tx_count
        cumulative_volume += step_volume
        cumulative_users |= step_users

        timeline.append({
            "step": int(step_index),
            "tx_count": step_tx_count,
            "volume": _money(step_volume),
            "distinct_users_in_step": len(step_users),
            "cumulative_tx_count": cumulative_tx_count,
            "cumulative_volume": _money(cumulative_volume),
            "cumulative_distinct_users": len(cumulative_users),
        })

    return timeline


def _load_postal_areas() -> dict:
    if not POSTAL_AREAS_PATH.exists():
        return {}

    payload = json.loads(POSTAL_AREAS_PATH.read_text(encoding="utf-8"))
    return payload.get("areas") or {}


def _iter_polygon_rings(geometry: dict):
    geo_type = geometry.get("type")
    coords = geometry.get("coordinates") or []

    if geo_type == "Polygon":
        for polygon in [coords]:
            if polygon:
                yield polygon

    elif geo_type == "MultiPolygon":
        for polygon in coords:
            if polygon:
                yield polygon


def _iter_geometries(area_record: dict):
    feature_collection = area_record.get("feature_collection") or {}
    features = feature_collection.get("features") or []

    for feature in features:
        geometry = feature.get("geometry") or {}
        if geometry.get("type") in {"Polygon", "MultiPolygon"}:
            yield geometry


def _geometry_bbox(area_record: dict) -> tuple[float, float, float, float] | None:
    xs = []
    ys = []

    for geometry in _iter_geometries(area_record):
        for polygon in _iter_polygon_rings(geometry):
            outer_ring = polygon[0] if polygon else []
            for point in outer_ring:
                if len(point) >= 2:
                    xs.append(float(point[0]))
                    ys.append(float(point[1]))

    if not xs or not ys:
        return None

    return min(xs), min(ys), max(xs), max(ys)


def _point_in_ring(lon: float, lat: float, ring: list[list[float]]) -> bool:
    inside = False
    n = len(ring)

    if n < 3:
        return False

    for i in range(n):
        x1, y1 = ring[i][0], ring[i][1]
        x2, y2 = ring[(i + 1) % n][0], ring[(i + 1) % n][1]

        intersects = ((y1 > lat) != (y2 > lat))
        if not intersects:
            continue

        denom = (y2 - y1)
        if denom == 0:
            continue

        x_intersection = (x2 - x1) * (lat - y1) / denom + x1
        if lon < x_intersection:
            inside = not inside

    return inside


def _point_in_polygon(lon: float, lat: float, polygon: list[list[list[float]]]) -> bool:
    if not polygon:
        return False

    outer = polygon[0]
    if not _point_in_ring(lon, lat, outer):
        return False

    holes = polygon[1:]
    return not any(_point_in_ring(lon, lat, hole) for hole in holes)


def _point_in_area(lon: float, lat: float, area_record: dict) -> bool:
    for geometry in _iter_geometries(area_record):
        geo_type = geometry.get("type")
        coords = geometry.get("coordinates") or []

        if geo_type == "Polygon":
            if _point_in_polygon(lon, lat, coords):
                return True

        elif geo_type == "MultiPolygon":
            for polygon in coords:
                if _point_in_polygon(lon, lat, polygon):
                    return True

    return False


def _seeded_rng(seed_text: str) -> random.Random:
    digest = hashlib.sha256(seed_text.encode("utf-8")).hexdigest()
    seed_int = int(digest[:16], 16)
    return random.Random(seed_int)


def _fallback_bbox_point(
    bbox: tuple[float, float, float, float],
    rng: random.Random,
) -> tuple[float, float]:
    min_lon, min_lat, max_lon, max_lat = bbox
    return (
        rng.uniform(min_lon, max_lon),
        rng.uniform(min_lat, max_lat),
    )


def _random_point_inside_area(
    area_record: dict,
    seed_text: str,
) -> dict | None:
    bbox = _geometry_bbox(area_record)
    if bbox is None:
        return None

    rng = _seeded_rng(seed_text)

    for _ in range(300):
        lon, lat = _fallback_bbox_point(bbox, rng)
        if _point_in_area(lon, lat, area_record):
            return {
                "longitude": round(lon, 7),
                "latitude": round(lat, 7),
                "placement": "synthetic_inside_postal_area",
            }

    # Cas très rares : géométrie complexe ou sampling malchanceux.
    lon, lat = _fallback_bbox_point(bbox, rng)
    return {
        "longitude": round(lon, 7),
        "latitude": round(lat, 7),
        "placement": "synthetic_bbox_fallback",
    }


def _strand_count(volume: float) -> int:
    value = float(volume or 0.0)

    if value >= 100_000:
        return 8
    if value >= 50_000:
        return 7
    if value >= 20_000:
        return 6
    if value >= 10_000:
        return 5
    if value >= 5_000:
        return 4
    if value >= 2_000:
        return 3
    if value >= 500:
        return 2
    return 1


def _build_source_points(
    postal_code: str,
    professional_ref: str,
    volume: float,
    area_record: dict | None,
) -> list[dict]:
    if not area_record:
        return []

    count = _strand_count(volume)
    points = []

    for index in range(count):
        seed_text = f"{postal_code}|{professional_ref}|strand:{index}"
        point = _random_point_inside_area(area_record, seed_text)

        if point is not None:
            points.append(point)

    return points


def _open_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_professional_consumption_map_payload(
    *,
    start: str | None = None,
    end: str | None = None,
    min_users: int = 2,
) -> dict:
    start_date = _safe_date(start)
    end_date = _safe_date(end)

    min_users = max(1, int(min_users or 5))

    where_clauses = [
        "t.from_label LIKE 'U_%'",
        "t.to_label LIKE 'P%'",
        "NULLIF(TRIM(i.zip), '') IS NOT NULL",
        "p.geo_match_status = 'confirmed'",
        "p.cyclos_latitude IS NOT NULL",
        "p.cyclos_longitude IS NOT NULL",
    ]
    params: list[Any] = []

    if start_date:
        where_clauses.append("SUBSTR(t.date, 1, 10) >= ?")
        params.append(start_date)

    if end_date:
        where_clauses.append("SUBSTR(t.date, 1, 10) <= ?")
        params.append(end_date)

    where_sql = " AND ".join(where_clauses)

    conn = _open_db()

    gross = conn.execute(
        f"""
        SELECT
            COUNT(*) AS tx_count,
            ROUND(COALESCE(SUM(t.amount), 0), 2) AS volume,
            COUNT(DISTINCT t.from_label) AS distinct_users,
            COUNT(DISTINCT p.professional_ref) AS distinct_professionals
        FROM transactions t
        JOIN odoo_individual_enrichment i
          ON i.pseudonym = t.from_label
        JOIN odoo_professional_enrichment p
          ON p.professional_ref = SUBSTR(
                t.to_label,
                1,
                INSTR(t.to_label || ' ', ' ') - 1
             )
        WHERE {where_sql}
        """,
        params,
    ).fetchone()

    period_bounds = conn.execute(
        f"""
        SELECT
            MIN(SUBSTR(t.date, 1, 10)) AS min_date,
            MAX(SUBSTR(t.date, 1, 10)) AS max_date
        FROM transactions t
        JOIN odoo_individual_enrichment i
          ON i.pseudonym = t.from_label
        JOIN odoo_professional_enrichment p
          ON p.professional_ref = SUBSTR(
                t.to_label,
                1,
                INSTR(t.to_label || ' ', ' ') - 1
             )
        WHERE {where_sql}
        """,
        params,
    ).fetchone()

    effective_start = start_date or period_bounds["min_date"]
    effective_end = end_date or period_bounds["max_date"]

    timeline_granularity, timeline_steps = _build_consumption_map_timeline(
        effective_start,
        effective_end,
    )

    timeline_start_day = _parse_iso_date(effective_start)

    all_route_rows = conn.execute(
        f"""
        SELECT
            REPLACE(TRIM(i.zip), ' ', '') AS source_postal_code,
            p.professional_ref,
            MIN(t.to_label) AS professional_label,
            p.industry_name,
            p.detailed_activity,
            p.cyclos_city AS professional_city,
            p.cyclos_zip AS professional_zip,
            p.cyclos_latitude AS professional_latitude,
            p.cyclos_longitude AS professional_longitude,

            COUNT(*) AS tx_count,
            ROUND(COALESCE(SUM(t.amount), 0), 2) AS volume,
            COUNT(DISTINCT t.from_label) AS distinct_users

        FROM transactions t
        JOIN odoo_individual_enrichment i
          ON i.pseudonym = t.from_label
        JOIN odoo_professional_enrichment p
          ON p.professional_ref = SUBSTR(
                t.to_label,
                1,
                INSTR(t.to_label || ' ', ' ') - 1
             )

        WHERE {where_sql}

        GROUP BY
            source_postal_code,
            p.professional_ref,
            p.industry_name,
            p.detailed_activity,
            p.cyclos_city,
            p.cyclos_zip,
            p.cyclos_latitude,
            p.cyclos_longitude

        ORDER BY volume DESC, tx_count DESC, distinct_users DESC
        """,
        params,
    ).fetchall()

    postal_areas = _load_postal_areas()

    all_routes = [dict(row) for row in all_route_rows]
    visible_routes = [
        route
        for route in all_routes
        if int(route.get("distinct_users") or 0) >= min_users
    ]

    hidden_routes = [
        route
        for route in all_routes
        if int(route.get("distinct_users") or 0) < min_users
    ]

    visible_route_keys = {
        (
            _clean_zip(route.get("source_postal_code")),
            str(route.get("professional_ref") or "").strip(),
        )
        for route in visible_routes
    }

    timeline_buckets: dict[tuple[str | None, str], dict[int, dict]] = defaultdict(
        lambda: defaultdict(
            lambda: {
                "tx_count": 0,
                "volume": 0.0,
                "users": set(),
            }
        )
    )

    if timeline_steps and timeline_start_day:
        timeline_rows = conn.execute(
            f"""
            SELECT
                REPLACE(TRIM(i.zip), ' ', '') AS source_postal_code,
                p.professional_ref,
                t.from_label AS user_pseudonym,
                SUBSTR(t.date, 1, 10) AS transaction_date,
                t.amount
            FROM transactions t
            JOIN odoo_individual_enrichment i
              ON i.pseudonym = t.from_label
            JOIN odoo_professional_enrichment p
              ON p.professional_ref = SUBSTR(
                    t.to_label,
                    1,
                    INSTR(t.to_label || ' ', ' ') - 1
                 )
            WHERE {where_sql}
            """,
            params,
        ).fetchall()

        for row in timeline_rows:
            postal_code = _clean_zip(row["source_postal_code"])
            professional_ref = str(row["professional_ref"] or "").strip()
            route_key = (postal_code, professional_ref)

            if route_key not in visible_route_keys:
                continue

            transaction_day = _parse_iso_date(row["transaction_date"])
            if not transaction_day:
                continue

            step_index = _timeline_step_index(
                transaction_day,
                timeline_start_day,
                timeline_granularity,
            )

            if step_index < 0 or step_index >= len(timeline_steps):
                continue

            bucket = timeline_buckets[route_key][step_index]
            bucket["tx_count"] += 1
            bucket["volume"] += float(row["amount"] or 0.0)
            bucket["users"].add(str(row["user_pseudonym"] or ""))

    conn.close()

    source_stats = defaultdict(lambda: {
        "route_count": 0,
        "tx_count": 0,
        "volume": 0.0,
        "distinct_professionals": set(),
        "has_area": False,
        "area_feature_count": 0,
    })

    destination_stats = defaultdict(lambda: {
        "professional_ref": None,
        "professional_label": None,
        "professional_city": None,
        "professional_zip": None,
        "industry_name": None,
        "route_count": 0,
        "tx_count": 0,
        "volume": 0.0,
        "source_postal_codes": set(),
        "latitude": None,
        "longitude": None,
    })

    rendered_routes = []

    for route in visible_routes:
        postal_code = _clean_zip(route.get("source_postal_code"))
        professional_ref = str(route.get("professional_ref") or "").strip()
        volume = float(route.get("volume") or 0.0)

        area_record = postal_areas.get(postal_code or "")
        source_points = _build_source_points(
            postal_code or "",
            professional_ref,
            volume,
            area_record,
        )

        area_status = "available" if area_record else "missing"

        route_timeline = _build_route_timeline(
            timeline_buckets.get((postal_code, professional_ref), {})
        )

        rendered_route = {
            "source_postal_code": postal_code,
            "professional_ref": professional_ref,
            "professional_label": route.get("professional_label"),
            "professional_city": route.get("professional_city"),
            "professional_zip": route.get("professional_zip"),
            "industry_name": route.get("industry_name"),
            "detailed_activity": route.get("detailed_activity"),
            "destination": {
                "latitude": float(route.get("professional_latitude")),
                "longitude": float(route.get("professional_longitude")),
            },
            "tx_count": int(route.get("tx_count") or 0),
            "volume": _money(volume),
            "distinct_users": int(route.get("distinct_users") or 0),
            "strand_count": len(source_points),
            "source_points": source_points,
            "area_status": area_status,
            "timeline": route_timeline,
        }
        rendered_routes.append(rendered_route)

        src = source_stats[postal_code]
        src["route_count"] += 1
        src["tx_count"] += int(route.get("tx_count") or 0)
        src["volume"] += volume
        src["distinct_professionals"].add(professional_ref)
        src["has_area"] = bool(area_record)
        src["area_feature_count"] = int((area_record or {}).get("feature_count") or 0)

        dest = destination_stats[professional_ref]
        dest["professional_ref"] = professional_ref
        dest["professional_label"] = route.get("professional_label")
        dest["professional_city"] = route.get("professional_city")
        dest["professional_zip"] = route.get("professional_zip")
        dest["industry_name"] = route.get("industry_name")
        dest["route_count"] += 1
        dest["tx_count"] += int(route.get("tx_count") or 0)
        dest["volume"] += volume
        dest["source_postal_codes"].add(postal_code)
        dest["latitude"] = float(route.get("professional_latitude"))
        dest["longitude"] = float(route.get("professional_longitude"))

    sources = [
        {
            "postal_code": postal_code,
            "route_count": int(stats["route_count"]),
            "tx_count": int(stats["tx_count"]),
            "volume": _money(stats["volume"]),
            "distinct_professionals": len(stats["distinct_professionals"]),
            "has_area": bool(stats["has_area"]),
            "area_feature_count": int(stats["area_feature_count"]),
        }
        for postal_code, stats in source_stats.items()
    ]
    sources.sort(key=lambda item: (-item["volume"], -item["tx_count"], item["postal_code"]))

    destinations = [
        {
            "professional_ref": stats["professional_ref"],
            "professional_label": stats["professional_label"],
            "professional_city": stats["professional_city"],
            "professional_zip": stats["professional_zip"],
            "industry_name": stats["industry_name"],
            "route_count": int(stats["route_count"]),
            "tx_count": int(stats["tx_count"]),
            "volume": _money(stats["volume"]),
            "distinct_source_postal_codes": len(stats["source_postal_codes"]),
            "latitude": stats["latitude"],
            "longitude": stats["longitude"],
        }
        for stats in destination_stats.values()
    ]
    destinations.sort(key=lambda item: (-item["volume"], -item["tx_count"], item["professional_ref"]))

    visible_tx = sum(int(route.get("tx_count") or 0) for route in visible_routes)
    visible_volume = sum(float(route.get("volume") or 0.0) for route in visible_routes)
    hidden_tx = sum(int(route.get("tx_count") or 0) for route in hidden_routes)
    hidden_volume = sum(float(route.get("volume") or 0.0) for route in hidden_routes)

    gross_tx = int(gross["tx_count"] or 0)
    gross_volume = float(gross["volume"] or 0.0)

    route_area_status_counts = defaultdict(int)
    for route in rendered_routes:
        route_area_status_counts[route["area_status"]] += 1

    visible_source_area_geojson = {}
    for source in sources:
        postal_code = source.get("postal_code")
        area_record = postal_areas.get(postal_code or "")

        if not area_record:
            continue

        feature_collection = area_record.get("feature_collection")
        if feature_collection:
            visible_source_area_geojson[postal_code] = feature_collection

    return {
        "period": {
            "start": start_date,
            "end": end_date,
        },
        "privacy": {
            "min_distinct_users_per_route": min_users,
            "interpretation": (
                "Les points-source sont synthétiques et répartis dans les périmètres "
                "postaux disponibles. Ils ne représentent jamais des adresses individuelles."
            ),
        },
        "timeline": {
            "mode": "cumulative",
            "granularity": timeline_granularity,
            "step_count": len(timeline_steps),
            "steps": timeline_steps,
            "privacy_gate": (
                "Pendant l'animation, une route n'est affichée qu'à partir du moment "
                "où elle atteint cumulativement le seuil minimal de particuliers distincts."
            ),
        },
        "coverage": {
            "cartographiable_tx_count": gross_tx,
            "cartographiable_volume": _money(gross_volume),
            "visible_route_count": len(visible_routes),
            "visible_tx_count": visible_tx,
            "visible_tx_share_of_cartographiable": _ratio(visible_tx, gross_tx),
            "visible_volume": _money(visible_volume),
            "visible_volume_share_of_cartographiable": _ratio(visible_volume, gross_volume),
            "hidden_route_count": len(hidden_routes),
            "hidden_tx_count": hidden_tx,
            "hidden_volume": _money(hidden_volume),
        },
        "geometry": {
            "postal_area_file_available": POSTAL_AREAS_PATH.exists(),
            "postal_area_count_loaded": len(postal_areas),
            "route_area_status_counts": dict(route_area_status_counts),
            "visible_source_area_geojson": visible_source_area_geojson,
        },
        "sources": sources,
        "destinations": destinations,
        "routes": rendered_routes,
    }
