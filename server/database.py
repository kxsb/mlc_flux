import sqlite3
from pathlib import Path


DB_PATH = Path(__file__).resolve().parent / "data" / "mlcflux.db"

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            transaction_number TEXT PRIMARY KEY,
            cyclos_id TEXT,
            date TEXT NOT NULL,
            group_label TEXT,
            from_label TEXT,
            to_label TEXT,
            amount REAL,
            type_label TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS sync_state (
            sync_name TEXT PRIMARY KEY,
            last_run_at TEXT,
            last_status TEXT,
            last_message TEXT
        )
    """)

    conn.commit()
    conn.close()