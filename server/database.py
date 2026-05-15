import sqlite3
from pathlib import Path


DB_PATH = Path(__file__).resolve().parent / "data" / "mlcflux.db"

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn



def _ensure_column(cur, table_name, column_name, column_type):
    """
    Ajoute une colonne à une table SQLite si elle n'existe pas encore.
    Sert de migration légère pour les bases déjà initialisées.
    """
    existing_columns = {
        row[1]
        for row in cur.execute(f"PRAGMA table_info({table_name})").fetchall()
    }

    if column_name not in existing_columns:
        cur.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
        )

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

    cur.execute("""
        CREATE TABLE IF NOT EXISTS odoo_professional_enrichment (
            professional_ref TEXT PRIMARY KEY,
            odoo_partner_id INTEGER NOT NULL,
            odoo_name TEXT NOT NULL,
            industry_id INTEGER,
            industry_name TEXT,
            detailed_activity TEXT,
            website_description_html TEXT,
            keywords TEXT,
            naf TEXT,
            street TEXT,
            zip TEXT,
            city TEXT,
            latitude REAL,
            longitude REAL,
            date_localization TEXT,
            membership_state TEXT,
            is_former_member INTEGER,
            cyclos_address_id TEXT,
            cyclos_address_line1 TEXT,
            cyclos_zip TEXT,
            cyclos_city TEXT,
            cyclos_latitude REAL,
            cyclos_longitude REAL,
            geo_distance_meters REAL,
            geo_match_status TEXT,
            fetched_at TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS odoo_professional_secondary_industries (
            professional_ref TEXT NOT NULL,
            industry_id INTEGER NOT NULL,
            industry_name TEXT NOT NULL,
            PRIMARY KEY (professional_ref, industry_id)
        )
    """)

    _ensure_column(cur, "odoo_professional_enrichment", "cyclos_address_id", "TEXT")
    _ensure_column(cur, "odoo_professional_enrichment", "cyclos_address_line1", "TEXT")
    _ensure_column(cur, "odoo_professional_enrichment", "cyclos_zip", "TEXT")
    _ensure_column(cur, "odoo_professional_enrichment", "cyclos_city", "TEXT")
    _ensure_column(cur, "odoo_professional_enrichment", "cyclos_latitude", "REAL")
    _ensure_column(cur, "odoo_professional_enrichment", "cyclos_longitude", "REAL")
    _ensure_column(cur, "odoo_professional_enrichment", "geo_distance_meters", "REAL")
    _ensure_column(cur, "odoo_professional_enrichment", "geo_match_status", "TEXT")

    conn.commit()
    conn.close()