import secrets

from flask import current_app, jsonify, request


SYNC_TOKEN_HEADER = "X-MLCFlux-Sync-Token"


def require_sync_token():
    """
    Protège les endpoints HTTP capables de déclencher une synchronisation Cyclos.

    Par défaut, aucun token n'est configuré : les routes restent donc désactivées
    côté web. Le cron / CLI ne passent pas par ces routes et restent inchangés.
    """
    expected_token = str(current_app.config.get("SYNC_API_TOKEN", "") or "")
    provided_token = str(request.headers.get(SYNC_TOKEN_HEADER, "") or "")

    if not expected_token:
        return jsonify({
            "error": "Synchronisation HTTP désactivée."
        }), 503

    if not provided_token or not secrets.compare_digest(provided_token, expected_token):
        return jsonify({
            "error": "Accès refusé."
        }), 403

    return None
