from flask import Blueprint, jsonify, request

from server.services.professional_reuse_prospects import (
    DEFAULT_LIMIT,
    get_professional_reuse_prospects,
)


professional_reuse_prospects_bp = Blueprint(
    "professional_reuse_prospects",
    __name__,
)


@professional_reuse_prospects_bp.route(
    "/api/pro/<professional_ref>/reuse-prospects",
    methods=["GET"],
)
def professional_reuse_prospects(professional_ref: str):
    raw_limit = request.args.get("limit")

    try:
        limit = int(raw_limit) if raw_limit is not None else DEFAULT_LIMIT

        payload = get_professional_reuse_prospects(
            professional_ref,
            start=request.args.get("start"),
            end=request.args.get("end"),
            limit=limit,
        )
    except ValueError as exc:
        return jsonify({
            "status": "error",
            "error": str(exc),
        }), 400

    return jsonify(payload)
