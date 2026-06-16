from __future__ import annotations

import secrets

from flask import jsonify, request

from server.config import Config


ADMIN_TOKEN_HEADER = "X-MLCFlux-Admin-Token"


def require_admin_token():
    """
    Protège les routes HTTP d'administration.

    Stratégie fail-closed :
    - si aucun ADMIN_API_TOKEN n'est configuré, l'administration HTTP est désactivée ;
    - si le token est absent ou invalide, l'accès est refusé.
    """
    configured_token = str(Config.ADMIN_API_TOKEN or "")

    if not configured_token:
        return jsonify({
            "error": "Administration HTTP désactivée."
        }), 503

    provided_token = str(request.headers.get(ADMIN_TOKEN_HEADER, "") or "")

    if not provided_token or not secrets.compare_digest(
        provided_token,
        configured_token,
    ):
        return jsonify({
            "error": "Accès refusé."
        }), 403

    return None
