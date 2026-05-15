from flask import Blueprint, jsonify

from server.utils.sync_auth import require_sync_token

sync_bp = Blueprint("sync", __name__)


def _format_sync_message(fetched, inserted):
    fetched_label = "transaction vérifiée" if fetched == 1 else "transactions vérifiées"
    inserted_label = (
        "nouvelle transaction importée"
        if inserted == 1
        else "nouvelles transactions importées"
    )

    return (
        "Synchronisation terminée : "
        f"{fetched} {fetched_label}, "
        f"{inserted} {inserted_label}."
    )


@sync_bp.route("/api/v2/sync", methods=["POST"])
def sync_transactions_now():
    auth_error = require_sync_token()
    if auth_error is not None:
        return auth_error

    from server.sync_transactions import run_sync

    result = run_sync()
    fetched = result["fetched"]
    inserted = result["inserted"]

    return jsonify({
        "status": "success",
        "fetched": fetched,
        "inserted": inserted,
        "message": _format_sync_message(fetched, inserted),
    })
