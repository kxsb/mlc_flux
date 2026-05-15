from flask import Blueprint, jsonify

health_bp = Blueprint("health", __name__)


@health_bp.route("/api/v2/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "service": "mlcflux-dev"
    })