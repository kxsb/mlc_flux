#!/usr/bin/env python3
"""
Synchronise une table pivot cartographique par instance MLC.

Principes :
- les professionnels peuvent garder des coordonnées précises ;
- les particuliers ne stockent jamais l'adresse brute ;
- les coordonnées de particuliers sont anonymisées par jitter déterministe ;
- les adresses exactes sans coordonnées sont seulement marquées comme "needs_geocoding" ;
- le géocodage externe sera branché dans un second temps.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import math
import os
import random
import re
import sqlite3
import sys
import time
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

DEFAULT_SLEEP = 0.02


def load_dotenv(path: Path = ROOT / ".env") -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def clean(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s or None


def qident(name: str) -> str:
    return '"' + str(name).replace('"', '""') + '"'


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def table_exists(cur: sqlite3.Cursor, table: str) -> bool:
    return cur.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone() is not None


def columns(cur: sqlite3.Cursor, table: str) -> list[str]:
    return [r[1] for r in cur.execute(f"PRAGMA table_info({qident(table)})").fetchall()]


def is_individual(row: dict[str, Any]) -> bool:
    ref = clean(row.get("actor_ref")) or ""
    fam = clean(row.get("actor_family")) or ""
    return (
        ref.startswith("U")
        or fam.upper() == "U"
        or fam.lower() in {"individual", "private", "particulier"}
    )


def is_professional(row: dict[str, Any]) -> bool:
    ref = clean(row.get("actor_ref")) or ""
    fam = clean(row.get("actor_family")) or ""
    return (
        ref.startswith("P")
        or fam.upper() == "P"
        or fam.lower() in {"professional", "pro", "professionnel"}
    )


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
    if not (-90 <= la <= 90 and -180 <= lo <= 180):
        return None
    return la, lo


def deterministic_jitter_square_km(
    lat: float,
    lon: float,
    stable_key: str,
    secret: str,
    square_m: float = 1000.0,
) -> tuple[float, float]:
    """
    Déplace un point de particulier dans une maille carrée approximative de 1 km.

    Le déplacement est déterministe : même acteur + même secret = même point.
    On ne stocke jamais la coordonnée originale.
    """
    digest = hmac.new(
        secret.encode("utf-8"),
        stable_key.encode("utf-8"),
        hashlib.sha256,
    ).digest()

    seed = int.from_bytes(digest[:16], "big")
    rng = random.Random(seed)

    dx_m = rng.uniform(-square_m / 2.0, square_m / 2.0)
    dy_m = rng.uniform(-square_m / 2.0, square_m / 2.0)

    meters_per_deg_lat = 111_320.0
    meters_per_deg_lon = max(1.0, 111_320.0 * math.cos(math.radians(lat)))

    return (
        lat + dy_m / meters_per_deg_lat,
        lon + dx_m / meters_per_deg_lon,
    )


def safe_status_from_exception(exc: Exception) -> str:
    msg = str(exc)
    match = re.search(r"\bHTTP\s+(\d{3})\b", msg)
    if match:
        return f"HTTP_{match.group(1)}"
    match = re.search(r"\bstatus[ =:]+(\d{3})\b", msg, flags=re.I)
    if match:
        return f"HTTP_{match.group(1)}"
    return type(exc).__name__


def create_schema(con: sqlite3.Connection) -> None:
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS actor_map_locations (
            actor_ref TEXT PRIMARY KEY,
            actor_family TEXT NOT NULL,
            actor_id TEXT,
            user_id TEXT,

            cartographiable INTEGER NOT NULL DEFAULT 0,
            location_strategy TEXT NOT NULL,
            precision_level TEXT NOT NULL,

            latitude REAL,
            longitude REAL,
            is_anonymized INTEGER NOT NULL DEFAULT 0,

            has_primary_address INTEGER NOT NULL DEFAULT 0,
            has_exact_address INTEGER NOT NULL DEFAULT 0,
            has_exact_coordinates INTEGER NOT NULL DEFAULT 0,
            needs_geocoding INTEGER NOT NULL DEFAULT 0,

            postal_code TEXT,
            city TEXT,

            source_provider TEXT,
            source_status TEXT,
            api_address_status TEXT,

            method_version TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )

    con.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_actor_map_locations_family
        ON actor_map_locations(actor_family)
        """
    )
    con.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_actor_map_locations_strategy
        ON actor_map_locations(location_strategy)
        """
    )
    con.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_actor_map_locations_cartographiable
        ON actor_map_locations(cartographiable)
        """
    )


def load_actor_rows(con: sqlite3.Connection) -> list[dict[str, Any]]:
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    if not table_exists(cur, "actor_territorial_enrichment"):
        return []

    wanted = [
        "actor_ref",
        "actor_family",
        "actor_id",
        "user_id",
        "postal_code",
        "raw_postal_code",
        "city",
        "latitude",
        "longitude",
        "source_provider",
        "source_status",
        "source_detail",
    ]
    existing = [c for c in wanted if c in columns(cur, "actor_territorial_enrichment")]

    rows = [
        dict(r)
        for r in cur.execute(
            f"""
            SELECT {", ".join(qident(c) for c in existing)}
            FROM actor_territorial_enrichment
            """
        ).fetchall()
    ]

    return [
        r for r in rows
        if clean(r.get("actor_ref")) and (is_individual(r) or is_professional(r))
    ]


def get_primary_address_safe(get_primary_address, user_ref: str, token: str) -> tuple[str, dict[str, Any] | None]:
    try:
        address = get_primary_address(user_ref, session_token=token)
        if address:
            return "OK_200", address
        return "NO_PRIMARY_ADDRESS_204", None
    except Exception as exc:
        return safe_status_from_exception(exc), None


def address_flags(address: dict[str, Any] | None) -> dict[str, bool]:
    if not address:
        return {
            "has_primary_address": False,
            "has_line1": False,
            "has_zip": False,
            "has_city": False,
            "has_coordinates": False,
        }

    lat_lon = valid_lat_lon(
        address.get("cyclos_latitude"),
        address.get("cyclos_longitude"),
    )

    return {
        "has_primary_address": True,
        "has_line1": bool(clean(address.get("cyclos_address_line1"))),
        "has_zip": bool(clean(address.get("cyclos_zip"))),
        "has_city": bool(clean(address.get("cyclos_city"))),
        "has_coordinates": lat_lon is not None,
    }


def build_location_record(
    *,
    mlc_id: str,
    row: dict[str, Any],
    address_status: str,
    address: dict[str, Any] | None,
    secret: str,
) -> dict[str, Any]:
    actor_ref = clean(row.get("actor_ref"))
    family = "U" if is_individual(row) else "P"

    local_postal_code = clean(row.get("postal_code")) or clean(row.get("raw_postal_code"))
    local_city = clean(row.get("city"))
    local_coords = valid_lat_lon(row.get("latitude"), row.get("longitude"))

    flags = address_flags(address)

    api_postal_code = clean(address.get("cyclos_zip")) if address else None
    api_city = clean(address.get("cyclos_city")) if address else None
    api_coords = (
        valid_lat_lon(address.get("cyclos_latitude"), address.get("cyclos_longitude"))
        if address
        else None
    )

    postal_code = api_postal_code or local_postal_code
    city = api_city or local_city

    stable_key = f"{mlc_id}:{actor_ref}:{clean(row.get('user_id')) or ''}"

    base = {
        "actor_ref": actor_ref,
        "actor_family": family,
        "actor_id": clean(row.get("actor_id")),
        "user_id": clean(row.get("user_id")),
        "cartographiable": 0,
        "location_strategy": "not_cartographiable",
        "precision_level": "none",
        "latitude": None,
        "longitude": None,
        "is_anonymized": 0,
        "has_primary_address": int(flags["has_primary_address"]),
        "has_exact_address": int(flags["has_line1"] and flags["has_zip"] and flags["has_city"]),
        "has_exact_coordinates": int(flags["has_coordinates"]),
        "needs_geocoding": 0,
        "postal_code": postal_code,
        "city": city,
        "source_provider": clean(row.get("source_provider")),
        "source_status": clean(row.get("source_status")),
        "api_address_status": address_status,
        "method_version": "CARTO_LOC001",
        "updated_at": now_iso(),
    }

    if family == "U":
        if api_coords:
            lat, lon = deterministic_jitter_square_km(
                api_coords[0],
                api_coords[1],
                stable_key=stable_key,
                secret=secret,
            )
            base.update(
                cartographiable=1,
                location_strategy="exact_coords_available_to_anonymize",
                precision_level="anonymized_1km_square",
                latitude=lat,
                longitude=lon,
                is_anonymized=1,
            )
            return base

        if flags["has_line1"] and flags["has_zip"] and flags["has_city"]:
            base.update(
                cartographiable=0,
                location_strategy="exact_address_to_geocode_then_anonymize",
                precision_level="needs_geocoding",
                needs_geocoding=1,
            )
            return base

        if flags["has_zip"] and flags["has_city"]:
            base.update(
                cartographiable=0,
                location_strategy="cyclos_zip_city_to_postal_synthetic",
                precision_level="needs_postal_point",
            )
            return base

        if local_coords:
            lat, lon = deterministic_jitter_square_km(
                local_coords[0],
                local_coords[1],
                stable_key=stable_key + ":local",
                secret=secret,
            )
            base.update(
                cartographiable=1,
                location_strategy="local_existing_coords_to_review",
                precision_level="anonymized_1km_square_from_local",
                latitude=lat,
                longitude=lon,
                is_anonymized=1,
            )
            return base

        if local_postal_code and local_city:
            base.update(
                cartographiable=0,
                location_strategy="local_zip_city_to_postal_synthetic",
                precision_level="needs_postal_point",
            )
            return base

        if local_postal_code:
            base.update(
                cartographiable=0,
                location_strategy="local_zip_only_to_postal_synthetic",
                precision_level="needs_postal_point",
            )
            return base

        return base

    # Professionnels : la position peut rester précise.
    if api_coords:
        base.update(
            cartographiable=1,
            location_strategy="professional_cyclos_exact_coords",
            precision_level="exact_or_declared_professional",
            latitude=api_coords[0],
            longitude=api_coords[1],
            is_anonymized=0,
        )
        return base

    if local_coords:
        base.update(
            cartographiable=1,
            location_strategy="professional_local_existing_coords",
            precision_level="exact_or_declared_professional",
            latitude=local_coords[0],
            longitude=local_coords[1],
            is_anonymized=0,
        )
        return base

    if flags["has_line1"] and flags["has_zip"] and flags["has_city"]:
        base.update(
            cartographiable=0,
            location_strategy="professional_address_to_geocode",
            precision_level="needs_geocoding",
            needs_geocoding=1,
        )
        return base

    if postal_code and city:
        base.update(
            cartographiable=0,
            location_strategy="professional_zip_city_to_postal_synthetic",
            precision_level="needs_postal_point",
        )
        return base

    if postal_code:
        base.update(
            cartographiable=0,
            location_strategy="professional_zip_only_to_postal_synthetic",
            precision_level="needs_postal_point",
        )
        return base

    return base


def upsert_record(con: sqlite3.Connection, record: dict[str, Any]) -> None:
    cols = list(record.keys())
    placeholders = ", ".join("?" for _ in cols)
    col_sql = ", ".join(qident(c) for c in cols)
    update_sql = ", ".join(
        f"{qident(c)} = excluded.{qident(c)}"
        for c in cols
        if c != "actor_ref"
    )

    con.execute(
        f"""
        INSERT INTO actor_map_locations ({col_sql})
        VALUES ({placeholders})
        ON CONFLICT(actor_ref) DO UPDATE SET {update_sql}
        """,
        [record[c] for c in cols],
    )


def sync_mlc(mlc_id: str, *, dry_run: bool, sleep: float) -> dict[str, Any]:
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
    create_schema(con)

    rows = load_actor_rows(con)

    counters = Counter()
    strategies = Counter()
    api_statuses = Counter()

    for row in rows:
        family = "U" if is_individual(row) else "P"
        counters[f"rows_{family}"] += 1

        user_ref = clean(row.get("user_id")) or clean(row.get("actor_ref"))
        if user_ref:
            status, address = get_primary_address_safe(get_primary_address, user_ref, token)
            time.sleep(sleep)
        else:
            status, address = "SKIP_NO_USER_REF", None

        api_statuses[status] += 1

        record = build_location_record(
            mlc_id=mlc_id,
            row=row,
            address_status=status,
            address=address,
            secret=secret,
        )

        strategies[record["location_strategy"]] += 1
        if record["cartographiable"]:
            counters[f"cartographiable_{family}"] += 1
        if record["needs_geocoding"]:
            counters[f"needs_geocoding_{family}"] += 1
        if record["is_anonymized"]:
            counters[f"anonymized_{family}"] += 1

        if not dry_run:
            upsert_record(con, record)

    if not dry_run:
        con.commit()

    summary = {
        "mlc_id": mlc_id,
        "db_path": str(db_path),
        "dry_run": dry_run,
        "rows_total": len(rows),
        "counters": dict(sorted(counters.items())),
        "api_statuses": dict(sorted(api_statuses.items())),
        "location_strategies": dict(sorted(strategies.items())),
    }

    if not dry_run:
        cur = con.cursor()
        summary["table_counts"] = {
            "actor_map_locations": cur.execute(
                "SELECT COUNT(*) FROM actor_map_locations"
            ).fetchone()[0],
            "cartographiable": cur.execute(
                "SELECT COUNT(*) FROM actor_map_locations WHERE cartographiable = 1"
            ).fetchone()[0],
            "needs_geocoding": cur.execute(
                "SELECT COUNT(*) FROM actor_map_locations WHERE needs_geocoding = 1"
            ).fetchone()[0],
            "anonymized": cur.execute(
                "SELECT COUNT(*) FROM actor_map_locations WHERE is_anonymized = 1"
            ).fetchone()[0],
        }

    con.close()
    return summary


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
        print(f"sync_actor_map_locations — {mlc_id} — dry_run={dry_run}")
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
