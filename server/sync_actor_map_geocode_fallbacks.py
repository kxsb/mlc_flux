#!/usr/bin/env python3
"""
CARTO_LOC003D — Fallback postal pour les échecs résiduels de géocodage.

But :
- traiter les derniers needs_geocoding non exploitables ;
- ne manipuler aucune adresse brute ;
- utiliser uniquement postal_code / city déjà présents dans actor_map_locations ;
- convertir en postal_synthetic si possible ;
- garder les cas impossibles en needs_geocoding pour audit ultérieur.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from server.sync_actor_map_postal_points import (
    clean,
    clean_postal_code,
    load_postal_areas,
    synthetic_point_for_area,
)
from server.sync_actor_map_postal_fallbacks import (
    normalize_city,
    resolve_center,
    stable_rng,
    jitter_around_lat_lon,
)


ROOT = Path(__file__).resolve().parents[1]

DB_BY_MLC = {
    "graine": ROOT / "server/data/instances/graine/mlcflux.db",
    "gonette": ROOT / "server/data/instances/gonette/mlcflux.db",
}
MLC_IDS = tuple(DB_BY_MLC.keys())

DEFAULT_SLEEP = 0.15


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
            precision_level,
            needs_geocoding
        FROM actor_map_locations
        WHERE needs_geocoding = 1
          AND precision_level = 'needs_geocoding'
          AND cartographiable = 0
          AND NULLIF(TRIM(COALESCE(postal_code, '')), '') IS NOT NULL
        ORDER BY actor_family, postal_code, actor_ref
        """
    ).fetchall()


def update_row(
    con: sqlite3.Connection,
    *,
    actor_ref: str,
    lat: float,
    lon: float,
    source_status: str,
) -> None:
    con.execute(
        """
        UPDATE actor_map_locations
        SET
            cartographiable = 1,
            latitude = ?,
            longitude = ?,
            precision_level = 'postal_synthetic',
            location_strategy = 'geocode_failed_fallback_to_postal_synthetic',
            is_anonymized = CASE WHEN actor_family = 'U' THEN 1 ELSE is_anonymized END,
            needs_geocoding = 0,
            geocode_status = CASE
                WHEN geocode_status IS NULL OR geocode_status = ''
                THEN 'fallback_postal_after_geocode_failure'
                ELSE geocode_status
            END,
            source_status = ?,
            method_version = 'CARTO_LOC003D',
            updated_at = ?
        WHERE actor_ref = ?
        """,
        (
            lat,
            lon,
            source_status,
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

    postal_areas = load_postal_areas()

    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row

    rows = fetch_candidates(con)

    counters = Counter()
    by_family = Counter()
    by_postal_code = Counter()
    by_method = Counter()
    unresolved = Counter()
    fallback_cache: dict[tuple[str | None, str], dict[str, Any]] = {}

    for row in rows:
        counters["candidates"] += 1

        actor_ref = clean(row["actor_ref"])
        actor_family = clean(row["actor_family"]) or "?"
        postal_code = clean_postal_code(row["postal_code"])
        city = clean(row["city"])

        by_family[actor_family] += 1
        if postal_code:
            by_postal_code[postal_code] += 1

        if not actor_ref or not postal_code:
            counters["skipped_missing_actor_or_postal_code"] += 1
            unresolved[postal_code or "NO_POSTAL_CODE"] += 1
            continue

        point = None
        area = postal_areas.get(postal_code)

        if area:
            point = synthetic_point_for_area(
                area=area,
                postal_code=postal_code,
                actor_ref=actor_ref,
                mlc_id=mlc_id,
                actor_family=actor_family,
                secret=secret,
            )
            if point:
                by_method[point["placement"]] += 1

        if not point:
            cache_key = (postal_code, normalize_city(city))
            if cache_key not in fallback_cache:
                fallback_cache[cache_key] = resolve_center(
                    postal_code=postal_code,
                    city=city,
                    secret=secret,
                    stable_key=f"{mlc_id}|{postal_code}|{city}|CARTO_LOC003D",
                    sleep=sleep,
                )

            resolution = fallback_cache[cache_key]
            status = resolution.get("status", "unresolved")

            if status != "unresolved":
                rng = stable_rng(
                    secret,
                    f"{mlc_id}|{postal_code}|{city}|{actor_family}|{actor_ref}|CARTO_LOC003D",
                )
                lat, lon = jitter_around_lat_lon(
                    float(resolution["latitude"]),
                    float(resolution["longitude"]),
                    rng,
                )
                point = {
                    "latitude": round(lat, 7),
                    "longitude": round(lon, 7),
                    "placement": f"fallback_{status}",
                }
                by_method[point["placement"]] += 1

        if not point:
            counters["unresolved"] += 1
            unresolved[postal_code] += 1
            continue

        counters["generated"] += 1

        if not dry_run:
            update_row(
                con,
                actor_ref=actor_ref,
                lat=float(point["latitude"]),
                lon=float(point["longitude"]),
                source_status=f"geocode_fallback:{point['placement']}",
            )

    if not dry_run:
        con.commit()

    table_counts = {
        "total": con.execute("SELECT COUNT(*) FROM actor_map_locations").fetchone()[0],
        "cartographiable": con.execute(
            "SELECT COUNT(*) FROM actor_map_locations WHERE cartographiable = 1"
        ).fetchone()[0],
        "needs_geocoding": con.execute(
            "SELECT COUNT(*) FROM actor_map_locations WHERE needs_geocoding = 1"
        ).fetchone()[0],
        "needs_geocoding_U": con.execute(
            """
            SELECT COUNT(*)
            FROM actor_map_locations
            WHERE actor_family = 'U'
              AND needs_geocoding = 1
            """
        ).fetchone()[0],
        "needs_geocoding_P": con.execute(
            """
            SELECT COUNT(*)
            FROM actor_map_locations
            WHERE actor_family = 'P'
              AND needs_geocoding = 1
            """
        ).fetchone()[0],
        "postal_synthetic": con.execute(
            """
            SELECT COUNT(*)
            FROM actor_map_locations
            WHERE precision_level = 'postal_synthetic'
            """
        ).fetchone()[0],
        "anonymized": con.execute(
            "SELECT COUNT(*) FROM actor_map_locations WHERE is_anonymized = 1"
        ).fetchone()[0],
    }

    con.close()

    return {
        "mlc_id": mlc_id,
        "db_path": str(db_path),
        "dry_run": dry_run,
        "counters": dict(sorted(counters.items())),
        "by_family": dict(sorted(by_family.items())),
        "by_postal_code": dict(sorted(by_postal_code.items())),
        "by_method": dict(sorted(by_method.items())),
        "unresolved": dict(sorted(unresolved.items())),
        "table_counts": table_counts,
        "privacy_note": "Aucune adresse brute n'est utilisée ni stockée ; fallback uniquement CP / ville.",
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
        print(f"sync_actor_map_geocode_fallbacks — {mlc_id} — dry_run={dry_run}")
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
