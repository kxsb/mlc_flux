from datetime import UTC, datetime

from server.database import get_connection


def refresh_pilotage_holdings_daily_cache() -> dict:
    """
    Reconstruit entièrement le cache quotidien Détention & ancrage.

    Le cache matérialise les stocks positifs quotidiens alignés avec la
    masse monétaire numérique Odoo. Il est volontairement reconstructible
    depuis les tables analytiques sources.
    """
    computed_at = datetime.now(UTC).isoformat()

    conn = get_connection()
    cur = conn.cursor()

    monetary_bounds = cur.execute("""
        SELECT
            MIN(snapshot_date) AS min_date,
            MAX(snapshot_date) AS max_date
        FROM odoo_monetary_indicators_daily
    """).fetchone()

    if (
        monetary_bounds is None
        or monetary_bounds["min_date"] is None
        or monetary_bounds["max_date"] is None
    ):
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
            "reason": "Aucune donnée monétaire quotidienne Odoo disponible.",
        }

    min_day = monetary_bounds["min_date"]
    max_day = monetary_bounds["max_date"]

    try:
        cur.execute("DELETE FROM pilotage_holdings_daily_cache")

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
                    COALESCE(
                        SUM(CASE WHEN balance > 0 THEN balance ELSE 0.0 END),
                        0.0
                    ) AS positive_user_stock
                FROM cyclos_individual_daily_balances
                WHERE balance_date BETWEEN ? AND ?
                GROUP BY balance_date
            ),
            daily_professional_stock AS (
                SELECT
                    balance_date AS day,
                    COALESCE(
                        SUM(
                            CASE
                                WHEN professional_ref NOT IN ('P0000', 'P9999')
                                 AND balance > 0
                                THEN balance
                                ELSE 0.0
                            END
                        ),
                        0.0
                    ) AS positive_professional_network_stock,
                    COALESCE(
                        SUM(
                            CASE
                                WHEN professional_ref IN ('P0000', 'P9999')
                                 AND balance > 0
                                THEN balance
                                ELSE 0.0
                            END
                        ),
                        0.0
                    ) AS positive_gonette_business_accounts_stock,
                    COALESCE(
                        SUM(CASE WHEN balance > 0 THEN balance ELSE 0.0 END),
                        0.0
                    ) AS positive_professional_total_stock
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
                daily_user_stock.day AS day,
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

        summary = cur.execute("""
            SELECT
                COUNT(*) AS items_written,
                MIN(day) AS min_day,
                MAX(day) AS max_day
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
    }
