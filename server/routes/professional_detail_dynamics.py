from flask import Blueprint, jsonify, request

from server.services.professional_detail_dynamics import (
    DEFAULT_NETWORK_LIMIT,
    get_professional_detail_dynamics,
)


professional_detail_dynamics_bp = Blueprint(
    "professional_detail_dynamics",
    __name__,
)


@professional_detail_dynamics_bp.route(
    "/api/pro/<professional_ref>/dynamics",
    methods=["GET"],
)
def professional_detail_dynamics(professional_ref: str):
    raw_limit = request.args.get("network_limit")

    try:
        network_limit = (
            int(raw_limit)
            if raw_limit is not None
            else DEFAULT_NETWORK_LIMIT
        )

        payload = get_professional_detail_dynamics(
            professional_ref,
            start=request.args.get("start"),
            end=request.args.get("end"),
            network_limit=network_limit,
        )
    except ValueError as exc:
        return jsonify({
            "status": "error",
            "error": str(exc),
        }), 400

    return jsonify(payload)
