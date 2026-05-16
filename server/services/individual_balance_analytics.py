from __future__ import annotations

from datetime import date

from server.database import get_connection


def parse_optional_iso_date(raw_value, field_name: str) -> date | None:
    """
    Parse un paramètre optionnel au format YYYY-MM-DD.
    """
    if raw_value in (None, ""):
        return None

    try:
        return date.fromisoformat(str(raw_value))
    except ValueError as exc:
        raise ValueError(
            f"Paramètre '{field_name}' invalide. Format attendu : YYYY-MM-DD."
        ) from exc


def _round_money(value) -> float:
    """
    Normalise les montants monétaires agrégés.
    """
    return round(float(value or 0.0), 2)


def _round_average(value) -> float | None:
    """
    Normalise les moyennes tout en conservant None
    quand aucun sous-ensemble ne permet le calcul.
    """
    if value is None:
        return None
    return round(float(value), 2)


def _get_balance_bounds(cur) -> dict | None:
    row = cur.execute("""
        SELECT
            MIN(balance_date) AS min_date,
            MAX(balance_date) AS max_date
        FROM cyclos_individual_daily_balances
    """).fetchone()

    if row is None or row["min_date"] is None or row["max_date"] is None:
        return None

    return {
        "min_date": row["min_date"],
        "max_date": row["max_date"],
    }


def _resolve_period(cur, requested_start: date | None, requested_end: date | None) -> dict:
    """
    Résout une période demandée en la bornant par les données réellement présentes.
    """
    bounds = _get_balance_bounds(cur)

    if bounds is None:
        return {
            "bounds": None,
            "requested_start": requested_start.isoformat() if requested_start else None,
            "requested_end": requested_end.isoformat() if requested_end else None,
            "effective_start": None,
            "effective_end": None,
        }

    min_date = date.fromisoformat(bounds["min_date"])
    max_date = date.fromisoformat(bounds["max_date"])

    start = requested_start or min_date
    end = requested_end or max_date

    if start > end:
        raise ValueError(
            "Période invalide : la date de début est postérieure à la date de fin."
        )

    effective_start = max(start, min_date)
    effective_end = min(end, max_date)

    if effective_start > effective_end:
        effective_start = None
        effective_end = None

    return {
        "bounds": bounds,
        "requested_start": start.isoformat(),
        "requested_end": end.isoformat(),
        "effective_start": effective_start.isoformat() if effective_start else None,
        "effective_end": effective_end.isoformat() if effective_end else None,
    }


def _aggregate_row_to_dict(row) -> dict | None:
    if row is None:
        return None

    return {
        "snapshot_date": row["snapshot_date"],
        "users_total": int(row["users_total"] or 0),
        "users_positive": int(row["users_positive"] or 0),
        "users_zero": int(row["users_zero"] or 0),
        "users_negative": int(row["users_negative"] or 0),
        "balance_total": _round_money(row["balance_total"]),
        "balance_positive_total": _round_money(row["balance_positive_total"]),
        "balance_negative_total": _round_money(row["balance_negative_total"]),
        "average_balance_all": _round_average(row["average_balance_all"]),
        "average_balance_positive": _round_average(row["average_balance_positive"]),
        "balance_min": _round_money(row["balance_min"]),
        "balance_max": _round_money(row["balance_max"]),
    }


def _aggregate_snapshot_for_date(cur, snapshot_date: str) -> dict | None:
    row = cur.execute("""
        SELECT
            balance_date AS snapshot_date,
            COUNT(*) AS users_total,
            SUM(CASE WHEN balance > 0 THEN 1 ELSE 0 END) AS users_positive,
            SUM(CASE WHEN balance = 0 THEN 1 ELSE 0 END) AS users_zero,
            SUM(CASE WHEN balance < 0 THEN 1 ELSE 0 END) AS users_negative,
            COALESCE(SUM(balance), 0.0) AS balance_total,
            COALESCE(SUM(CASE WHEN balance > 0 THEN balance ELSE 0.0 END), 0.0)
                AS balance_positive_total,
            COALESCE(SUM(CASE WHEN balance < 0 THEN balance ELSE 0.0 END), 0.0)
                AS balance_negative_total,
            AVG(balance) AS average_balance_all,
            AVG(CASE WHEN balance > 0 THEN balance END) AS average_balance_positive,
            MIN(balance) AS balance_min,
            MAX(balance) AS balance_max
        FROM cyclos_individual_daily_balances
        WHERE balance_date = ?
        GROUP BY balance_date
    """, (snapshot_date,)).fetchone()

    return _aggregate_row_to_dict(row)


def get_individual_balance_status() -> dict:
    """
    Retourne l'état synthétique du dataset de soldes quotidiens particuliers.
    """
    conn = get_connection()
    cur = conn.cursor()

    overview = cur.execute("""
        SELECT
            COUNT(*) AS points_count,
            COUNT(DISTINCT pseudonym) AS individuals_count,
            COUNT(DISTINCT balance_date) AS dates_count,
            MIN(balance_date) AS min_date,
            MAX(balance_date) AS max_date
        FROM cyclos_individual_daily_balances
    """).fetchone()

    if (
        overview is None
        or overview["points_count"] is None
        or int(overview["points_count"] or 0) == 0
    ):
        conn.close()
        return {
            "points_count": 0,
            "individuals_count": 0,
            "dates_count": 0,
            "bounds": None,
            "latest_snapshot": None,
        }

    latest_snapshot = _aggregate_snapshot_for_date(
        cur,
        overview["max_date"],
    )

    conn.close()

    return {
        "points_count": int(overview["points_count"] or 0),
        "individuals_count": int(overview["individuals_count"] or 0),
        "dates_count": int(overview["dates_count"] or 0),
        "bounds": {
            "min_date": overview["min_date"],
            "max_date": overview["max_date"],
        },
        "latest_snapshot": latest_snapshot,
    }


def get_individual_balance_daily_series(
    requested_start: date | None,
    requested_end: date | None,
) -> dict:
    """
    Retourne une série quotidienne agrégée sur les soldes particuliers.
    """
    conn = get_connection()
    cur = conn.cursor()

    try:
        period = _resolve_period(cur, requested_start, requested_end)
    except Exception:
        conn.close()
        raise

    if period["effective_start"] is None or period["effective_end"] is None:
        conn.close()
        return {
            "bounds": period["bounds"],
            "requested_period": {
                "start": period["requested_start"],
                "end": period["requested_end"],
            },
            "effective_period": None,
            "items": [],
        }

    rows = cur.execute("""
        SELECT
            balance_date AS snapshot_date,
            COUNT(*) AS users_total,
            SUM(CASE WHEN balance > 0 THEN 1 ELSE 0 END) AS users_positive,
            SUM(CASE WHEN balance = 0 THEN 1 ELSE 0 END) AS users_zero,
            SUM(CASE WHEN balance < 0 THEN 1 ELSE 0 END) AS users_negative,
            COALESCE(SUM(balance), 0.0) AS balance_total,
            COALESCE(SUM(CASE WHEN balance > 0 THEN balance ELSE 0.0 END), 0.0)
                AS balance_positive_total,
            COALESCE(SUM(CASE WHEN balance < 0 THEN balance ELSE 0.0 END), 0.0)
                AS balance_negative_total,
            AVG(balance) AS average_balance_all,
            AVG(CASE WHEN balance > 0 THEN balance END) AS average_balance_positive,
            MIN(balance) AS balance_min,
            MAX(balance) AS balance_max
        FROM cyclos_individual_daily_balances
        WHERE balance_date BETWEEN ? AND ?
        GROUP BY balance_date
        ORDER BY balance_date ASC
    """, (
        period["effective_start"],
        period["effective_end"],
    )).fetchall()

    conn.close()

    return {
        "bounds": period["bounds"],
        "requested_period": {
            "start": period["requested_start"],
            "end": period["requested_end"],
        },
        "effective_period": {
            "start": period["effective_start"],
            "end": period["effective_end"],
        },
        "items": [_aggregate_row_to_dict(row) for row in rows],
    }


BALANCE_DISTRIBUTION_BUCKETS = [
    {
        "key": "negative",
        "label": "Solde négatif",
        "condition_sql": "balance < 0",
        "stock_share_applicable": False,
    },
    {
        "key": "zero",
        "label": "0 G",
        "condition_sql": "balance = 0",
        "stock_share_applicable": True,
    },
    {
        "key": "gt_0_lte_10",
        "label": "0 < solde ≤ 10 G",
        "condition_sql": "balance > 0 AND balance <= 10",
        "stock_share_applicable": True,
    },
    {
        "key": "gt_10_lte_50",
        "label": "10 < solde ≤ 50 G",
        "condition_sql": "balance > 10 AND balance <= 50",
        "stock_share_applicable": True,
    },
    {
        "key": "gt_50_lte_100",
        "label": "50 < solde ≤ 100 G",
        "condition_sql": "balance > 50 AND balance <= 100",
        "stock_share_applicable": True,
    },
    {
        "key": "gt_100_lte_250",
        "label": "100 < solde ≤ 250 G",
        "condition_sql": "balance > 100 AND balance <= 250",
        "stock_share_applicable": True,
    },
    {
        "key": "gt_250_lte_500",
        "label": "250 < solde ≤ 500 G",
        "condition_sql": "balance > 250 AND balance <= 500",
        "stock_share_applicable": True,
    },
    {
        "key": "gt_500_lte_1000",
        "label": "500 < solde ≤ 1 000 G",
        "condition_sql": "balance > 500 AND balance <= 1000",
        "stock_share_applicable": True,
    },
    {
        "key": "gt_1000",
        "label": "Solde > 1 000 G",
        "condition_sql": "balance > 1000",
        "stock_share_applicable": True,
    },
]


def _round_percent(value) -> float | None:
    if value is None:
        return None
    return round(float(value), 2)


def _resolve_snapshot_date(cur, requested_date: date | None) -> dict:
    """
    Résout une date de snapshot :
    - si aucune date n'est fournie, on prend la dernière date disponible ;
    - si la date demandée sort des bornes de la série, effective_date=None.
    """
    bounds = _get_balance_bounds(cur)

    if bounds is None:
        return {
            "bounds": None,
            "requested_date": requested_date.isoformat() if requested_date else None,
            "effective_date": None,
        }

    min_date = date.fromisoformat(bounds["min_date"])
    max_date = date.fromisoformat(bounds["max_date"])

    target_date = requested_date or max_date

    if target_date < min_date or target_date > max_date:
        effective_date = None
    else:
        effective_date = target_date.isoformat()

    return {
        "bounds": bounds,
        "requested_date": target_date.isoformat(),
        "effective_date": effective_date,
    }


def get_individual_balance_distribution(requested_date: date | None) -> dict:
    """
    Retourne la distribution des soldes particuliers pour une date donnée.

    Si aucune date n'est fournie, la dernière date disponible est utilisée.
    Les parts de stock sont calculées relativement au stock positif total :
    c'est la base la plus lisible pour mesurer la concentration de la détention.
    """
    conn = get_connection()
    cur = conn.cursor()

    resolution = _resolve_snapshot_date(cur, requested_date)

    if resolution["effective_date"] is None:
        conn.close()
        return {
            "bounds": resolution["bounds"],
            "requested_date": resolution["requested_date"],
            "effective_date": None,
            "snapshot": None,
            "stock_share_reference": "balance_positive_total",
            "buckets": [],
        }

    effective_date = resolution["effective_date"]
    snapshot = _aggregate_snapshot_for_date(cur, effective_date)

    rows_by_key = {}

    for bucket in BALANCE_DISTRIBUTION_BUCKETS:
        row = cur.execute(f"""
            SELECT
                COUNT(*) AS users_count,
                COALESCE(SUM(balance), 0.0) AS balance_total
            FROM cyclos_individual_daily_balances
            WHERE balance_date = ?
              AND {bucket["condition_sql"]}
        """, (effective_date,)).fetchone()

        rows_by_key[bucket["key"]] = {
            "users_count": int(row["users_count"] or 0),
            "balance_total": _round_money(row["balance_total"]),
        }

    conn.close()

    users_total = int(snapshot["users_total"] or 0) if snapshot else 0
    positive_stock_total = (
        float(snapshot["balance_positive_total"] or 0.0)
        if snapshot else 0.0
    )

    items = []

    for bucket in BALANCE_DISTRIBUTION_BUCKETS:
        raw = rows_by_key[bucket["key"]]
        users_count = raw["users_count"]
        balance_total = raw["balance_total"]

        users_share_percent = None
        if users_total > 0:
            users_share_percent = _round_percent(
                (users_count / users_total) * 100
            )

        stock_share_percent = None
        if bucket["stock_share_applicable"] and positive_stock_total > 0:
            stock_share_percent = _round_percent(
                (balance_total / positive_stock_total) * 100
            )

        items.append({
            "key": bucket["key"],
            "label": bucket["label"],
            "users_count": users_count,
            "users_share_percent": users_share_percent,
            "balance_total": balance_total,
            "stock_share_percent": stock_share_percent,
        })

    return {
        "bounds": resolution["bounds"],
        "requested_date": resolution["requested_date"],
        "effective_date": effective_date,
        "snapshot": snapshot,
        "stock_share_reference": "balance_positive_total",
        "buckets": items,
    }



def _compute_delta(closing: dict | None, opening: dict | None, key: str):
    if closing is None or opening is None:
        return None

    closing_value = closing.get(key)
    opening_value = opening.get(key)

    if closing_value is None or opening_value is None:
        return None

    return round(float(closing_value) - float(opening_value), 2)


def get_individual_balance_period_summary(
    requested_start: date | None,
    requested_end: date | None,
) -> dict:
    """
    Retourne un résumé ouverture / clôture sur une période donnée.
    """
    conn = get_connection()
    cur = conn.cursor()

    try:
        period = _resolve_period(cur, requested_start, requested_end)
    except Exception:
        conn.close()
        raise

    if period["effective_start"] is None or period["effective_end"] is None:
        conn.close()
        return {
            "bounds": period["bounds"],
            "requested_period": {
                "start": period["requested_start"],
                "end": period["requested_end"],
            },
            "effective_period": None,
            "opening_snapshot": None,
            "closing_snapshot": None,
            "period_metrics": None,
        }

    closing_snapshot = _aggregate_snapshot_for_date(
        cur,
        period["effective_end"],
    )

    opening_reference_row = cur.execute("""
        SELECT MAX(balance_date) AS opening_date
        FROM cyclos_individual_daily_balances
        WHERE balance_date < ?
    """, (period["effective_start"],)).fetchone()

    opening_snapshot = None
    if opening_reference_row and opening_reference_row["opening_date"]:
        opening_snapshot = _aggregate_snapshot_for_date(
            cur,
            opening_reference_row["opening_date"],
        )

    conn.close()

    period_metrics = None
    if closing_snapshot is not None and opening_snapshot is not None:
        period_metrics = {
            "balance_total_delta": _compute_delta(
                closing_snapshot,
                opening_snapshot,
                "balance_total",
            ),
            "balance_positive_total_delta": _compute_delta(
                closing_snapshot,
                opening_snapshot,
                "balance_positive_total",
            ),
            "balance_negative_total_delta": _compute_delta(
                closing_snapshot,
                opening_snapshot,
                "balance_negative_total",
            ),
            "users_positive_delta": _compute_delta(
                closing_snapshot,
                opening_snapshot,
                "users_positive",
            ),
            "users_zero_delta": _compute_delta(
                closing_snapshot,
                opening_snapshot,
                "users_zero",
            ),
            "users_negative_delta": _compute_delta(
                closing_snapshot,
                opening_snapshot,
                "users_negative",
            ),
            "average_balance_all_delta": _compute_delta(
                closing_snapshot,
                opening_snapshot,
                "average_balance_all",
            ),
            "average_balance_positive_delta": _compute_delta(
                closing_snapshot,
                opening_snapshot,
                "average_balance_positive",
            ),
        }

    return {
        "bounds": period["bounds"],
        "requested_period": {
            "start": period["requested_start"],
            "end": period["requested_end"],
        },
        "effective_period": {
            "start": period["effective_start"],
            "end": period["effective_end"],
        },
        "opening_snapshot": opening_snapshot,
        "closing_snapshot": closing_snapshot,
        "period_metrics": period_metrics,
    }
