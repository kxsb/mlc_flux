from flask import Blueprint, jsonify, request
from server.database import get_connection

stored_transactions_bp = Blueprint("stored_transactions", __name__)


@stored_transactions_bp.route("/api/v2/stored-transactions", methods=["GET"])
def stored_transactions():
    start = request.args.get("start")
    end = request.args.get("end")
    limit = request.args.get("limit", default=500, type=int)

    # Défense contre les requêtes abusives :
    # - LIMIT négatif SQLite = pas de limite effective
    # - LIMIT très élevé = charge inutile sur la DB et le JSON retourné
    limit = max(1, min(limit or 500, 5000))

    conn = get_connection()
    cur = conn.cursor()

    query = """
        SELECT
            date,
            group_label,
            from_label,
            to_label,
            amount,
            type_label,
            transaction_number
        FROM transactions
        WHERE 1=1
    """
    params = []

    if start:
        query += " AND date >= ?"
        params.append(start)

    if end:
        query += " AND date <= ?"
        params.append(end)

    query += " ORDER BY date DESC LIMIT ?"
    params.append(limit)

    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()

    return jsonify([dict(row) for row in rows])