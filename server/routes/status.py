from flask import Blueprint, jsonify

from server.database import get_connection


status_bp = Blueprint("status", __name__)


@status_bp.route("/api/v2/status", methods=["GET"])
def application_status():
    conn = get_connection()
    cur = conn.cursor()

    db_row = cur.execute("""
        SELECT
            COUNT(*) AS transaction_count,
            MIN(substr(date, 1, 10)) AS min_date,
            MAX(substr(date, 1, 10)) AS max_date
        FROM transactions
    """).fetchone()

    sync_row = cur.execute("""
        SELECT
            sync_name,
            last_run_at,
            last_status,
            last_message
        FROM sync_state
        WHERE sync_name = 'daily_sync'
        LIMIT 1
    """).fetchone()

    conn.close()

    return jsonify({
        "status": "ok",
        "service": "mlcflux-dev",
        "database": {
            "transaction_count": db_row["transaction_count"] if db_row else 0,
            "min_date": db_row["min_date"] if db_row else None,
            "max_date": db_row["max_date"] if db_row else None,
        },
        "sync": {
            "sync_name": sync_row["sync_name"] if sync_row else "daily_sync",
            "last_run_at": sync_row["last_run_at"] if sync_row else None,
            "last_status": sync_row["last_status"] if sync_row else None,
            "last_message": sync_row["last_message"] if sync_row else None,
        },
    })
