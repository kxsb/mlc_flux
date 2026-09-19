import re
import sqlite3
from pathlib import Path

from server.mlc_context import (
    ensure_mlc_instance_dirs,
    get_active_mlc_db_path,
)


def get_db_path() -> Path:
    db_path = get_active_mlc_db_path()

    ensure_mlc_instance_dirs(db_path.parent.name)
    return db_path


def get_connection():
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
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
            external_transaction_id TEXT,
            date TEXT NOT NULL,
            group_label TEXT,
            from_label TEXT,
            to_label TEXT,
            amount REAL,
            type_label TEXT
        )
    """)

    cur.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_transactions_external_transaction_id_unique
        ON transactions (external_transaction_id)
        WHERE external_transaction_id IS NOT NULL AND TRIM(external_transaction_id) <> ''
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
        CREATE TABLE IF NOT EXISTS individual_daily_balances (
            pseudonym TEXT NOT NULL,
            balance_date TEXT NOT NULL,
            balance REAL NOT NULL,
            fetched_at TEXT NOT NULL,
            source TEXT NOT NULL,
            PRIMARY KEY (pseudonym, balance_date)
        )
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_individual_daily_balances_date
        ON individual_daily_balances (balance_date)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_individual_daily_balances_pseudonym
        ON individual_daily_balances (pseudonym)
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS professional_daily_balances (
            professional_ref TEXT NOT NULL,
            balance_date TEXT NOT NULL,
            balance REAL NOT NULL,
            fetched_at TEXT NOT NULL,
            source TEXT NOT NULL,
            PRIMARY KEY (professional_ref, balance_date)
        )
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_professional_daily_balances_date
        ON professional_daily_balances (balance_date)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_professional_daily_balances_ref
        ON professional_daily_balances (professional_ref)
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS monetary_indicators_yearly (
            year INTEGER PRIMARY KEY,
            numeric_circulation REAL NOT NULL,
            paper_circulation REAL NOT NULL,
            total_circulation REAL NOT NULL,
            numeric_guarantee_fund REAL NOT NULL,
            paper_guarantee_fund REAL NOT NULL,
            numeric_guarantee_gap REAL NOT NULL,
            paper_guarantee_gap REAL NOT NULL,
            fetched_at TEXT NOT NULL,
            source TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS monetary_indicators_daily (
            snapshot_date TEXT PRIMARY KEY,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            day INTEGER NOT NULL,
            numeric_circulation REAL NOT NULL,
            paper_circulation REAL NOT NULL,
            total_circulation REAL NOT NULL,
            numeric_guarantee_fund REAL NOT NULL,
            paper_guarantee_fund REAL NOT NULL,
            numeric_guarantee_gap REAL NOT NULL,
            paper_guarantee_gap REAL NOT NULL,
            fetched_at TEXT NOT NULL,
            source TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_monetary_indicators_daily_year_month
        ON monetary_indicators_daily (year, month, day)
    """)




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
            positive_operator_professional_stock REAL NOT NULL,
            positive_professional_total_stock REAL NOT NULL,
            numeric_mass REAL NOT NULL,
            computed_at TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


def init_professional_enrichment_db():
    """
    Initialise le registre interne neutre d'enrichissement professionnel.

    Les adaptateurs amont doivent alimenter cette table sans exposer
    leur modèle source au reste de l'application.
    """
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS professional_enrichment (
            professional_ref TEXT PRIMARY KEY,
            source_provider TEXT NOT NULL,
            external_professional_ref TEXT,
            actor_type_internal TEXT,
            display_name TEXT,
            legal_name TEXT,
            industry_name TEXT,
            industry_internal_name TEXT,
            secondary_industries_json TEXT,
            secondary_industry_internal_names_json TEXT,
            payment_methods_accepted_json TEXT,
            detailed_activity TEXT,
            short_description TEXT,
            keywords TEXT,
            website TEXT,
            siret TEXT,
            siren TEXT,
            street TEXT,
            zip TEXT,
            city TEXT,
            latitude REAL,
            longitude REAL,
            raw_safe_json TEXT,
            fetched_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_professional_enrichment_source_provider
        ON professional_enrichment (source_provider)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_professional_enrichment_city_zip
        ON professional_enrichment (city, zip)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_professional_enrichment_industry
        ON professional_enrichment (industry_name)
    """)

    conn.commit()
    conn.close()


def init_geography_db():
    """
    Initialise le modèle géographique interne neutre de MLCFlux.

    Deux niveaux sont séparés :

    - geographic_areas :
      référentiel réutilisable des territoires, zones et géométries ;

    - actor_geography :
      localisation canonique résolue d'un acteur MLCFlux.

    Les tables sources propres à un provider ne doivent pas être
    interrogées par les analytics ou le frontend. La résolution
    géographique constitue la frontière entre les données provider
    et ce modèle interne.
    """
    conn = get_connection()
    cur = conn.cursor()

    # -------------------------------------------------------------
    # Référentiel géographique
    # -------------------------------------------------------------

    cur.execute("""
        CREATE TABLE IF NOT EXISTS geographic_areas (
            area_id TEXT PRIMARY KEY,

            area_type TEXT NOT NULL,
            country_code TEXT,
            area_code TEXT,

            name TEXT,
            short_name TEXT,

            parent_area_id TEXT,

            latitude REAL,
            longitude REAL,

            geometry_kind TEXT,
            geometry_geojson TEXT,

            source_provider TEXT NOT NULL,
            source_record_id TEXT,
            source_updated_at TEXT,

            metadata_json TEXT,

            fetched_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,

            FOREIGN KEY (parent_area_id)
                REFERENCES geographic_areas(area_id)
                ON DELETE SET NULL,

            CHECK (
                latitude IS NULL
                OR (
                    latitude >= -90
                    AND latitude <= 90
                )
            ),

            CHECK (
                longitude IS NULL
                OR (
                    longitude >= -180
                    AND longitude <= 180
                )
            ),

            CHECK (
                (
                    latitude IS NULL
                    AND longitude IS NULL
                )
                OR
                (
                    latitude IS NOT NULL
                    AND longitude IS NOT NULL
                )
            )
        )
    """)

    cur.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS
        idx_geographic_areas_natural_identity
        ON geographic_areas (
            country_code,
            area_type,
            area_code
        )
        WHERE
            area_code IS NOT NULL
            AND TRIM(area_code) <> ''
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS
        idx_geographic_areas_type
        ON geographic_areas (area_type)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS
        idx_geographic_areas_parent
        ON geographic_areas (parent_area_id)
    """)

    # -------------------------------------------------------------
    # Géographie canonique des acteurs
    # -------------------------------------------------------------

    cur.execute("""
        CREATE TABLE IF NOT EXISTS actor_geography (
            actor_ref TEXT PRIMARY KEY,
            actor_family TEXT NOT NULL,

            mlc_territory_area_id TEXT,
            postal_area_id TEXT,
            commune_area_id TEXT,

            street TEXT,
            postal_code TEXT,
            city TEXT,

            latitude REAL,
            longitude REAL,

            precision_level TEXT NOT NULL,
            confidence_level TEXT NOT NULL,
            resolution_method TEXT NOT NULL,

            resolution_sources_json TEXT,
            resolution_trace_json TEXT,

            resolved_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,

            FOREIGN KEY (mlc_territory_area_id)
                REFERENCES geographic_areas(area_id)
                ON DELETE SET NULL,

            FOREIGN KEY (postal_area_id)
                REFERENCES geographic_areas(area_id)
                ON DELETE SET NULL,

            FOREIGN KEY (commune_area_id)
                REFERENCES geographic_areas(area_id)
                ON DELETE SET NULL,

            CHECK (
                latitude IS NULL
                OR (
                    latitude >= -90
                    AND latitude <= 90
                )
            ),

            CHECK (
                longitude IS NULL
                OR (
                    longitude >= -180
                    AND longitude <= 180
                )
            ),

            CHECK (
                (
                    latitude IS NULL
                    AND longitude IS NULL
                )
                OR
                (
                    latitude IS NOT NULL
                    AND longitude IS NOT NULL
                )
            )
        )
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS
        idx_actor_geography_family
        ON actor_geography (actor_family)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS
        idx_actor_geography_mlc_territory
        ON actor_geography (mlc_territory_area_id)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS
        idx_actor_geography_postal_area
        ON actor_geography (postal_area_id)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS
        idx_actor_geography_commune_area
        ON actor_geography (commune_area_id)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS
        idx_actor_geography_postal_code
        ON actor_geography (postal_code)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS
        idx_actor_geography_precision
        ON actor_geography (
            precision_level,
            confidence_level
        )
    """)

    conn.commit()
    conn.close()
