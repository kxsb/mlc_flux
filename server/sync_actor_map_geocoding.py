#!/usr/bin/env python3
"""
CARTO_LOC003A — Géocodage contrôlé des actor_map_locations en needs_geocoding.

Principes :
- on récupère l'adresse primaire Cyclos en mémoire uniquement ;
- aucune adresse brute n'est écrite dans la base ni dans les logs ;
- pour U : géocodage -> anonymisation 1 km² -> stockage possible uniquement du point anonymisé ;
- pour P : géocodage -> stockage possible du point professionnel exact/déclaré ;
- CARTO_LOC003A lance d'abord un échantillon en dry-run.
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
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
GEOCODING_SEARCH_URL = "https://data.geopf.fr/geocodage/search"

DB_BY_MLC = {
    "graine": ROOT / "server/data/instances/graine/mlcflux.db",
    "gonette": ROOT / "server/data/instances/gonette/mlcflux.db",
}
MLC_IDS = tuple(DB_BY_MLC.keys())

DEFAULT_LIMIT_U = 10
DEFAULT_LIMIT_P = 5
DEFAULT_SLEEP = 0.25
HTTP_TIMEOUT = 20
MIN_ACCEPTED_SCORE = 0.45


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


def stable_rng(secret: str, key: str) -> random.Random:
    digest = hmac.new(
        secret.encode("utf-8"),
        key.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return random.Random(int.from_bytes(digest[:16], "big"))


def deterministic_jitter_square_km(
    lat: float,
    lon: float,
    *,
    stable_key: str,
    secret: str,
    square_m: float = 1000.0,
) -> tuple[float, float]:
    rng = stable_rng(secret, stable_key)

    dx_m = rng.uniform(-square_m / 2.0, square_m / 2.0)
    dy_m = rng.uniform(-square_m / 2.0, square_m / 2.0)

    meters_per_deg_lat = 111_320.0
    meters_per_deg_lon = max(1.0, 111_320.0 * math.cos(math.radians(lat)))

    return (
        lat + dy_m / meters_per_deg_lat,
        lon + dx_m / meters_per_deg_lon,
    )


def address_to_query(address: dict[str, Any] | None) -> tuple[str | None, str | None, str | None]:
    if not address:
        return None, None, None

    line1 = clean(address.get("cyclos_address_line1"))
    zip_code = clean_postal_code(address.get("cyclos_zip"))
    city = clean(address.get("cyclos_city"))

    parts = [p for p in [line1, zip_code, city] if p]
    if not parts:
        return None, zip_code, city

    return " ".join(parts), zip_code, city


def score_bucket(score: float | None) -> str:
    if score is None:
        return "no_score"
    if score >= 0.8:
        return "score_0_80_plus"
    if score >= 0.6:
        return "score_0_60_0_79"
    if score >= MIN_ACCEPTED_SCORE:
        return "score_accepted_low"
    return "score_too_low"


def http_json(url: str) -> tuple[int | str, Any]:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "MLCFlux-CARTO_LOC003A/1.0",
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            body = resp.read()
            if not body:
                return resp.status, None
            return resp.status, json.loads(body.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            _ = exc.read()
        except Exception:
            pass
        return exc.code, None
    except Exception as exc:
        return type(exc).__name__, {"error_type": type(exc).__name__}


def parse_geocode_payload(payload: Any) -> dict[str, Any]:
    """
    Parse volontairement tolérant :
    - FeatureCollection type BAN / Addok ;
    - liste directe ;
    - objet avec features / results.
    """
    features = []

    if isinstance(payload, dict):
        if isinstance(payload.get("features"), list):
            features = payload["features"]
        elif isinstance(payload.get("results"), list):
            features = payload["results"]
        elif isinstance(payload.get("items"), list):
            features = payload["items"]
    elif isinstance(payload, list):
        features = payload

    if not features:
        return {
            "ok": False,
            "status": "no_result",
        }

    first = features[0]
    if not isinstance(first, dict):
        return {
            "ok": False,
            "status": "invalid_result_shape",
        }

    properties = first.get("properties") if isinstance(first.get("properties"), dict) else first
    geometry = first.get("geometry") if isinstance(first.get("geometry"), dict) else {}

    coords = geometry.get("coordinates")
    lat_lon = None

    if isinstance(coords, list) and len(coords) >= 2:
        # GeoJSON : [lon, lat]
        lat_lon = valid_lat_lon(coords[1], coords[0])

    # Tolérance autres formats.
    if lat_lon is None:
        lat_lon = valid_lat_lon(
            properties.get("lat") or properties.get("latitude"),
            properties.get("lon") or properties.get("lng") or properties.get("longitude"),
        )

    score = to_float(properties.get("score"))
    result_type = clean(properties.get("type")) or clean(properties.get("kind")) or "unknown"

    if lat_lon is None:
        return {
            "ok": False,
            "status": "no_coordinates_in_result",
            "score": score,
            "type": result_type,
        }

    if score is not None and score < MIN_ACCEPTED_SCORE:
        return {
            "ok": False,
            "status": "score_too_low",
            "score": score,
            "type": result_type,
            "latitude": lat_lon[0],
            "longitude": lat_lon[1],
        }

    return {
        "ok": True,
        "status": "ok",
        "score": score,
        "type": result_type,
        "latitude": lat_lon[0],
        "longitude": lat_lon[1],
    }


def geocode_address(query: str, zip_code: str | None = None, city: str | None = None) -> dict[str, Any]:
    params = {
        "q": query,
        "limit": "1",
    }

    if zip_code:
        params["postcode"] = zip_code
    if city:
        params["city"] = city

    url = GEOCODING_SEARCH_URL + "?" + urllib.parse.urlencode(params)
    status, payload = http_json(url)

    if status != 200:
        return {
            "ok": False,
            "status": f"http_{status}",
        }

    parsed = parse_geocode_payload(payload)
    parsed["http_status"] = status
    return parsed


def ensure_geocode_columns(con: sqlite3.Connection) -> None:
    existing = {
        r[1]
        for r in con.execute("PRAGMA table_info(actor_map_locations)").fetchall()
    }

    columns_to_add = {
        "geocode_provider": "TEXT",
        "geocode_status": "TEXT",
        "geocode_score": "REAL",
        "geocode_type": "TEXT",
        "geocoded_at": "TEXT",
    }

    for col, col_type in columns_to_add.items():
        if col not in existing:
            con.execute(
                f"ALTER TABLE actor_map_locations ADD COLUMN {qident(col)} {col_type}"
            )


def load_candidates(
    con: sqlite3.Connection,
    *,
    limit_u: int,
    limit_p: int,
) -> list[sqlite3.Row]:
    con.row_factory = sqlite3.Row
    rows: list[sqlite3.Row] = []

    for family, limit in [("U", limit_u), ("P", limit_p)]:
        if limit <= 0:
            continue

        rows.extend(
            con.execute(
                """
                SELECT
                    actor_ref,
                    actor_family,
                    user_id,
                    postal_code,
                    city,
                    location_strategy,
                    precision_level
                FROM actor_map_locations
                WHERE needs_geocoding = 1
                  AND precision_level = 'needs_geocoding'
                  AND actor_family = ?
                ORDER BY actor_ref
                LIMIT ?
                """,
                (family, limit),
            ).fetchall()
        )

    return rows


def get_primary_address_safe(get_primary_address, user_ref: str, token: str) -> tuple[str, dict[str, Any] | None]:
    try:
        address = get_primary_address(user_ref, session_token=token)
        if address:
            return "OK_200", address
        return "NO_PRIMARY_ADDRESS_204", None
    except Exception as exc:
        msg = str(exc)
        return f"{type(exc).__name__}:{msg[:80]}", None


def build_update_values(
    *,
    mlc_id: str,
    row: sqlite3.Row,
    geocode: dict[str, Any],
    secret: str,
) -> dict[str, Any] | None:
    if not geocode.get("ok"):
        return None

    lat_lon = valid_lat_lon(geocode.get("latitude"), geocode.get("longitude"))
    if not lat_lon:
        return None

    actor_ref = clean(row["actor_ref"])
    family = clean(row["actor_family"])

    if not actor_ref or family not in {"U", "P"}:
        return None

    if family == "U":
        lat, lon = deterministic_jitter_square_km(
            lat_lon[0],
            lat_lon[1],
            stable_key=f"{mlc_id}:{actor_ref}:geocoded:CARTO_LOC003",
            secret=secret,
        )
        return {
            "latitude": round(lat, 7),
            "longitude": round(lon, 7),
            "cartographiable": 1,
            "is_anonymized": 1,
            "precision_level": "anonymized_1km_square_from_geocoding",
            "location_strategy": "exact_address_geocoded_then_anonymized",
        }

    return {
        "latitude": round(lat_lon[0], 7),
        "longitude": round(lat_lon[1], 7),
        "cartographiable": 1,
        "is_anonymized": 0,
        "precision_level": "exact_or_declared_professional_from_geocoding",
        "location_strategy": "professional_address_geocoded",
    }


def update_location(
    con: sqlite3.Connection,
    *,
    actor_ref: str,
    update_values: dict[str, Any],
    geocode: dict[str, Any],
) -> None:
    con.execute(
        """
        UPDATE actor_map_locations
        SET
            cartographiable = ?,
            latitude = ?,
            longitude = ?,
            is_anonymized = ?,
            precision_level = ?,
            location_strategy = ?,
            needs_geocoding = 0,
            geocode_provider = 'geoplateforme',
            geocode_status = ?,
            geocode_score = ?,
            geocode_type = ?,
            geocoded_at = ?,
            method_version = 'CARTO_LOC003',
            updated_at = ?
        WHERE actor_ref = ?
        """,
        (
            update_values["cartographiable"],
            update_values["latitude"],
            update_values["longitude"],
            update_values["is_anonymized"],
            update_values["precision_level"],
            update_values["location_strategy"],
            geocode.get("status"),
            geocode.get("score"),
            geocode.get("type"),
            now_iso(),
            now_iso(),
            actor_ref,
        ),
    )


def sync_mlc(
    mlc_id: str,
    *,
    dry_run: bool,
    limit_u: int,
    limit_p: int,
    sleep: float,
) -> dict[str, Any]:
    db_path = DB_BY_MLC[mlc_id]
    if not db_path.exists():
        raise FileNotFoundError(db_path)

    os.environ["MLCFLUX_DEFAULT_MLC_ID"] = mlc_id

    from server.services.cyclos_client import create_session_token, get_primary_address

    token = create_session_token()

    secret = (
        os.environ.get("MLCFLUX_LOCATION_ANON_SECRET")
        or os.environ.get("MLCFLUX_SECRET_KEY")
        or "mlcflux-dev-location-secret"
    )

    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row

    if not dry_run:
        ensure_geocode_columns(con)

    rows = load_candidates(con, limit_u=limit_u, limit_p=limit_p)

    counters = Counter()
    by_family = Counter()
    by_address_status = Counter()
    by_geocode_status = Counter()
    by_score_bucket = Counter()
    by_result_type = Counter()
    would_update = Counter()

    for row in rows:
        actor_ref = clean(row["actor_ref"])
        family = clean(row["actor_family"])
        user_ref = clean(row["user_id"]) or actor_ref

        counters["candidates"] += 1
        by_family[family or "unknown"] += 1

        if not actor_ref or not user_ref:
            by_address_status["missing_user_ref"] += 1
            continue

        address_status, address = get_primary_address_safe(get_primary_address, user_ref, token)
        by_address_status[address_status] += 1

        query, zip_code, city = address_to_query(address)
        if not query:
            by_geocode_status["no_query_built"] += 1
            continue

        geocode = geocode_address(query, zip_code=zip_code, city=city)
        time.sleep(sleep)

        status = clean(geocode.get("status")) or "unknown"
        by_geocode_status[status] += 1
        by_score_bucket[score_bucket(to_float(geocode.get("score")))] += 1
        by_result_type[clean(geocode.get("type")) or "unknown"] += 1

        update_values = build_update_values(
            mlc_id=mlc_id,
            row=row,
            geocode=geocode,
            secret=secret,
        )

        if update_values:
            would_update[family or "unknown"] += 1
            counters["geocode_success"] += 1
            if not dry_run:
                update_location(
                    con,
                    actor_ref=actor_ref,
                    update_values=update_values,
                    geocode=geocode,
                )
        else:
            counters["geocode_not_usable"] += 1

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
        "anonymized": con.execute(
            "SELECT COUNT(*) FROM actor_map_locations WHERE is_anonymized = 1"
        ).fetchone()[0],
    }

    con.close()

    return {
        "mlc_id": mlc_id,
        "db_path": str(db_path),
        "dry_run": dry_run,
        "limits": {
            "U": limit_u,
            "P": limit_p,
        },
        "counters": dict(sorted(counters.items())),
        "by_family": dict(sorted(by_family.items())),
        "by_address_status": dict(sorted(by_address_status.items())),
        "by_geocode_status": dict(sorted(by_geocode_status.items())),
        "by_score_bucket": dict(sorted(by_score_bucket.items())),
        "by_result_type": dict(sorted(by_result_type.items())),
        "would_update_by_family": dict(sorted(would_update.items())),
        "table_counts": table_counts,
        "privacy_note": (
            "Aucune adresse brute n'est affichée ni exportée. "
            "Les adresses Cyclos sont utilisées en mémoire uniquement."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mlc", choices=MLC_IDS, action="append")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--limit-u", type=int, default=DEFAULT_LIMIT_U)
    parser.add_argument("--limit-p", type=int, default=DEFAULT_LIMIT_P)
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
        print(f"sync_actor_map_geocoding — {mlc_id} — dry_run={dry_run}")
        print("========================================================================")
        summary = sync_mlc(
            mlc_id,
            dry_run=dry_run,
            limit_u=args.limit_u,
            limit_p=args.limit_p,
            sleep=args.sleep,
        )
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
