#!/usr/bin/env python3
"""
CARTO_LOC002B — Résolution fallback des points postaux restants.

But :
- traiter les quelques CP absents de consumption_postal_areas.json ;
- utiliser geo.api.gouv.fr pour récupérer un centre communal / postal ;
- générer un point synthétique déterministe autour de ce centre ;
- ne manipuler aucune adresse individuelle ;
- ne modifier que les lignes actor_map_locations encore en needs_postal_point.
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
import time
import unicodedata
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DB_BY_MLC = {
    "graine": ROOT / "server/data/instances/graine/mlcflux.db",
    "gonette": ROOT / "server/data/instances/gonette/mlcflux.db",
}
MLC_IDS = tuple(DB_BY_MLC.keys())

GEO_API_BASE = "https://geo.api.gouv.fr"
DEFAULT_SLEEP = 0.15
HTTP_TIMEOUT = 20


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


def normalize_city(value: Any) -> str:
    s = clean(value) or ""
    s = s.lower()
    s = s.replace("cedex", " ")
    s = "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )
    keep = []
    for c in s:
        keep.append(c if c.isalnum() else " ")
    return " ".join("".join(keep).split())


def qident(name: str) -> str:
    return '"' + str(name).replace('"', '""') + '"'


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
    radius_m: float = 1400.0,
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


def http_json(url: str) -> Any:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "MLCFlux-CARTO_LOC002B/1.0",
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
        body = resp.read()
        if not body:
            return None
        return json.loads(body.decode("utf-8"))


def extract_center_from_commune(item: dict[str, Any]) -> tuple[float, float] | None:
    centre = item.get("centre") or item.get("center") or {}
    if isinstance(centre, dict):
        coordinates = centre.get("coordinates")
        if isinstance(coordinates, list) and len(coordinates) >= 2:
            lon = float(coordinates[0])
            lat = float(coordinates[1])
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                return lat, lon

    geometry = item.get("geometry") or {}
    coordinates = geometry.get("coordinates")
    if isinstance(coordinates, list) and len(coordinates) >= 2:
        lon = float(coordinates[0])
        lat = float(coordinates[1])
        if -90 <= lat <= 90 and -180 <= lon <= 180:
            return lat, lon

    return None


def commune_candidates_by_postal_code(postal_code: str) -> list[dict[str, Any]]:
    query = urllib.parse.urlencode({
        "codePostal": postal_code,
        "fields": "nom,codesPostaux,centre",
        "format": "json",
        "geometry": "centre",
    })
    url = f"{GEO_API_BASE}/communes?{query}"
    payload = http_json(url)
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    return []


def commune_candidates_by_city(city: str) -> list[dict[str, Any]]:
    city_norm = normalize_city(city)
    if not city_norm:
        return []

    query = urllib.parse.urlencode({
        "nom": city_norm,
        "fields": "nom,codesPostaux,centre",
        "format": "json",
        "geometry": "centre",
        "boost": "population",
        "limit": "8",
    })
    url = f"{GEO_API_BASE}/communes?{query}"
    payload = http_json(url)
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    return []


def choose_best_candidate(
    *,
    candidates: list[dict[str, Any]],
    postal_code: str | None,
    city: str | None,
    secret: str,
    stable_key: str,
) -> tuple[dict[str, Any], str] | tuple[None, str]:
    if not candidates:
        return None, "no_candidate"

    city_norm = normalize_city(city)
    if city_norm:
        exact_city = [
            c for c in candidates
            if normalize_city(c.get("nom")) == city_norm
        ]
        if exact_city:
            candidates = exact_city

    if postal_code:
        exact_cp = [
            c for c in candidates
            if postal_code in [clean_postal_code(x) for x in (c.get("codesPostaux") or [])]
        ]
        if exact_cp:
            candidates = exact_cp

    usable = [
        c for c in candidates
        if extract_center_from_commune(c) is not None
    ]
    if not usable:
        return None, "no_candidate_with_center"

    if len(usable) == 1:
        return usable[0], "single_candidate"

    rng = stable_rng(secret, stable_key + "|choose_commune")
    return usable[rng.randrange(len(usable))], "deterministic_choice_among_candidates"


def resolve_center(
    *,
    postal_code: str | None,
    city: str | None,
    secret: str,
    stable_key: str,
    sleep: float,
) -> dict[str, Any]:
    errors: list[str] = []

    if postal_code:
        try:
            candidates = commune_candidates_by_postal_code(postal_code)
            chosen, reason = choose_best_candidate(
                candidates=candidates,
                postal_code=postal_code,
                city=city,
                secret=secret,
                stable_key=stable_key + "|postal",
            )
            if chosen:
                center = extract_center_from_commune(chosen)
                if center:
                    return {
                        "status": "resolved_by_postal_code",
                        "reason": reason,
                        "commune_name": chosen.get("nom"),
                        "postal_codes": chosen.get("codesPostaux") or [],
                        "latitude": center[0],
                        "longitude": center[1],
                    }
        except Exception as exc:
            errors.append(f"postal_code_lookup:{type(exc).__name__}:{exc}")
        finally:
            time.sleep(sleep)

    if city:
        try:
            candidates = commune_candidates_by_city(city)
            chosen, reason = choose_best_candidate(
                candidates=candidates,
                postal_code=postal_code,
                city=city,
                secret=secret,
                stable_key=stable_key + "|city",
            )
            if chosen:
                center = extract_center_from_commune(chosen)
                if center:
                    return {
                        "status": "resolved_by_city",
                        "reason": reason,
                        "commune_name": chosen.get("nom"),
                        "postal_codes": chosen.get("codesPostaux") or [],
                        "latitude": center[0],
                        "longitude": center[1],
                    }
        except Exception as exc:
            errors.append(f"city_lookup:{type(exc).__name__}:{exc}")
        finally:
            time.sleep(sleep)

    return {
        "status": "unresolved",
        "errors": errors,
    }


def fetch_candidates(con: sqlite3.Connection) -> list[sqlite3.Row]:
    con.row_factory = sqlite3.Row
    return con.execute(
        """
        SELECT
            actor_ref,
            actor_family,
            postal_code,
            city,
            location_strategy,
            precision_level
        FROM actor_map_locations
        WHERE precision_level = 'needs_postal_point'
          AND cartographiable = 0
          AND NULLIF(TRIM(COALESCE(postal_code, '')), '') IS NOT NULL
        ORDER BY postal_code, actor_family, actor_ref
        """
    ).fetchall()


def update_row(
    con: sqlite3.Connection,
    *,
    actor_ref: str,
    lat: float,
    lon: float,
    resolution_status: str,
) -> None:
    con.execute(
        """
        UPDATE actor_map_locations
        SET
            cartographiable = 1,
            latitude = ?,
            longitude = ?,
            precision_level = 'postal_synthetic',
            is_anonymized = CASE WHEN actor_family = 'U' THEN 1 ELSE is_anonymized END,
            source_status = CASE
                WHEN source_status IS NULL OR source_status = ''
                THEN ?
                ELSE source_status
            END,
            method_version = 'CARTO_LOC002B',
            updated_at = ?
        WHERE actor_ref = ?
        """,
        (
            lat,
            lon,
            f"postal_fallback:{resolution_status}",
            now_iso(),
            actor_ref,
        ),
    )


def sync_mlc(mlc_id: str, *, dry_run: bool, sleep: float) -> dict[str, Any]:
    db_path = DB_BY_MLC[mlc_id]
    if not db_path.exists():
        raise FileNotFoundError(db_path)

    secret = (
        os.environ.get("MLCFLUX_LOCATION_ANON_SECRET")
        or os.environ.get("MLCFLUX_SECRET_KEY")
        or "mlcflux-dev-location-secret"
    )

    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row

    rows = fetch_candidates(con)

    counters = Counter()
    by_postal_code = Counter()
    by_strategy = Counter()
    by_resolution = Counter()
    unresolved = Counter()

    center_cache: dict[tuple[str | None, str | None], dict[str, Any]] = {}

    for row in rows:
        counters["candidates"] += 1

        actor_ref = clean(row["actor_ref"])
        actor_family = clean(row["actor_family"]) or "?"
        postal_code = clean_postal_code(row["postal_code"])
        city = clean(row["city"])
        strategy = clean(row["location_strategy"]) or "unknown"

        by_strategy[strategy] += 1
        if postal_code:
            by_postal_code[postal_code] += 1

        if not actor_ref:
            counters["skipped_missing_actor_ref"] += 1
            continue

        cache_key = (postal_code, normalize_city(city))
        if cache_key not in center_cache:
            center_cache[cache_key] = resolve_center(
                postal_code=postal_code,
                city=city,
                secret=secret,
                stable_key=f"{mlc_id}|{postal_code}|{city}",
                sleep=sleep,
            )

        resolution = center_cache[cache_key]
        status = resolution.get("status", "unknown")
        by_resolution[status] += 1

        if status == "unresolved":
            counters["unresolved"] += 1
            unresolved[postal_code or "NO_POSTAL_CODE"] += 1
            continue

        rng = stable_rng(
            secret,
            f"{mlc_id}|{postal_code}|{city}|{actor_family}|{actor_ref}|CARTO_LOC002B",
        )
        lat, lon = jitter_around_lat_lon(
            float(resolution["latitude"]),
            float(resolution["longitude"]),
            rng,
        )

        counters["generated"] += 1

        if not dry_run:
            update_row(
                con,
                actor_ref=actor_ref,
                lat=round(lat, 7),
                lon=round(lon, 7),
                resolution_status=status,
            )

    if not dry_run:
        con.commit()

    table_counts = {
        "total": con.execute(
            "SELECT COUNT(*) FROM actor_map_locations"
        ).fetchone()[0],
        "cartographiable": con.execute(
            "SELECT COUNT(*) FROM actor_map_locations WHERE cartographiable = 1"
        ).fetchone()[0],
        "needs_postal_point_remaining": con.execute(
            """
            SELECT COUNT(*)
            FROM actor_map_locations
            WHERE precision_level = 'needs_postal_point'
              AND cartographiable = 0
            """
        ).fetchone()[0],
        "postal_synthetic": con.execute(
            """
            SELECT COUNT(*)
            FROM actor_map_locations
            WHERE precision_level = 'postal_synthetic'
            """
        ).fetchone()[0],
        "needs_geocoding": con.execute(
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
        "counters": dict(sorted(counters.items())),
        "by_postal_code": dict(sorted(by_postal_code.items())),
        "by_strategy": dict(sorted(by_strategy.items())),
        "by_resolution": dict(sorted(by_resolution.items())),
        "unresolved": dict(sorted(unresolved.items())),
        "table_counts": table_counts,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mlc", choices=MLC_IDS, action="append")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--sleep", type=float, default=DEFAULT_SLEEP)
    parser.add_argument("--json-out")
    args = parser.parse_args()

    load_dotenv()

    mlc_ids = args.mlc or list(MLC_IDS)
    dry_run = not args.write

    summaries = []
    for mlc_id in mlc_ids:
        print()
        print("========================================================================")
        print(f"sync_actor_map_postal_fallbacks — {mlc_id} — dry_run={dry_run}")
        print("========================================================================")
        summary = sync_mlc(mlc_id, dry_run=dry_run, sleep=args.sleep)
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
