#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import os
import sqlite3
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


APP_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = APP_DIR / "server" / "data"
INSTANCES_DIR = DATA_DIR / "instances"
PROFILES_DIR = DATA_DIR / "mlc_profiles"


def _load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _clean_postal_code(value: Any) -> str | None:
    cleaned = "".join(char for char in str(value or "").strip() if char.isdigit())
    return cleaned or None


def _safe_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    return number if math.isfinite(number) else None


def _instance_db_path(mlc_id: str) -> Path:
    return INSTANCES_DIR / mlc_id / "mlcflux.db"


def _instance_output_path(mlc_id: str) -> Path:
    return INSTANCES_DIR / mlc_id / "consumption_postal_areas.json"


def _load_profile(mlc_id: str) -> dict[str, Any]:
    return _load_json(PROFILES_DIR / f"{mlc_id}.json", {})


def _scope_prefixes(profile: dict[str, Any]) -> list[str]:
    scope = profile.get("territorial_scope") or {}
    prefixes = scope.get("postal_code_prefixes") or []

    return [
        str(prefix).strip()
        for prefix in prefixes
        if str(prefix).strip()
    ]


def _collect_postal_codes(mlc_id: str, prefixes: list[str]) -> list[str]:
    db_path = _instance_db_path(mlc_id)

    if not db_path.exists():
        raise FileNotFoundError(f"Base SQLite introuvable : {db_path}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    try:
        rows = conn.execute(
            """
            SELECT DISTINCT TRIM(postal_code) AS postal_code
            FROM actor_map_locations
            WHERE cartographiable = 1
              AND NULLIF(TRIM(postal_code), '') IS NOT NULL
              AND latitude IS NOT NULL
              AND longitude IS NOT NULL
            ORDER BY TRIM(postal_code)
            """
        ).fetchall()
    finally:
        conn.close()

    postal_codes = []
    for row in rows:
        postal_code = _clean_postal_code(row["postal_code"])
        if not postal_code:
            continue

        if prefixes and not any(postal_code.startswith(prefix) for prefix in prefixes):
            continue

        postal_codes.append(postal_code)

    return sorted(set(postal_codes))


def _fetch_geo_api_postal_code(postal_code: str, timeout: int = 20) -> dict[str, Any]:
    params = urllib.parse.urlencode({
        "codePostal": postal_code,
        "fields": "code,nom,centre,contour,codesPostaux",
        "format": "geojson",
        "geometry": "contour",
    })

    url = f"https://geo.api.gouv.fr/communes?{params}"

    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _feature_points(feature_collection: dict[str, Any]) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []

    def push_coordinates(coords: Any) -> None:
        if not isinstance(coords, list):
            return

        if (
            len(coords) >= 2
            and _safe_float(coords[0]) is not None
            and _safe_float(coords[1]) is not None
        ):
            points.append((float(coords[0]), float(coords[1])))
            return

        for item in coords:
            push_coordinates(item)

    for feature in feature_collection.get("features") or []:
        geometry = feature.get("geometry") or {}
        push_coordinates(geometry.get("coordinates"))

    return points


def _feature_centers(feature_collection: dict[str, Any]) -> list[tuple[float, float]]:
    centers: list[tuple[float, float]] = []

    for feature in feature_collection.get("features") or []:
        properties = feature.get("properties") or {}
        centre = properties.get("centre") or {}
        coordinates = centre.get("coordinates") or []

        if len(coordinates) < 2:
            continue

        lon = _safe_float(coordinates[0])
        lat = _safe_float(coordinates[1])

        if lon is not None and lat is not None:
            centers.append((lon, lat))

    return centers


def _feature_collection_center(feature_collection: dict[str, Any]) -> tuple[float | None, float | None]:
    centers = _feature_centers(feature_collection)

    if not centers:
        centers = _feature_points(feature_collection)

    if not centers:
        return None, None

    lon = sum(point[0] for point in centers) / len(centers)
    lat = sum(point[1] for point in centers) / len(centers)

    return lon, lat


def _city_label(feature_collection: dict[str, Any]) -> str | None:
    names = []

    for feature in feature_collection.get("features") or []:
        name = str((feature.get("properties") or {}).get("nom") or "").strip()
        if name and name not in names:
            names.append(name)

    if not names:
        return None

    if len(names) == 1:
        return names[0]

    return ", ".join(names[:4]) + ("…" if len(names) > 4 else "")


def _normalize_feature_collection(payload: dict[str, Any]) -> dict[str, Any]:
    features = payload.get("features") if isinstance(payload, dict) else []

    normalized_features = []

    for feature in features or []:
        geometry = feature.get("geometry")
        properties = feature.get("properties") or {}

        if not geometry:
            continue

        normalized_features.append({
            "type": "Feature",
            "properties": {
                "code": properties.get("code"),
                "nom": properties.get("nom"),
                "codesPostaux": properties.get("codesPostaux"),
                "centre": properties.get("centre"),
                "source": "geo.api.gouv.fr/communes",
            },
            "geometry": geometry,
        })

    return {
        "type": "FeatureCollection",
        "features": normalized_features,
    }


def build_postal_areas_for_instance(
    mlc_id: str,
    *,
    sleep_seconds: float = 0.12,
    limit: int | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    profile = _load_profile(mlc_id)
    prefixes = _scope_prefixes(profile)
    postal_codes = _collect_postal_codes(mlc_id, prefixes)

    if limit is not None:
        postal_codes = postal_codes[:limit]

    areas: dict[str, Any] = {}
    failures: list[dict[str, Any]] = []

    for index, postal_code in enumerate(postal_codes, start=1):
        print(f"[{mlc_id}] {index}/{len(postal_codes)} CP {postal_code}", flush=True)

        try:
            payload = _fetch_geo_api_postal_code(postal_code)
            feature_collection = _normalize_feature_collection(payload)

            if not feature_collection["features"]:
                failures.append({
                    "postal_code": postal_code,
                    "error": "no_feature",
                })
                continue

            longitude, latitude = _feature_collection_center(feature_collection)

            if longitude is None or latitude is None:
                failures.append({
                    "postal_code": postal_code,
                    "error": "no_center",
                })
                continue

            areas[postal_code] = {
                "postal_code": postal_code,
                "city_label": _city_label(feature_collection),
                "longitude": longitude,
                "latitude": latitude,
                "feature_collection": feature_collection,
                "source": "geo.api.gouv.fr/communes",
                "geometry_kind": "commune_contours_by_postal_code",
                "feature_count": len(feature_collection["features"]),
            }

        except Exception as exc:
            failures.append({
                "postal_code": postal_code,
                "error": f"{type(exc).__name__}: {exc}",
            })

        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    output = {
        "schema_version": "mlcflux.payment_basin_postal_areas.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mlc_id": mlc_id,
        "territorial_scope": profile.get("territorial_scope"),
        "source": {
            "provider": "geo.api.gouv.fr",
            "endpoint": "/communes",
            "geometry": "contour",
            "note": (
                "Les contours sont des contours communaux rattachés aux codes postaux. "
                "Ils ne constituent pas toujours un découpage postal intra-communal strict."
            ),
        },
        "postal_code_count_requested": len(postal_codes),
        "area_count": len(areas),
        "failure_count": len(failures),
        "failures": failures,
        "areas": areas,
    }

    if not dry_run:
        output_path = _instance_output_path(mlc_id)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(output, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        print(f"[{mlc_id}] écrit : {output_path}", flush=True)

    return output


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Génère les géométries de fonds postaux pour les cartes bassin de paiement."
    )
    parser.add_argument(
        "--mlc",
        action="append",
        choices=["graine", "gonette"],
        help="Instance MLC à traiter. Peut être répété. Par défaut : graine + gonette.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Télécharge et construit le JSON sans écrire le fichier.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limite le nombre de codes postaux traités, pour test.",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.12,
        help="Pause entre deux appels à geo.api.gouv.fr.",
    )

    args = parser.parse_args()
    mlc_ids = args.mlc or ["graine", "gonette"]

    summaries = []

    for mlc_id in mlc_ids:
        output = build_postal_areas_for_instance(
            mlc_id,
            sleep_seconds=args.sleep,
            limit=args.limit,
            dry_run=args.dry_run,
        )
        summaries.append({
            "mlc_id": mlc_id,
            "requested": output["postal_code_count_requested"],
            "areas": output["area_count"],
            "failures": output["failure_count"],
            "output_path": str(_instance_output_path(mlc_id)),
            "dry_run": args.dry_run,
        })

    print(json.dumps(summaries, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
