from flask import Blueprint, jsonify

from server.utils.sync_auth import require_sync_token

sync_bp = Blueprint("sync", __name__)


def _format_sync_message(fetched, written):
    fetched_label = "transaction vérifiée" if fetched == 1 else "transactions vérifiées"
    written_label = (
        "transaction écrite / upsertée"
        if written == 1
        else "transactions écrites / upsertées"
    )

    return (
        "Synchronisation terminée : "
        f"{fetched} {fetched_label}, "
        f"{written} {written_label}."
    )


@sync_bp.route("/api/v2/sync", methods=["POST"])
def sync_transactions_now():
    auth_error = require_sync_token()
    if auth_error is not None:
        return auth_error

    from server.sync_transactions import run_sync

    result = run_sync()
    fetched = result["fetched"]
    written = result["written"]

    return jsonify({
        "status": "success",
        "fetched": fetched,
        "written": written,
        # Alias de compatibilité pour d'éventuels appelants historiques.
        "inserted": written,
        "message": _format_sync_message(fetched, written),
    })
