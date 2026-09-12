from __future__ import annotations

from flask import Blueprint, jsonify

from server.mlc_context import get_default_mlc_id
from server.mlc_profiles import get_mlc_profile


current_mlc_bp = Blueprint("current_mlc", __name__)


@current_mlc_bp.route("/api/current-mlc", methods=["GET"])
def current_mlc():
    """
    Retourne le profil de l'unique MLC configurée sur cette installation.

    En mode standalone, il n'existe plus de sélection dynamique
    d'instance dans la session utilisateur.
    """
    mlc_id = get_default_mlc_id()
    profile = get_mlc_profile(mlc_id).public_dict()

    return jsonify({
        "authenticated": True,
        "mlc_id": mlc_id,
        "current_mlc_id": mlc_id,
        "active_mlc_id": mlc_id,
        "active_mlc": profile,
    })
