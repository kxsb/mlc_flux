from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from server import database
from server.mlc_context import (
    get_default_mlc_id,
    get_mlc_instance_dir,
    normalize_mlc_id,
)
from server.mlc_profiles import get_mlc_profile


REFERENCE_FILENAME = "consumption_postal_areas.json"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_dump(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _clean_text(value: Any) -> str | None:
    value = str(value or "").strip()
    return value or None


def _detect_country_code(payload: dict[str, Any]) -> str | None:
    """
    Détermine le pays du référentiel sans imposer FR au modèle interne.

    Le référentiel historique actuellement disponible provient de
    geo.api.gouv.fr et est donc explicitement français.
    """
    scope = payload.get("territorial_scope") or {}
    source = payload.get("source") or {}

    explicit = (
        payload.get("country_code")
        or scope.get("country_code")
    )

    if explicit:
        return str(explicit).strip().upper()

    provider = str(source.get("provider") or "").lower()

    if "geo.api.gouv.fr" in provider:
        return "FR"

    return None


def _build_area_id(
    country_code: str | None,
    area_type: str,
    area_code: str,
) -> str:
    namespace = country_code or "XX"

    if area_type == "postal_area":
        type_token = "postal"
    elif area_type == "mlc_territory":
        type_token = "mlc"
    else:
        type_token = area_type

    return f"{namespace}:{type_token}:{area_code}"


def _load_reference(path: Path) -> dict[str, Any]:
    payload = json.loads(
        path.read_text(encoding="utf-8")
    )

    if not isinstance(payload, dict):
        raise ValueError(
            "Le référentiel géographique doit être un objet JSON."
        )

    areas = payload.get("areas")

    if not isinstance(areas, dict):
        raise ValueError(
            "Le référentiel ne contient pas de dictionnaire 'areas'."
        )

    return payload


def sync_geographic_areas_from_reference(
    mlc_id: str | None = None,
    *,
    reference_path: str | Path | None = None,
) -> dict[str, Any]:
    """
    Importe un référentiel territorial d'instance vers
    geographic_areas.

    L'import est idempotent :
    - identifiants déterministes ;
    - UPSERT ;
    - aucune duplication au second passage.

    Cette fonction ne touche pas actor_geography.
    """
    normalized_mlc_id = normalize_mlc_id(
        mlc_id or get_default_mlc_id()
    )

    profile = get_mlc_profile(normalized_mlc_id)

    if reference_path is None:
        path = (
            get_mlc_instance_dir(normalized_mlc_id)
            / REFERENCE_FILENAME
        )
    else:
        path = Path(reference_path)

    if not path.exists():
        raise FileNotFoundError(
            f"Référentiel géographique introuvable : {path}"
        )

    payload = _load_reference(path)

    payload_mlc_id = _clean_text(payload.get("mlc_id"))

    if (
        payload_mlc_id
        and payload_mlc_id != normalized_mlc_id
    ):
        raise ValueError(
            "Le référentiel appartient à une autre MLC : "
            f"{payload_mlc_id!r} != {normalized_mlc_id!r}"
        )

    country_code = _detect_country_code(payload)

    generated_at = (
        _clean_text(payload.get("generated_at"))
        or _utc_now_iso()
    )

    territorial_scope = (
        payload.get("territorial_scope")
        if isinstance(
            payload.get("territorial_scope"),
            dict,
        )
        else {}
    )

    reference_source = (
        payload.get("source")
        if isinstance(payload.get("source"), dict)
        else {}
    )

    areas = payload["areas"]

    declared_count = payload.get("area_count")

    if (
        declared_count is not None
        and int(declared_count) != len(areas)
    ):
        raise ValueError(
            "area_count incohérent : "
            f"{declared_count} déclaré, {len(areas)} trouvé."
        )

    mlc_territory_id = _build_area_id(
        country_code,
        "mlc_territory",
        normalized_mlc_id,
    )

    conn = database.get_connection()

    try:
        cur = conn.cursor()

        # ---------------------------------------------------------
        # Territoire fonctionnel général de la MLC
        # ---------------------------------------------------------

        territory_name = (
            _clean_text(territorial_scope.get("label"))
            or profile.name
        )

        territory_metadata = {
            "mlc_id": normalized_mlc_id,
            "mlc_name": profile.name,
            "mlc_short_name": profile.short_name,
            "territorial_scope": territorial_scope,
            "reference_schema_version": payload.get(
                "schema_version"
            ),
            "reference_source": reference_source,
        }

        cur.execute(
            """
            INSERT INTO geographic_areas (
                area_id,
                area_type,
                country_code,
                area_code,
                name,
                short_name,
                parent_area_id,
                latitude,
                longitude,
                geometry_kind,
                geometry_geojson,
                source_provider,
                source_record_id,
                source_updated_at,
                metadata_json,
                fetched_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)

            ON CONFLICT(area_id) DO UPDATE SET
                area_type = excluded.area_type,
                country_code = excluded.country_code,
                area_code = excluded.area_code,
                name = excluded.name,
                short_name = excluded.short_name,
                parent_area_id = excluded.parent_area_id,
                latitude = excluded.latitude,
                longitude = excluded.longitude,
                geometry_kind = excluded.geometry_kind,
                geometry_geojson = excluded.geometry_geojson,
                source_provider = excluded.source_provider,
                source_record_id = excluded.source_record_id,
                source_updated_at = excluded.source_updated_at,
                metadata_json = excluded.metadata_json,
                fetched_at = excluded.fetched_at,
                updated_at = excluded.updated_at
            """,
            (
                mlc_territory_id,
                "mlc_territory",
                country_code,
                normalized_mlc_id,
                territory_name,
                profile.short_name,
                None,
                None,
                None,
                None,
                None,
                "mlcflux.mlc_profile",
                normalized_mlc_id,
                None,
                _json_dump(territory_metadata),
                generated_at,
                generated_at,
            ),
        )

        processed_postal_areas = 0

        # ---------------------------------------------------------
        # Zones postales
        # ---------------------------------------------------------

        for root_code, area in sorted(areas.items()):
            if not isinstance(area, dict):
                raise ValueError(
                    f"Aire {root_code!r} invalide."
                )

            postal_code = (
                _clean_text(area.get("postal_code"))
                or _clean_text(root_code)
            )

            if not postal_code:
                raise ValueError(
                    "Zone postale sans code."
                )

            if (
                _clean_text(root_code)
                and str(root_code).strip() != postal_code
            ):
                raise ValueError(
                    "Code postal incohérent : "
                    f"clé={root_code!r}, "
                    f"postal_code={postal_code!r}"
                )

            latitude = area.get("latitude")
            longitude = area.get("longitude")

            feature_collection = area.get(
                "feature_collection"
            )

            if feature_collection is not None:
                if not isinstance(
                    feature_collection,
                    dict,
                ):
                    raise ValueError(
                        f"GeoJSON invalide pour {postal_code}."
                    )

                geometry_geojson = _json_dump(
                    feature_collection
                )
            else:
                geometry_geojson = None

            geometry_kind = _clean_text(
                area.get("geometry_kind")
            )

            source_provider = (
                _clean_text(area.get("source"))
                or _clean_text(
                    reference_source.get("provider")
                )
                or "unknown"
            )

            area_id = _build_area_id(
                country_code,
                "postal_area",
                postal_code,
            )

            metadata = {
                "city_label": area.get("city_label"),
                "feature_count": area.get("feature_count"),
                "reference_schema_version": payload.get(
                    "schema_version"
                ),
                "geometry_semantics": (
                    "commune_contours_grouped_by_postal_code"
                    if geometry_kind
                    == "commune_contours_by_postal_code"
                    else geometry_kind
                ),
                "reference_note": reference_source.get(
                    "note"
                ),
            }

            cur.execute(
                """
                INSERT INTO geographic_areas (
                    area_id,
                    area_type,
                    country_code,
                    area_code,
                    name,
                    short_name,
                    parent_area_id,
                    latitude,
                    longitude,
                    geometry_kind,
                    geometry_geojson,
                    source_provider,
                    source_record_id,
                    source_updated_at,
                    metadata_json,
                    fetched_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)

                ON CONFLICT(area_id) DO UPDATE SET
                    area_type = excluded.area_type,
                    country_code = excluded.country_code,
                    area_code = excluded.area_code,
                    name = excluded.name,
                    short_name = excluded.short_name,
                    parent_area_id = excluded.parent_area_id,
                    latitude = excluded.latitude,
                    longitude = excluded.longitude,
                    geometry_kind = excluded.geometry_kind,
                    geometry_geojson = excluded.geometry_geojson,
                    source_provider = excluded.source_provider,
                    source_record_id = excluded.source_record_id,
                    source_updated_at = excluded.source_updated_at,
                    metadata_json = excluded.metadata_json,
                    fetched_at = excluded.fetched_at,
                    updated_at = excluded.updated_at
                """,
                (
                    area_id,
                    "postal_area",
                    country_code,
                    postal_code,
                    _clean_text(area.get("city_label"))
                    or postal_code,
                    postal_code,

                    # Important :
                    # le territoire MLC n'est pas un parent
                    # administratif du code postal.
                    None,

                    latitude,
                    longitude,
                    geometry_kind,
                    geometry_geojson,
                    source_provider,
                    postal_code,
                    generated_at,
                    _json_dump(metadata),
                    generated_at,
                    generated_at,
                ),
            )

            processed_postal_areas += 1

        conn.commit()

        return {
            "mlc_id": normalized_mlc_id,
            "country_code": country_code,
            "reference_path": str(path),
            "mlc_territory_area_id": mlc_territory_id,
            "postal_area_count": processed_postal_areas,
            "total_area_count": (
                processed_postal_areas + 1
            ),
        }

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()
