from __future__ import annotations

from flask import Blueprint, jsonify, request

from server.database import get_connection


transactions_bp = Blueprint("transactions", __name__)

LIVE_TRANSACTIONS_MAX_DAYS = 365


@transactions_bp.route("/api/v2/transactions", methods=["GET"])
def transactions():
    days = request.args.get("days", type=int)
    date_from = request.args.get(
        "date_from",
        default="",
        type=str,
    ).strip() or None
    date_to = request.args.get(
        "date_to",
        default="",
        type=str,
    ).strip() or None

    if days is not None and days <= 0:
        return jsonify({
            "error": "days doit être un entier positif"
        }), 400

    if days is not None and days > LIVE_TRANSACTIONS_MAX_DAYS:
        return jsonify({
            "error": (
                "Période trop large : "
                f"{LIVE_TRANSACTIONS_MAX_DAYS} jours maximum."
            )
        }), 400

    if days is not None and (date_from or date_to):
        return jsonify({
            "error": (
                "days ne peut pas être combiné "
                "avec date_from ou date_to."
            )
        }), 400

    if date_to and not date_from:
        return jsonify({
            "error": "date_to nécessite date_from."
        }), 400

    where = []
    params = []

    if days is not None:
        where.append(
            "date >= datetime('now', ?)"
        )
        params.append(f"-{days} days")

    if date_from:
        where.append(
            "substr(date, 1, 10) >= ?"
        )
        params.append(date_from)

    if date_to:
        where.append(
            "substr(date, 1, 10) <= ?"
        )
        params.append(date_to)

    where_sql = (
        "WHERE " + " AND ".join(where)
        if where
        else ""
    )

    conn = get_connection()

    try:
        rows = conn.execute(
            f"""
            SELECT
                transaction_number,
                external_transaction_id,
                date,
                group_label,
                from_label,
                to_label,
                amount,
                type_label
            FROM transactions
            {where_sql}
            ORDER BY date DESC
            LIMIT 10000
            """,
            params,
        ).fetchall()

        result = [
            {
                "id": (
                    row["external_transaction_id"]
                    or row["transaction_number"]
                ),
                "transactionNumber": row["transaction_number"],
                "date": row["date"],
                "amount": row["amount"],
                "description": row["type_label"],
                "from": row["from_label"],
                "to": row["to_label"],
                "group": row["group_label"],
                "type": row["type_label"],
            }
            for row in rows
        ]

        return jsonify(result)

    finally:
        conn.close()
