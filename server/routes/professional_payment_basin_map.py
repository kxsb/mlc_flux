from flask import Blueprint, jsonify, request

from server.services.professional_payment_basin_map import (
    DEFAULT_MIN_USERS,
    get_professional_payment_basin_map,
)


professional_payment_basin_map_bp = Blueprint(
    "professional_payment_basin_map",
    __name__,
)


@professional_payment_basin_map_bp.route(
    "/api/pro/<professional_ref>/payment-basin-map",
    methods=["GET"],
)
def professional_payment_basin_map(professional_ref: str):
    raw_min_users = request.args.get("min_users")

    try:
        min_users = (
            int(raw_min_users)
            if raw_min_users is not None
            else DEFAULT_MIN_USERS
        )

        payload = get_professional_payment_basin_map(
            professional_ref,
            start=request.args.get("start"),
            end=request.args.get("end"),
            min_users=min_users,
        )
    except ValueError as exc:
        return jsonify({
            "status": "error",
            "error": str(exc),
        }), 400

    return jsonify(payload)
