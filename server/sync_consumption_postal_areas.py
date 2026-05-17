from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import requests


SERVER_DIR = Path(__file__).resolve().parent
DATA_DIR = SERVER_DIR / "data"
DB_PATH = DATA_DIR / "mlcflux.db"
OUT_PATH = DATA_DIR / "consumption_postal_areas.json"

GEO_API_COMMUNES_URL = "https://geo.api.gouv.fr/communes"

LYON_ARRONDISSEMENT_INSEE_BY_POSTAL_CODE = {
    "69001": "69381",
    "69002": "69382",
    "69003": "69383",
    "69004": "69384",
    "69005": "69385",
    "69006": "69386",
    "69007": "69387",
    "69008": "69388",
    "69009": "69389",
}

BASE_URL = "https://geo.api.gouv.fr/communes"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def clean_zip(value) -> str | None:
    raw = str(value or "").strip().replace(" ", "")
    return raw or None


def fetch_consumption_postal_codes() -> list[str]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    rows = conn.execute("""
        SELECT DISTINCT REPLACE(TRIM(i.zip), ' ', '') AS postal_code
        FROM transactions t
        JOIN odoo_individual_enrichment i
          ON i.pseudonym = t.from_label
         AND NULLIF(TRIM(i.zip), '') IS NOT NULL

        JOIN odoo_professional_enrichment p
          ON p.professional_ref = SUBSTR(
                t.to_label,
                1,
                INSTR(t.to_label || ' ', ' ') - 1
             )
         AND p.geo_match_status = 'confirmed'
         AND p.cyclos_latitude IS NOT NULL
         AND p.cyclos_longitude IS NOT NULL

        WHERE t.from_label LIKE 'U_%'
          AND t.to_label LIKE 'P%'

        ORDER BY postal_code
    """).fetchall()

    conn.close()

    return [
        code
        for row in rows
        if (code := clean_zip(row["postal_code"]))
    ]


def fetch_postal_area(postal_code: str) -> dict:
    cleaned_postal_code = clean_zip(postal_code)
    if not cleaned_postal_code:
        raise ValueError(f"Code postal vide ou invalide : {postal_code!r}")

    lyon_arrondissement_insee = LYON_ARRONDISSEMENT_INSEE_BY_POSTAL_CODE.get(
        cleaned_postal_code
    )

    if lyon_arrondissement_insee:
        # Les recherches génériques par codePostal retournent la commune Lyon
        # pour 69001→69009. On interroge donc directement l'arrondissement
        # municipal par code INSEE afin d'obtenir une géométrie distincte.
        url = f"{GEO_API_COMMUNES_URL}/{lyon_arrondissement_insee}"
        params = {
            "fields": "nom,code,codesPostaux,centre,contour",
            "format": "geojson",
            "geometry": "contour",
        }
    else:
        url = GEO_API_COMMUNES_URL
        params = {
            "codePostal": cleaned_postal_code,
            "fields": "nom,code,codesPostaux,centre,contour",
            "format": "geojson",
            "geometry": "contour",
        }

    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    payload = response.json()

    # /communes?codePostal=... renvoie normalement une FeatureCollection.
    # /communes/{code}?format=geojson peut renvoyer selon les formes de l'API
    # soit une Feature, soit une FeatureCollection. On normalise les deux.
    if isinstance(payload, dict) and payload.get("type") == "FeatureCollection":
        feature_collection = payload
    elif isinstance(payload, dict) and payload.get("type") == "Feature":
        feature_collection = {
            "type": "FeatureCollection",
            "features": [payload],
        }
    else:
        raise ValueError(
            f"Réponse GeoJSON inattendue pour {cleaned_postal_code}: "
            f"type={type(payload).__name__}, payload_type={payload.get('type') if isinstance(payload, dict) else None!r}"
        )

    features = feature_collection.get("features")
    if not isinstance(features, list):
        raise ValueError(
            f"Réponse inattendue pour {cleaned_postal_code}: features absent ou non-liste."
        )

    return {
        "postal_code": cleaned_postal_code,
        "feature_count": len(features),
        "feature_collection": feature_collection,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    postal_codes = fetch_consumption_postal_codes()

    print("========================================================================")
    print("SYNCHRO DES PÉRIMÈTRES POSTAUX — BASSINS DE CONSOMMATION U→P")
    print("========================================================================")
    print(f"Codes postaux à interroger : {len(postal_codes)}")
    print()

    areas = {}
    failures = []

    for index, postal_code in enumerate(postal_codes, start=1):
        try:
            area = fetch_postal_area(postal_code)
            areas[postal_code] = area
            print(
                f"[{index:03d}/{len(postal_codes):03d}] "
                f"{postal_code} : OK — {area['feature_count']} feature(s)"
            )
        except Exception as exc:
            failures.append({
                "postal_code": postal_code,
                "error": str(exc),
            })
            print(
                f"[{index:03d}/{len(postal_codes):03d}] "
                f"{postal_code} : ERREUR — {exc}"
            )

    payload = {
        "generated_at": utc_now_iso(),
        "source": "geo.api.gouv.fr/communes",
        "postal_code_count_requested": len(postal_codes),
        "postal_code_count_success": len(areas),
        "postal_code_count_failed": len(failures),
        "areas": areas,
        "failures": failures,
    }

    OUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print()
    print("========================================================================")
    print("RÉSUMÉ")
    print("========================================================================")
    print(f"Fichier produit : {OUT_PATH}")
    print(f"Succès          : {len(areas)}")
    print(f"Échecs          : {len(failures)}")

    if failures:
        print()
        print("Échecs détaillés :")
        for item in failures:
            print(f"- {item['postal_code']} : {item['error']}")


if __name__ == "__main__":
    main()
