import re
import sqlite3
from pathlib import Path


DB_PATH = Path(__file__).resolve().parent / "data" / "mlcflux.db"

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # WAL améliore la coexistence entre lectures HTTP et écritures de sync.
    # Le mode est persistant au niveau de la base SQLite.
    conn.execute("PRAGMA journal_mode = WAL")

    # Les contraintes FOREIGN KEY sont désactivées par défaut dans SQLite
    # et doivent être réactivées pour chaque nouvelle connexion.
    conn.execute("PRAGMA foreign_keys = ON")

    # Rend explicite l'attente en cas de verrou temporaire.
    conn.execute("PRAGMA busy_timeout = 5000")

    return conn


_SQL_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _validate_sql_identifier(value, *, field_name="identifiant SQL"):
    """
    Valide un identifiant SQL utilisé dans les fragments DDL internes.

    Les valeurs autorisées sont volontairement strictes :
    - lettres ASCII, chiffres et underscore uniquement ;
    - pas de chiffre en premier caractère ;
    - aucun espace, guillemet, séparateur ou fragment SQL.
    """
    normalized = str(value or "").strip()

    if not _SQL_IDENTIFIER_RE.fullmatch(normalized):
        raise ValueError(
            f"{field_name} invalide : {value!r}"
        )

    return normalized


def _ensure_column(cur, table_name, column_name, column_type):
    """
    Ajoute une colonne à une table SQLite si elle n'existe pas encore.
    Sert de migration légère pour les bases déjà initialisées.

    Les noms de table et colonne sont construits dynamiquement à partir
    de constantes internes, mais restent validés strictement par défense
    en profondeur avant d'être injectés dans du DDL SQLite.
    """
    table_name = _validate_sql_identifier(
        table_name,
        field_name="nom de table",
    )
    column_name = _validate_sql_identifier(
        column_name,
        field_name="nom de colonne",
    )

    existing_columns = {
        row[1]
        for row in cur.execute(
            f'PRAGMA table_info("{table_name}")'
        ).fetchall()
    }

    if column_name not in existing_columns:
        cur.execute(
            f'ALTER TABLE "{table_name}" ADD COLUMN "{column_name}" {column_type}'
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
        CREATE UNIQUE INDEX IF NOT EXISTS idx_transactions_cyclos_id_unique
        ON transactions (cyclos_id)
        WHERE cyclos_id IS NOT NULL AND TRIM(cyclos_id) <> ''
    """)

    # Optimise les analyses territoriales et de bassins de flux
    # qui croisent l'émetteur et le jour transactionnel.
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_transactions_from_label_day
        ON transactions (from_label, substr(date, 1, 10))
    """)

    # Optimise les agrégations professionnelles fondées sur
    # la référence Pxxxx extraite du libellé émetteur.
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_transactions_from_prof_ref_day
        ON transactions (substr(from_label, 1, 5), substr(date, 1, 10))
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


    cur.execute("""
        CREATE TABLE IF NOT EXISTS odoo_individual_enrichment (
            pseudonym TEXT PRIMARY KEY,
            odoo_match_status TEXT NOT NULL,
            zip TEXT,
            city TEXT,
            latitude REAL,
            longitude REAL,
            membership_state TEXT,
            is_former_member INTEGER,
            has_zip INTEGER NOT NULL DEFAULT 0,
            has_city INTEGER NOT NULL DEFAULT 0,
            has_coordinates INTEGER NOT NULL DEFAULT 0,
            fetched_at TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'odoo_jsonrpc_via_cyclos_numadherent'
        )
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_odoo_individual_enrichment_match_status
        ON odoo_individual_enrichment (odoo_match_status)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_odoo_individual_enrichment_zip
        ON odoo_individual_enrichment (zip)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_odoo_individual_enrichment_city
        ON odoo_individual_enrichment (city)
    """)


    cur.execute("""
        CREATE TABLE IF NOT EXISTS cyclos_individual_daily_balances (
            pseudonym TEXT NOT NULL,
            balance_date TEXT NOT NULL,
            balance REAL NOT NULL,
            fetched_at TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'cyclos_balances_history_daily',
            PRIMARY KEY (pseudonym, balance_date)
        )
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_cyclos_individual_daily_balances_date
        ON cyclos_individual_daily_balances (balance_date)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_cyclos_individual_daily_balances_pseudonym
        ON cyclos_individual_daily_balances (pseudonym)
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS cyclos_individual_daily_balance_windows (
            pseudonym TEXT NOT NULL,
            window_date_from TEXT NOT NULL,
            window_date_to TEXT NOT NULL,
            status TEXT NOT NULL,
            points_received INTEGER NOT NULL DEFAULT 0,
            points_stored INTEGER NOT NULL DEFAULT 0,
            attempts INTEGER NOT NULL DEFAULT 0,
            last_error TEXT,
            last_run_at TEXT,
            fetched_at TEXT,
            PRIMARY KEY (pseudonym, window_date_from, window_date_to)
        )
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_cyclos_individual_daily_balance_windows_status
        ON cyclos_individual_daily_balance_windows (status)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_cyclos_individual_daily_balance_windows_pseudonym
        ON cyclos_individual_daily_balance_windows (pseudonym)
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS cyclos_professional_daily_balances (
            professional_ref TEXT NOT NULL,
            balance_date TEXT NOT NULL,
            balance REAL NOT NULL,
            fetched_at TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'cyclos_professional_balances_history_daily',
            PRIMARY KEY (professional_ref, balance_date)
        )
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_cyclos_professional_daily_balances_date
        ON cyclos_professional_daily_balances (balance_date)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_cyclos_professional_daily_balances_ref
        ON cyclos_professional_daily_balances (professional_ref)
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS cyclos_professional_daily_balance_windows (
            professional_ref TEXT NOT NULL,
            window_date_from TEXT NOT NULL,
            window_date_to TEXT NOT NULL,
            status TEXT NOT NULL,
            points_received INTEGER NOT NULL DEFAULT 0,
            points_stored INTEGER NOT NULL DEFAULT 0,
            attempts INTEGER NOT NULL DEFAULT 0,
            last_error TEXT,
            last_run_at TEXT,
            fetched_at TEXT,
            PRIMARY KEY (professional_ref, window_date_from, window_date_to)
        )
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_cyclos_professional_daily_balance_windows_status
        ON cyclos_professional_daily_balance_windows (status)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_cyclos_professional_daily_balance_windows_ref
        ON cyclos_professional_daily_balance_windows (professional_ref)
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS odoo_monetary_indicators_yearly (
            year INTEGER PRIMARY KEY,
            gonettes_num_circulation REAL NOT NULL,
            gonettes_paper_circulation REAL NOT NULL,
            gonettes_total_circulation REAL NOT NULL,
            fonds_garantie_num REAL NOT NULL,
            fonds_garantie_paper REAL NOT NULL,
            ecart_num REAL NOT NULL,
            ecart_paper REAL NOT NULL,
            fetched_at TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'odoo_jsonrpc'
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS odoo_monetary_indicators_daily (
            snapshot_date TEXT PRIMARY KEY,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            day INTEGER NOT NULL,
            gonettes_num_circulation REAL NOT NULL,
            gonettes_paper_circulation REAL NOT NULL,
            gonettes_total_circulation REAL NOT NULL,
            fonds_garantie_num REAL NOT NULL,
            fonds_garantie_paper REAL NOT NULL,
            ecart_num REAL NOT NULL,
            ecart_paper REAL NOT NULL,
            fetched_at TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'odoo_jsonrpc'
        )
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_odoo_monetary_indicators_daily_year_month
        ON odoo_monetary_indicators_daily (year, month, day)
    """)


    cur.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            public_ref TEXT UNIQUE,
            slug TEXT UNIQUE,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'new',
            visibility TEXT NOT NULL DEFAULT 'public',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_activity_at TEXT NOT NULL,
            resolved_at TEXT,
            closed_at TEXT,
            author_name TEXT NOT NULL,
            author_email TEXT NOT NULL,
            source_page TEXT,
            context_json TEXT,
            official_message_id INTEGER
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS ticket_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER NOT NULL,
            author_name TEXT NOT NULL,
            author_email TEXT NOT NULL,
            author_role TEXT NOT NULL DEFAULT 'public',
            body_markdown TEXT NOT NULL,
            visibility TEXT NOT NULL DEFAULT 'public',
            created_at TEXT NOT NULL,
            updated_at TEXT,
            FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE CASCADE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS ticket_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            actor_role TEXT NOT NULL,
            old_value TEXT,
            new_value TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE CASCADE
        )
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_tickets_visibility_status_activity
        ON tickets (visibility, status, last_activity_at DESC)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_tickets_category
        ON tickets (category)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_ticket_messages_ticket_visibility_created
        ON ticket_messages (ticket_id, visibility, created_at)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_ticket_events_ticket_created
        ON ticket_events (ticket_id, created_at)
    """)

    _ensure_column(cur, "odoo_professional_enrichment", "cyclos_address_id", "TEXT")
    _ensure_column(cur, "odoo_professional_enrichment", "cyclos_address_line1", "TEXT")
    _ensure_column(cur, "odoo_professional_enrichment", "cyclos_zip", "TEXT")
    _ensure_column(cur, "odoo_professional_enrichment", "cyclos_city", "TEXT")
    _ensure_column(cur, "odoo_professional_enrichment", "cyclos_latitude", "REAL")
    _ensure_column(cur, "odoo_professional_enrichment", "cyclos_longitude", "REAL")
    _ensure_column(cur, "odoo_professional_enrichment", "geo_distance_meters", "REAL")
    _ensure_column(cur, "odoo_professional_enrichment", "geo_match_status", "TEXT")

    # -----------------------------------------------------------------
    # Index temporels sur transactions
    # -----------------------------------------------------------------
    #
    # Les tableaux de bord filtrent très souvent les transactions par
    # période ou par année. Sans ces index, SQLite scanne toute la table
    # transactions, y compris pour des périodes courtes.
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_transactions_date
        ON transactions(date)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_transactions_day
        ON transactions(substr(date, 1, 10))
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_transactions_year
        ON transactions(substr(date, 1, 4))
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS pilotage_yearly_cache (
            series_key TEXT NOT NULL,
            year INTEGER NOT NULL,
            item_json TEXT NOT NULL,
            computed_at TEXT NOT NULL,
            PRIMARY KEY (series_key, year)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS pilotage_holdings_daily_cache (
            day TEXT PRIMARY KEY,
            positive_user_stock REAL NOT NULL,
            positive_professional_network_stock REAL NOT NULL,
            positive_gonette_business_accounts_stock REAL NOT NULL,
            positive_professional_total_stock REAL NOT NULL,
            numeric_mass REAL NOT NULL,
            computed_at TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()