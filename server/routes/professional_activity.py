from __future__ import annotations

from datetime import date

from flask import Blueprint, jsonify, request

from server.services.professional_activity_analytics import (
    get_professional_activity_flow_summary,
    get_professional_circulation_timeseries,
)


from server.services.professional_chain_fate_analytics import (
    load_professional_chain_fate_summary,
)

from server.services.professional_consumption_map_analytics import (
    get_professional_consumption_map_payload,
)

professional_activity_bp = Blueprint("professional_activity", __name__)


def _parse_optional_iso_date(raw_value: str | None, label: str) -> str | None:
    value = str(raw_value or "").strip()
    if not value:
        return None

    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise ValueError(
            f"Paramètre {label} invalide : date ISO attendue au format YYYY-MM-DD."
        ) from exc


@professional_activity_bp.route(
    "/api/professionals/activity-summary",
    methods=["GET"],
)
def professionals_activity_summary():
    try:
        requested_start = _parse_optional_iso_date(
            request.args.get("start"),
            "start",
        )
        requested_end = _parse_optional_iso_date(
            request.args.get("end"),
            "end",
        )

        if (
            requested_start is not None
            and requested_end is not None
            and requested_start > requested_end
        ):
            raise ValueError(
                "Période invalide : la date de début doit précéder la date de fin."
            )

        payload = get_professional_activity_flow_summary(
            requested_start=requested_start,
            requested_end=requested_end,
        )

    except ValueError as exc:
        return jsonify({
            "status": "error",
            "error": str(exc),
        }), 400

    return jsonify({
        "status": "ok",
        **payload,
    })


@professional_activity_bp.route(
    "/api/professionals/circulation-timeseries",
    methods=["GET"],
)
def professionals_circulation_timeseries():
    try:
        requested_start = _parse_optional_iso_date(
            request.args.get("start"),
            "start",
        )
        requested_end = _parse_optional_iso_date(
            request.args.get("end"),
            "end",
        )

        if (
            requested_start is not None
            and requested_end is not None
            and requested_start > requested_end
        ):
            raise ValueError(
                "Période invalide : la date de début doit précéder la date de fin."
            )

        payload = get_professional_circulation_timeseries(
            requested_start=requested_start,
            requested_end=requested_end,
        )

    except ValueError as exc:
        return jsonify({
            "status": "error",
            "error": str(exc),
        }), 400

    return jsonify({
        "status": "ok",
        **payload,
    })


@professional_activity_bp.route(
    "/api/professionals/chain-fate-summary",
    methods=["GET"],
)
def professionals_chain_fate_summary():
    payload = load_professional_chain_fate_summary()

    if payload is None:
        return jsonify({
            "status": "unavailable",
            "error": (
                "Résumé de trajectoire professionnelle indisponible. "
                "Lancez le script sync_professional_chain_fate_summary.py."
            ),
        }), 404

    return jsonify({
        "status": "ok",
        **payload,
    })


@professional_activity_bp.route(
    "/api/professionals/consumption-map",
    methods=["GET"],
)
def professionals_consumption_map():
    start = request.args.get("start")
    end = request.args.get("end")
    min_users = request.args.get("min_users", default=2, type=int)

    payload = get_professional_consumption_map_payload(
        start=start,
        end=end,
        min_users=min_users or 5,
    )

    return jsonify({
        "status": "ok",
        **payload,
    })

