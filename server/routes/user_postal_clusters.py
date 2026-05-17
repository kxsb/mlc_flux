from flask import Blueprint, jsonify, request

from server.services.user_postal_cluster_analytics import (
    DEFAULT_MIN_INDIVIDUALS,
    get_user_postal_clusters,
)


user_postal_clusters_bp = Blueprint("user_postal_clusters", __name__)


@user_postal_clusters_bp.route("/api/user-postal-clusters", methods=["GET"])
def user_postal_clusters():
    raw_min_individuals = request.args.get("min_individuals")

    try:
        min_individuals = (
            int(raw_min_individuals)
            if raw_min_individuals is not None
            else DEFAULT_MIN_INDIVIDUALS
        )
    except (TypeError, ValueError):
        min_individuals = DEFAULT_MIN_INDIVIDUALS

    payload = get_user_postal_clusters(
        start=request.args.get("start"),
        end=request.args.get("end"),
        min_individuals=min_individuals,
    )

    return jsonify(payload)
