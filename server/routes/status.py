from flask import Blueprint, jsonify

from server.database import get_connection


status_bp = Blueprint("status", __name__)


@status_bp.route("/api/v2/status", methods=["GET"])
def application_status():
    conn = get_connection()

    try:
        db_row = conn.execute("""
            SELECT
                COUNT(*) AS transaction_count,
                MIN(substr(date, 1, 10)) AS min_date,
                MAX(substr(date, 1, 10)) AS max_date
            FROM transactions
        """).fetchone()
    finally:
        conn.close()

    return jsonify({
        "status": "ok",
        "service": "mlcflux-dev",
        "database": {
            "transaction_count": (
                db_row["transaction_count"]
                if db_row else 0
            ),
            "min_date": (
                db_row["min_date"]
                if db_row else None
            ),
            "max_date": (
                db_row["max_date"]
                if db_row else None
            ),
        },
        "sync": {
            "managed": False,
            "sync_name": None,
            "last_run_at": None,
            "last_status": "not_managed",
            "last_message": (
                "La synchronisation amont n'est pas gérée "
                "par le socle MLCFlux Lite."
            ),
        },
    })
