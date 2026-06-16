from __future__ import annotations

from flask import Blueprint, jsonify, request

from server.mlc_context import get_active_mlc_id
from server.mlc_profiles import get_mlc_profile
from server.services.user_to_professional_map_analytics import (
    get_user_to_professional_map_payload,
)


user_to_professional_map_bp = Blueprint(
    "user_to_professional_map",
    __name__,
)


def _int_arg(name: str, default: int) -> int:
    raw = request.args.get(name)
    if raw in (None, ""):
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"Paramètre {name} invalide.") from exc


def _float_arg(name: str, default: float) -> float:
    raw = request.args.get(name)
    if raw in (None, ""):
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"Paramètre {name} invalide.") from exc


def _resolve_requested_mlc_id(value: str | None) -> str:
    if value in (None, ""):
        return get_active_mlc_id()
    return get_mlc_profile(str(value).strip()).id



# CARTO_CLUSTER_MAIN_OPT001_COMPACT_GEOMETRY
def _bool_arg(name: str, default: bool = False) -> bool:
    raw = request.args.get(name)
    if raw in (None, ""):
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


# CARTO_CLUSTER_MAIN_OPT001_COMPACT_GEOMETRY

# CARTO_CLUSTER_MAIN_OPT004A_SAFE_LEAN_INITIAL_PAYLOAD
# CARTO_CLUSTER_MAIN_OPT004A2_METADATA_NORMALIZE
def _strip_user_to_professional_map_heavy_fields(
    payload,
    *,
    include_route_timeline=True,
    include_extra_flow_families=True,
):
    """
    Allège le payload initial de la carte U→P.

    Contrat :
    - par défaut, rien n'est retiré ;
    - si include_route_timeline=False, routes[].timeline est supprimé ;
    - si include_extra_flow_families=False, extra_flow_families.families devient [] ;
    - les métadonnées de mode sont toujours normalisées.
    """
    if not isinstance(payload, dict):
        return payload

    omitted = {
        "route_timeline": 0,
        "extra_flow_families": 0,
    }

    if not include_route_timeline:
        for route in payload.get("routes") or []:
            if isinstance(route, dict) and "timeline" in route:
                route.pop("timeline", None)
                omitted["route_timeline"] += 1

    if not include_extra_flow_families:
        extra = payload.get("extra_flow_families")

        if not isinstance(extra, dict):
            extra = {}
            payload["extra_flow_families"] = extra

        families = extra.get("families")
        if isinstance(families, list):
            omitted["extra_flow_families"] = len(families)

        extra["families"] = []
        extra["families_omitted"] = omitted["extra_flow_families"]
        extra["payload_mode"] = "deferred"
        extra["include_extra_flow_families"] = False

    mode = "lean" if (
        not include_route_timeline
        or not include_extra_flow_families
    ) else "full"

    metadata = payload.setdefault("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
        payload["metadata"] = metadata

    metadata["initial_payload_mode"] = mode
    metadata["omitted_heavy_fields"] = omitted
    metadata["include_route_timeline"] = bool(include_route_timeline)
    metadata["include_extra_flow_families"] = bool(include_extra_flow_families)

    payload["initial_payload_mode"] = mode
    payload["omitted_heavy_fields"] = omitted

    return payload



# CARTO_CLUSTER_MAIN_OPT005A_REPRESENTATIVE_SOURCE_POINTS
def _representative_source_point(point):
    if not isinstance(point, dict):
        return None

    coordinates = point.get("coordinates")
    lon = None
    lat = None

    if isinstance(coordinates, (list, tuple)) and len(coordinates) >= 2:
        lon = coordinates[0]
        lat = coordinates[1]
    else:
        lon = point.get("longitude")
        lat = point.get("latitude")

    try:
        lon = float(lon)
        lat = float(lat)
    except (TypeError, ValueError):
        return None

    compact = {
        "coordinates": [lon, lat],
        "longitude": lon,
        "latitude": lat,
    }

    for key in (
        "point_status",
        "source_point_status",
        "location_source",
        "precision_level",
        "is_anonymized",
    ):
        if key in point:
            compact[key] = point.get(key)

    return compact


# CARTO_CLUSTER_MAIN_OPT005A_REPRESENTATIVE_SOURCE_POINTS

# CARTO_CLUSTER_MAIN_OPT006A_COMPACT_ROUTE_ENDPOINTS
_ROUTE_SOURCE_COMPACT_KEYS = (
    "kind",
    "id",
    "key",
    "label",
    "name",
    "postal_code",
    "city",
    "latitude",
    "longitude",
    "coordinates",
    "location_source",
    "precision_level",
    "location_strategy",
    "is_anonymized",
    "mapped_user_count",
    "anonymized_user_count",
)

_ROUTE_DESTINATION_COMPACT_KEYS = (
    "kind",
    "id",
    "key",
    "label",
    "name",
    "display_label",
    "professional_label",
    "professional_ref",
    "professionalRef",
    "postal_code",
    "city",
    "latitude",
    "longitude",
    "coordinates",
    "location_source",
    "precision_level",
    "location_strategy",
    "is_anonymized",
    "industry_name",
)


# CARTO_CLUSTER_MAIN_OPT006A_COMPACT_ROUTE_ENDPOINTS
def _compact_route_endpoint_object(endpoint, keys):
    if not isinstance(endpoint, dict):
        return endpoint

    compact = {
        key: endpoint.get(key)
        for key in keys
        if key in endpoint
    }

    return compact


# CARTO_CLUSTER_MAIN_OPT006A_COMPACT_ROUTE_ENDPOINTS
def _compact_user_to_professional_map_route_endpoints(payload, *, route_endpoint_mode="full"):
    """
    Allège route.source / route.destination.

    Mode par défaut : full, inchangé.
    Mode compact : garde coordonnées, libellés, identifiants et métadonnées simples,
    mais retire les listes détaillées répétées par route.
    """
    if not isinstance(payload, dict):
        return payload

    mode = str(route_endpoint_mode or "full").strip().lower()

    if mode not in ("compact", "lean", "minimal"):
        return payload

    compacted_routes = 0
    removed_keys = {}

    for route in payload.get("routes") or []:
        if not isinstance(route, dict):
            continue

        touched = False

        source = route.get("source")
        if isinstance(source, dict):
            before_keys = set(source.keys())
            route["source"] = _compact_route_endpoint_object(
                source,
                _ROUTE_SOURCE_COMPACT_KEYS,
            )
            after_keys = set(route["source"].keys())
            for key in sorted(before_keys - after_keys):
                removed_keys[f"source.{key}"] = removed_keys.get(f"source.{key}", 0) + 1
            touched = True

        destination = route.get("destination")
        if isinstance(destination, dict):
            before_keys = set(destination.keys())
            route["destination"] = _compact_route_endpoint_object(
                destination,
                _ROUTE_DESTINATION_COMPACT_KEYS,
            )
            after_keys = set(route["destination"].keys())
            for key in sorted(before_keys - after_keys):
                removed_keys[f"destination.{key}"] = removed_keys.get(f"destination.{key}", 0) + 1
            touched = True

        if touched:
            compacted_routes += 1
            route["route_endpoint_payload_mode"] = "compact"

    metadata = payload.setdefault("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
        payload["metadata"] = metadata

    omitted = metadata.setdefault("omitted_heavy_fields", {})
    if isinstance(omitted, dict):
        omitted["route.source_destination.deep_fields"] = sum(removed_keys.values())

    metadata["route_endpoint_payload_mode"] = "compact"
    metadata["route_endpoint_compacted_routes"] = compacted_routes
    metadata["route_endpoint_removed_keys"] = removed_keys

    payload["route_endpoint_payload_mode"] = "compact"

    return payload


def _compact_user_to_professional_map_source_points(payload, *, source_points_mode="full"):
    """
    Allège route.source_points.

    Mode par défaut : full, inchangé.
    Mode representative : conserve un seul point-source par route.
    """
    if not isinstance(payload, dict):
        return payload

    mode = str(source_points_mode or "full").strip().lower()

    if mode not in ("representative", "single", "compact"):
        return payload

    omitted_total = 0
    compacted_routes = 0

    for route in payload.get("routes") or []:
        if not isinstance(route, dict):
            continue

        points = route.get("source_points")

        if not isinstance(points, list) or not points:
            continue

        representative = None

        for point in points:
            representative = _representative_source_point(point)
            if representative:
                break

        if not representative:
            continue

        original_count = len(points)
        omitted = max(0, original_count - 1)

        route["source_points"] = [representative]
        route["source_points_original_count"] = original_count
        route["source_points_omitted_count"] = omitted
        route["source_points_payload_mode"] = "representative"

        previous_mode = route.get("source_points_mode") or "source_points"
        route["source_points_mode"] = f"{previous_mode}_representative"

        omitted_total += omitted
        compacted_routes += 1

    metadata = payload.setdefault("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
        payload["metadata"] = metadata

    omitted = metadata.setdefault("omitted_heavy_fields", {})
    if isinstance(omitted, dict):
        omitted["route.source_points.extra"] = omitted_total

    metadata["source_points_payload_mode"] = "representative"
    metadata["source_points_compacted_routes"] = compacted_routes
    metadata["source_points_omitted_count"] = omitted_total

    payload["source_points_payload_mode"] = "representative"

    return payload


def _compact_user_to_professional_map_payload(payload):
    """
    Allège le payload cartographique principal sans modifier le contrat utile
    au renderer MapLibre/deck.gl : routes, sources, destinations, timeline,
    coverage, privacy et compteurs geometry restent disponibles.
    """
    if not isinstance(payload, dict):
        return payload

    geometry = payload.get("geometry")
    if not isinstance(geometry, dict):
        return payload

    omitted = {}

    for key in (
        "visible_source_area_geojson",
        "source_postal_areas",
    ):
        value = geometry.pop(key, None)
        if isinstance(value, dict):
            omitted[key] = len(value)
        elif isinstance(value, list):
            omitted[key] = len(value)
        elif value is not None:
            omitted[key] = True

    if omitted:
        geometry["geometry_payload_mode"] = "compact"
        geometry["omitted_geometry_keys"] = omitted
        payload.setdefault("metadata", {})["geometry_payload_mode"] = "compact"

    return payload



# CARTO_CLUSTER_MAIN_OPT003A_OPTIONAL_HEAVY_FIELDS
def _strip_user_to_professional_map_heavy_fields(
    payload,
    *,
    include_route_timeline: bool = True,
    include_extra_flow_families: bool = True,
):
    """
    Rend optionnels les champs très lourds qui ne sont pas nécessaires
    au premier affichage statique de la carte principale.

    - route.timeline : utile au player / mode dynamique ;
    - extra_flow_families.families : utile seulement aux flux optionnels P→P / P→U.
    """
    if not isinstance(payload, dict):
        return payload

    metadata = payload.setdefault("metadata", {})
    omitted = metadata.setdefault("omitted_heavy_fields", {})

    if not include_route_timeline:
        stripped_count = 0
        stripped_bytes_hint = 0

        for route in payload.get("routes") or []:
            if not isinstance(route, dict):
                continue

            timeline = route.pop("timeline", None)
            if timeline is not None:
                stripped_count += 1
                try:
                    stripped_bytes_hint += len(str(timeline))
                except Exception:
                    pass

        omitted["route.timeline"] = stripped_count
        metadata["include_route_timeline"] = False
        metadata["route_timeline_payload_mode"] = "omitted"
        if stripped_bytes_hint:
            metadata["route_timeline_stripped_chars_hint"] = stripped_bytes_hint
    else:
        metadata["include_route_timeline"] = True

    if not include_extra_flow_families:
        extra = payload.get("extra_flow_families")

        if isinstance(extra, dict):
            families = extra.pop("families", None)

            omitted["extra_flow_families.families"] = (
                len(families)
                if isinstance(families, dict)
                else bool(families)
            )

            extra["families_payload_mode"] = "omitted"
            extra["families_available_on_demand"] = True
            metadata["include_extra_flow_families"] = False
            metadata["extra_flow_families_payload_mode"] = "omitted"
        else:
            metadata["include_extra_flow_families"] = False
    else:
        metadata["include_extra_flow_families"] = True

    return payload


@user_to_professional_map_bp.route("/api/user-to-professional-map", methods=["GET"])
def user_to_professional_map():
    try:
        requested_mlc = (
            request.args.get("mlc_id")
            or request.args.get("mlc")
            or request.args.get("instance")
        )
        mlc_id = _resolve_requested_mlc_id(requested_mlc)

        payload = get_user_to_professional_map_payload(
            mlc_id=mlc_id,
            start=request.args.get("start"),
            end=request.args.get("end"),
            min_users=_int_arg("min_users", 3),
            limit_routes=_int_arg("limit_routes", 800),
            max_render_distance_km=_float_arg("max_render_distance_km", 20.0),
        )
        # CARTO_CLUSTER_MAIN_OPT001_COMPACT_GEOMETRY
        # CARTO_CLUSTER_MAIN_OPT005A_REPRESENTATIVE_SOURCE_POINTS
        payload = _compact_user_to_professional_map_source_points(
            payload,
            source_points_mode=request.args.get("source_points_mode", "full"),
        )

        # CARTO_CLUSTER_MAIN_OPT006A_COMPACT_ROUTE_ENDPOINTS
        payload = _compact_user_to_professional_map_route_endpoints(
            payload,
            route_endpoint_mode=request.args.get("route_endpoint_mode", "full"),
        )

        if _bool_arg("compact_geometry", False) or _bool_arg("compact", False):
            payload = _compact_user_to_professional_map_payload(payload)

        # CARTO_CLUSTER_MAIN_OPT003A_OPTIONAL_HEAVY_FIELDS
        payload = _strip_user_to_professional_map_heavy_fields(
            payload,
            include_route_timeline=_bool_arg("include_route_timeline", True),
            include_extra_flow_families=_bool_arg("include_extra_flow_families", True),
        )

        return jsonify(payload)
    except Exception as exc:
        return jsonify({
            "error": "Erreur lors de la génération de la cartographie U→P.",
            "detail": str(exc),
        }), 500
