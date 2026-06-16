from datetime import UTC, datetime
import json
import os
from pathlib import Path

from server.database import get_connection


def _current_mlc_id() -> str:
    return os.environ.get("MLCFLUX_DEFAULT_MLC_ID") or "gonette"



def _load_operator_professional_refs(mlc_id: str) -> list[str]:
    profile_path = Path("server/data/mlc_profiles") / f"{mlc_id}.json"

    try:
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
    except Exception:
        return []

    refs = (
        (profile.get("monetary_indicators") or {})
        .get("operator_professional_refs")
        or []
    )

    cleaned = []
    for ref in refs:
        ref = str(ref).strip()
        if ref and ref not in cleaned:
            cleaned.append(ref)

    return cleaned


def _prepare_operator_professional_refs_temp_table(cur, refs: list[str]) -> None:
    cur.execute("DROP TABLE IF EXISTS temp_operator_professional_refs")
    cur.execute("""
        CREATE TEMP TABLE temp_operator_professional_refs (
            ref TEXT PRIMARY KEY
        )
    """)

    if refs:
        cur.executemany(
            "INSERT INTO temp_operator_professional_refs (ref) VALUES (?)",
            [(ref,) for ref in refs],
        )


def _fetch_bounds(cur, table_name, day_column):
    row = cur.execute(
        f"""
        SELECT
            MIN({day_column}) AS min_date,
            MAX({day_column}) AS max_date,
            COUNT(*) AS rows_count
        FROM {table_name}
        """
    ).fetchone()

    if (
        row is None
        or row["min_date"] is None
        or row["max_date"] is None
        or int(row["rows_count"] or 0) <= 0
    ):
        return None

    return {
        "min_date": row["min_date"],
        "max_date": row["max_date"],
        "rows_count": int(row["rows_count"] or 0),
    }


def _fetch_balances_common_bounds(cur):
    row = cur.execute("""
        WITH days AS (
            SELECT balance_date AS day
            FROM cyclos_individual_daily_balances
            INTERSECT
            SELECT balance_date AS day
            FROM cyclos_professional_daily_balances
        )
        SELECT
            MIN(day) AS min_date,
            MAX(day) AS max_date,
            COUNT(*) AS days_count
        FROM days
    """).fetchone()

    if (
        row is None
        or row["min_date"] is None
        or row["max_date"] is None
        or int(row["days_count"] or 0) <= 0
    ):
        return None

    return {
        "min_date": row["min_date"],
        "max_date": row["max_date"],
        "days_count": int(row["days_count"] or 0),
    }


def _fetch_system_numeric_mass_bounds(cur, mlc_id: str):
    try:
        row = cur.execute("""
            SELECT
                MIN(balance_date) AS min_date,
                MAX(balance_date) AS max_date,
                COUNT(*) AS rows_count
            FROM cyclos_system_daily_balances
            WHERE mlc_id = ?
              AND role = 'digital_dedicated'
        """, (mlc_id,)).fetchone()
    except Exception:
        return None

    if (
        row is None
        or row["min_date"] is None
        or row["max_date"] is None
        or int(row["rows_count"] or 0) <= 0
    ):
        return None

    return {
        "min_date": row["min_date"],
        "max_date": row["max_date"],
        "rows_count": int(row["rows_count"] or 0),
    }


def refresh_pilotage_holdings_daily_cache() -> dict:
    """
    Reconstruit entièrement le cache quotidien Détention & ancrage.

    Priorité des sources de masse numérique :
    1. Odoo daily, utilisé par la Gonette ;
    2. solde système Cyclos digital_dedicated, utilisé par la Graine ;
    3. fallback soldes seuls, numeric_mass = 0.0.
    """
    computed_at = datetime.now(UTC).isoformat()
    mlc_id = _current_mlc_id()

    conn = get_connection()
    cur = conn.cursor()

    operator_professional_refs = _load_operator_professional_refs(mlc_id)
    _prepare_operator_professional_refs_temp_table(
        cur,
        operator_professional_refs,
    )

    odoo_bounds = _fetch_bounds(
        cur,
        "odoo_monetary_indicators_daily",
        "snapshot_date",
    )

    system_numeric_bounds = _fetch_system_numeric_mass_bounds(cur, mlc_id)
    balances_bounds = _fetch_balances_common_bounds(cur)

    if odoo_bounds is not None:
        mode = "odoo_daily_numeric_mass"
        min_day = odoo_bounds["min_date"]
        max_day = odoo_bounds["max_date"]
        numeric_mass_source = "odoo"
    elif system_numeric_bounds is not None:
        mode = "cyclos_system_daily_numeric_mass"
        min_day = system_numeric_bounds["min_date"]
        max_day = system_numeric_bounds["max_date"]
        numeric_mass_source = "cyclos_system"
    elif balances_bounds is not None:
        mode = "balances_only_no_numeric_mass"
        min_day = balances_bounds["min_date"]
        max_day = balances_bounds["max_date"]
        numeric_mass_source = "none"
    else:
        try:
            cur.execute("DELETE FROM pilotage_holdings_daily_cache")
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

        return {
            "computed_at": computed_at,
            "items_written": 0,
            "min_day": None,
            "max_day": None,
            "mode": "empty",
            "reason": "Aucune donnée quotidienne de soldes U/P disponible.",
        }

    try:
        cur.execute("DELETE FROM pilotage_holdings_daily_cache")

        if numeric_mass_source == "odoo":
            cur.execute("""
                INSERT INTO pilotage_holdings_daily_cache (
                    day,
                    positive_user_stock,
                    positive_professional_network_stock,
                    positive_gonette_business_accounts_stock,
                    positive_professional_total_stock,
                    numeric_mass,
                    computed_at
                )
                WITH daily_user_stock AS (
                    SELECT
                        balance_date AS day,
                        COALESCE(SUM(CASE WHEN balance > 0 THEN balance ELSE 0.0 END), 0.0)
                            AS positive_user_stock
                    FROM cyclos_individual_daily_balances
                    WHERE balance_date BETWEEN ? AND ?
                    GROUP BY balance_date
                ),
                daily_professional_stock AS (
                    SELECT
                        balance_date AS day,
                        COALESCE(SUM(
                            CASE
                                WHEN professional_ref NOT IN (SELECT ref FROM temp_operator_professional_refs)
                                 AND balance > 0
                                THEN balance
                                ELSE 0.0
                            END
                        ), 0.0) AS positive_professional_network_stock,
                        COALESCE(SUM(
                            CASE
                                WHEN professional_ref IN (SELECT ref FROM temp_operator_professional_refs)
                                 AND balance > 0
                                THEN balance
                                ELSE 0.0
                            END
                        ), 0.0) AS positive_gonette_business_accounts_stock,
                        COALESCE(SUM(CASE WHEN balance > 0 THEN balance ELSE 0.0 END), 0.0)
                            AS positive_professional_total_stock
                    FROM cyclos_professional_daily_balances
                    WHERE balance_date BETWEEN ? AND ?
                    GROUP BY balance_date
                ),
                daily_numeric_mass AS (
                    SELECT
                        snapshot_date AS day,
                        gonettes_num_circulation AS numeric_mass
                    FROM odoo_monetary_indicators_daily
                    WHERE snapshot_date BETWEEN ? AND ?
                )
                SELECT
                    daily_user_stock.day,
                    daily_user_stock.positive_user_stock,
                    daily_professional_stock.positive_professional_network_stock,
                    daily_professional_stock.positive_gonette_business_accounts_stock,
                    daily_professional_stock.positive_professional_total_stock,
                    daily_numeric_mass.numeric_mass,
                    ? AS computed_at
                FROM daily_user_stock
                JOIN daily_professional_stock
                    ON daily_professional_stock.day = daily_user_stock.day
                JOIN daily_numeric_mass
                    ON daily_numeric_mass.day = daily_user_stock.day
                ORDER BY daily_user_stock.day ASC
            """, (
                min_day,
                max_day,
                min_day,
                max_day,
                min_day,
                max_day,
                computed_at,
            ))

        elif numeric_mass_source == "cyclos_system":
            cur.execute("""
                INSERT INTO pilotage_holdings_daily_cache (
                    day,
                    positive_user_stock,
                    positive_professional_network_stock,
                    positive_gonette_business_accounts_stock,
                    positive_professional_total_stock,
                    numeric_mass,
                    computed_at
                )
                WITH daily_user_stock AS (
                    SELECT
                        balance_date AS day,
                        COALESCE(SUM(CASE WHEN balance > 0 THEN balance ELSE 0.0 END), 0.0)
                            AS positive_user_stock
                    FROM cyclos_individual_daily_balances
                    WHERE balance_date BETWEEN ? AND ?
                    GROUP BY balance_date
                ),
                daily_professional_stock AS (
                    SELECT
                        balance_date AS day,
                        COALESCE(SUM(
                            CASE
                                WHEN professional_ref NOT IN (SELECT ref FROM temp_operator_professional_refs)
                                 AND balance > 0
                                THEN balance
                                ELSE 0.0
                            END
                        ), 0.0) AS positive_professional_network_stock,
                        COALESCE(SUM(
                            CASE
                                WHEN professional_ref IN (SELECT ref FROM temp_operator_professional_refs)
                                 AND balance > 0
                                THEN balance
                                ELSE 0.0
                            END
                        ), 0.0) AS positive_gonette_business_accounts_stock,
                        COALESCE(SUM(CASE WHEN balance > 0 THEN balance ELSE 0.0 END), 0.0)
                            AS positive_professional_total_stock
                    FROM cyclos_professional_daily_balances
                    WHERE balance_date BETWEEN ? AND ?
                    GROUP BY balance_date
                ),
                daily_numeric_mass AS (
                    SELECT
                        balance_date AS day,
                        balance AS numeric_mass
                    FROM cyclos_system_daily_balances
                    WHERE mlc_id = ?
                      AND role = 'digital_dedicated'
                      AND balance_date BETWEEN ? AND ?
                )
                SELECT
                    daily_user_stock.day,
                    daily_user_stock.positive_user_stock,
                    daily_professional_stock.positive_professional_network_stock,
                    daily_professional_stock.positive_gonette_business_accounts_stock,
                    daily_professional_stock.positive_professional_total_stock,
                    daily_numeric_mass.numeric_mass,
                    ? AS computed_at
                FROM daily_user_stock
                JOIN daily_professional_stock
                    ON daily_professional_stock.day = daily_user_stock.day
                JOIN daily_numeric_mass
                    ON daily_numeric_mass.day = daily_user_stock.day
                ORDER BY daily_user_stock.day ASC
            """, (
                min_day,
                max_day,
                min_day,
                max_day,
                mlc_id,
                min_day,
                max_day,
                computed_at,
            ))

        else:
            cur.execute("""
                INSERT INTO pilotage_holdings_daily_cache (
                    day,
                    positive_user_stock,
                    positive_professional_network_stock,
                    positive_gonette_business_accounts_stock,
                    positive_professional_total_stock,
                    numeric_mass,
                    computed_at
                )
                WITH daily_user_stock AS (
                    SELECT
                        balance_date AS day,
                        COALESCE(SUM(CASE WHEN balance > 0 THEN balance ELSE 0.0 END), 0.0)
                            AS positive_user_stock
                    FROM cyclos_individual_daily_balances
                    WHERE balance_date BETWEEN ? AND ?
                    GROUP BY balance_date
                ),
                daily_professional_stock AS (
                    SELECT
                        balance_date AS day,
                        COALESCE(SUM(
                            CASE
                                WHEN professional_ref NOT IN (SELECT ref FROM temp_operator_professional_refs)
                                 AND balance > 0
                                THEN balance
                                ELSE 0.0
                            END
                        ), 0.0) AS positive_professional_network_stock,
                        COALESCE(SUM(
                            CASE
                                WHEN professional_ref IN (SELECT ref FROM temp_operator_professional_refs)
                                 AND balance > 0
                                THEN balance
                                ELSE 0.0
                            END
                        ), 0.0) AS positive_gonette_business_accounts_stock,
                        COALESCE(SUM(CASE WHEN balance > 0 THEN balance ELSE 0.0 END), 0.0)
                            AS positive_professional_total_stock
                    FROM cyclos_professional_daily_balances
                    WHERE balance_date BETWEEN ? AND ?
                    GROUP BY balance_date
                )
                SELECT
                    daily_user_stock.day,
                    daily_user_stock.positive_user_stock,
                    daily_professional_stock.positive_professional_network_stock,
                    daily_professional_stock.positive_gonette_business_accounts_stock,
                    daily_professional_stock.positive_professional_total_stock,
                    0.0 AS numeric_mass,
                    ? AS computed_at
                FROM daily_user_stock
                JOIN daily_professional_stock
                    ON daily_professional_stock.day = daily_user_stock.day
                ORDER BY daily_user_stock.day ASC
            """, (
                min_day,
                max_day,
                min_day,
                max_day,
                computed_at,
            ))

        summary = cur.execute("""
            SELECT
                COUNT(*) AS items_written,
                MIN(day) AS min_day,
                MAX(day) AS max_day,
                SUM(CASE WHEN numeric_mass > 0 THEN 1 ELSE 0 END) AS days_with_numeric_mass
            FROM pilotage_holdings_daily_cache
        """).fetchone()

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return {
        "computed_at": computed_at,
        "items_written": int(summary["items_written"] or 0),
        "min_day": summary["min_day"],
        "max_day": summary["max_day"],
        "mode": mode,
        "days_with_numeric_mass": int(summary["days_with_numeric_mass"] or 0),
        "operator_professional_refs_count": len(operator_professional_refs),
    }
