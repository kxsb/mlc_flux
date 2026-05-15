from flask import Blueprint, current_app, jsonify, request

from server.services.cyclos_client import get_transactions
from server.utils.anonymizer import anonymize_transactions

transactions_bp = Blueprint("transactions", __name__)


@transactions_bp.route("/api/v2/transactions", methods=["GET"])
def transactions():
    try:
        days = request.args.get("days", type=int)
        date_from = request.args.get("date_from", default="", type=str).strip() or None
        date_to = request.args.get("date_to", default="", type=str).strip() or None

        if days is not None and days <= 0:
            return jsonify({"error": "days doit être un entier positif"}), 400

        raw_data = get_transactions(days=days, date_from=date_from, date_to=date_to)
        safe_data = anonymize_transactions(raw_data)
        return jsonify(safe_data)

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        current_app.logger.exception(
            "Erreur inattendue lors de la récupération des transactions Cyclos anonymisées."
        )
        return jsonify({"error": "Erreur serveur interne."}), 500
