from __future__ import annotations

from bisect import bisect_right
from collections import defaultdict
from datetime import date

from server.analytics import (
    _classify_analytical_transaction,
    _structural_flow_key,
    fetch_transactions,
)
from server.database import get_connection


DORMANCY_BUCKET_DEFINITIONS = [
    {
        "key": "active_30",
        "label": "Actif ≤ 30 j",
    },
    {
        "key": "dormant_31_90",
        "label": "Dormant 31–90 j",
    },
    {
        "key": "dormant_91_180",
        "label": "Dormant 91–180 j",
    },
    {
        "key": "dormant_gt_180",
        "label": "Dormant > 180 j",
    },
    {
        "key": "no_activity",
        "label": "Sans activité antérieure retrouvée",
    },
]


def _money2(value) -> float:
    return round(float(value or 0.0), 2)


def _ratio(value, base, digits: int = 6):
    if base in (None, 0):
        return None
    return round(float(value or 0.0) / float(base), digits)


def _date_value(raw_value) -> date:
    return date.fromisoformat(str(raw_value)[:10])


def _empty_bounds():
    return {
        "individual_balances": None,
        "monetary_daily": None,
        "common": None,
    }


def _get_source_bounds(cur) -> dict:
    individual_row = cur.execute("""
        SELECT
            MIN(balance_date) AS min_date,
            MAX(balance_date) AS max_date
        FROM cyclos_individual_daily_balances
    """).fetchone()

    monetary_row = cur.execute("""
        SELECT
            MIN(snapshot_date) AS min_date,
            MAX(snapshot_date) AS max_date
        FROM odoo_monetary_indicators_daily
    """).fetchone()

    if (
        individual_row is None
        or individual_row["min_date"] is None
        or individual_row["max_date"] is None
        or monetary_row is None
        or monetary_row["min_date"] is None
        or monetary_row["max_date"] is None
    ):
        return _empty_bounds()

    individual_bounds = {
        "min_date": individual_row["min_date"],
        "max_date": individual_row["max_date"],
    }

    monetary_bounds = {
        "min_date": monetary_row["min_date"],
        "max_date": monetary_row["max_date"],
    }

    common_min = max(
        _date_value(individual_bounds["min_date"]),
        _date_value(monetary_bounds["min_date"]),
    )
    common_max = min(
        _date_value(individual_bounds["max_date"]),
        _date_value(monetary_bounds["max_date"]),
    )

    common_bounds = None
    if common_min <= common_max:
        common_bounds = {
            "min_date": common_min.isoformat(),
            "max_date": common_max.isoformat(),
        }

    return {
        "individual_balances": individual_bounds,
        "monetary_daily": monetary_bounds,
        "common": common_bounds,
    }


def _resolve_holdings_period(cur, requested_start, requested_end) -> dict:
    bounds = _get_source_bounds(cur)
    common = bounds["common"]

    if common is None:
        return {
            "bounds": bounds,
            "requested_start": requested_start.isoformat() if requested_start else None,
            "requested_end": requested_end.isoformat() if requested_end else None,
            "effective_start": None,
            "effective_end": None,
        }

    min_date = _date_value(common["min_date"])
    max_date = _date_value(common["max_date"])

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


def _fetch_aligned_period_averages(cur, effective_start: str, effective_end: str) -> dict:
    row = cur.execute("""
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
            COUNT(*) AS aligned_day_count,
            AVG(daily_user_stock.positive_user_stock) AS average_positive_user_stock,
            AVG(
                daily_professional_stock.positive_professional_network_stock
            ) AS average_positive_professional_network_stock,
            AVG(
                daily_professional_stock.positive_gonette_business_accounts_stock
            ) AS average_positive_gonette_business_accounts_stock,
            AVG(
                daily_professional_stock.positive_professional_total_stock
            ) AS average_positive_professional_total_stock,
            AVG(daily_numeric_mass.numeric_mass) AS average_numeric_mass,
            AVG(
                CASE
                    WHEN daily_numeric_mass.numeric_mass > 0
                    THEN daily_user_stock.positive_user_stock / daily_numeric_mass.numeric_mass
                    ELSE NULL
                END
            ) AS average_daily_user_stock_share_of_numeric_mass,
            AVG(
                CASE
                    WHEN daily_numeric_mass.numeric_mass > 0
                    THEN daily_professional_stock.positive_professional_network_stock
                         / daily_numeric_mass.numeric_mass
                    ELSE NULL
                END
            ) AS average_daily_professional_network_stock_share_of_numeric_mass,
            AVG(
                CASE
                    WHEN daily_numeric_mass.numeric_mass > 0
                    THEN daily_professional_stock.positive_gonette_business_accounts_stock
                         / daily_numeric_mass.numeric_mass
                    ELSE NULL
                END
            ) AS average_daily_gonette_business_accounts_stock_share_of_numeric_mass,
            AVG(
                CASE
                    WHEN daily_numeric_mass.numeric_mass > 0
                    THEN daily_professional_stock.positive_professional_total_stock
                         / daily_numeric_mass.numeric_mass
                    ELSE NULL
                END
            ) AS average_daily_professional_total_stock_share_of_numeric_mass
        FROM daily_user_stock
        JOIN daily_professional_stock
          ON daily_professional_stock.day = daily_user_stock.day
        JOIN daily_numeric_mass
          ON daily_numeric_mass.day = daily_user_stock.day
    """, (
        effective_start,
        effective_end,
        effective_start,
        effective_end,
        effective_start,
        effective_end,
    )).fetchone()

    average_positive_user_stock = _money2(
        row["average_positive_user_stock"]
    )
    average_positive_professional_network_stock = _money2(
        row["average_positive_professional_network_stock"]
    )
    average_positive_gonette_business_accounts_stock = _money2(
        row["average_positive_gonette_business_accounts_stock"]
    )
    average_positive_professional_total_stock = _money2(
        row["average_positive_professional_total_stock"]
    )
    average_numeric_mass = _money2(
        row["average_numeric_mass"]
    )

    return {
        "aligned_day_count": int(row["aligned_day_count"] or 0),
        "average_positive_user_stock": average_positive_user_stock,
        "average_positive_professional_network_stock": (
            average_positive_professional_network_stock
        ),
        "average_positive_gonette_business_accounts_stock": (
            average_positive_gonette_business_accounts_stock
        ),
        "average_positive_professional_total_stock": (
            average_positive_professional_total_stock
        ),
        "average_numeric_mass": average_numeric_mass,
        "average_user_stock_share_of_numeric_mass": _ratio(
                average_positive_user_stock,
                average_numeric_mass,
            ),
            "average_professional_network_stock_share_of_numeric_mass": _ratio(
                average_positive_professional_network_stock,
                average_numeric_mass,
            ),
            "average_gonette_business_accounts_stock_share_of_numeric_mass": _ratio(
                average_positive_gonette_business_accounts_stock,
                average_numeric_mass,
            ),
            "average_professional_total_stock_share_of_numeric_mass": _ratio(
                average_positive_professional_total_stock,
                average_numeric_mass,
            ),
        "average_professional_network_stock_share_of_numeric_mass": _ratio(
            average_positive_professional_network_stock,
            average_numeric_mass,
        ),
        "average_gonette_business_accounts_stock_share_of_numeric_mass": _ratio(
            average_positive_gonette_business_accounts_stock,
            average_numeric_mass,
        ),
        "average_professional_total_stock_share_of_numeric_mass": _ratio(
            average_positive_professional_total_stock,
            average_numeric_mass,
        ),
        "average_daily_user_stock_share_of_numeric_mass": (
            round(float(row["average_daily_user_stock_share_of_numeric_mass"] or 0.0), 6)
            if row["average_daily_user_stock_share_of_numeric_mass"] is not None
            else None
        ),
        "average_daily_professional_network_stock_share_of_numeric_mass": (
            round(
                float(
                    row[
                        "average_daily_professional_network_stock_share_of_numeric_mass"
                    ] or 0.0
                ),
                6,
            )
            if row[
                "average_daily_professional_network_stock_share_of_numeric_mass"
            ] is not None
            else None
        ),
        "average_daily_gonette_business_accounts_stock_share_of_numeric_mass": (
            round(
                float(
                    row[
                        "average_daily_gonette_business_accounts_stock_share_of_numeric_mass"
                    ] or 0.0
                ),
                6,
            )
            if row[
                "average_daily_gonette_business_accounts_stock_share_of_numeric_mass"
            ] is not None
            else None
        ),
        "average_daily_professional_total_stock_share_of_numeric_mass": (
            round(
                float(
                    row[
                        "average_daily_professional_total_stock_share_of_numeric_mass"
                    ] or 0.0
                ),
                6,
            )
            if row[
                "average_daily_professional_total_stock_share_of_numeric_mass"
            ] is not None
            else None
        ),
    }


def _fetch_closing_snapshot(cur, snapshot_day: str) -> dict | None:
    row = cur.execute("""
        SELECT
            COUNT(*) AS users_total,
            SUM(CASE WHEN balance > 0 THEN 1 ELSE 0 END) AS users_positive,
            SUM(CASE WHEN balance = 0 THEN 1 ELSE 0 END) AS users_zero,
            SUM(CASE WHEN balance < 0 THEN 1 ELSE 0 END) AS users_negative,
            COALESCE(
                SUM(CASE WHEN balance > 0 THEN balance ELSE 0.0 END),
                0.0
            ) AS positive_user_stock,
            COALESCE(SUM(balance), 0.0) AS net_user_stock,
            AVG(CASE WHEN balance > 0 THEN balance END) AS average_positive_balance,
            MAX(balance) AS max_balance
        FROM cyclos_individual_daily_balances
        WHERE balance_date = ?
    """, (snapshot_day,)).fetchone()

    professional_row = cur.execute("""
        SELECT
            SUM(
                CASE
                    WHEN professional_ref NOT IN ('P0000', 'P9999')
                    THEN 1
                    ELSE 0
                END
            ) AS professional_network_accounts_total,
            SUM(
                CASE
                    WHEN professional_ref NOT IN ('P0000', 'P9999')
                     AND balance > 0
                    THEN 1
                    ELSE 0
                END
            ) AS professional_network_accounts_positive,
            SUM(
                CASE
                    WHEN professional_ref NOT IN ('P0000', 'P9999')
                     AND balance = 0
                    THEN 1
                    ELSE 0
                END
            ) AS professional_network_accounts_zero,
            SUM(
                CASE
                    WHEN professional_ref NOT IN ('P0000', 'P9999')
                     AND balance < 0
                    THEN 1
                    ELSE 0
                END
            ) AS professional_network_accounts_negative,
            SUM(
                CASE
                    WHEN professional_ref IN ('P0000', 'P9999')
                    THEN 1
                    ELSE 0
                END
            ) AS gonette_business_accounts_total,
            SUM(
                CASE
                    WHEN professional_ref IN ('P0000', 'P9999')
                     AND balance > 0
                    THEN 1
                    ELSE 0
                END
            ) AS gonette_business_accounts_positive,
            SUM(
                CASE
                    WHEN professional_ref IN ('P0000', 'P9999')
                     AND balance = 0
                    THEN 1
                    ELSE 0
                END
            ) AS gonette_business_accounts_zero,
            SUM(
                CASE
                    WHEN professional_ref IN ('P0000', 'P9999')
                     AND balance < 0
                    THEN 1
                    ELSE 0
                END
            ) AS gonette_business_accounts_negative,
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
        WHERE balance_date = ?
    """, (snapshot_day,)).fetchone()

    monetary_row = cur.execute("""
        SELECT
            gonettes_num_circulation AS numeric_mass
        FROM odoo_monetary_indicators_daily
        WHERE snapshot_date = ?
    """, (snapshot_day,)).fetchone()

    if row is None:
        return None

    positive_user_stock = _money2(row["positive_user_stock"])
    positive_professional_network_stock = _money2(
        professional_row["positive_professional_network_stock"]
    )
    positive_gonette_business_accounts_stock = _money2(
        professional_row["positive_gonette_business_accounts_stock"]
    )
    positive_professional_total_stock = _money2(
        professional_row["positive_professional_total_stock"]
    )
    numeric_mass = (
        _money2(monetary_row["numeric_mass"])
        if monetary_row is not None
        else None
    )

    return {
        "snapshot_date": snapshot_day,
        "users_total": int(row["users_total"] or 0),
        "users_positive": int(row["users_positive"] or 0),
        "users_zero": int(row["users_zero"] or 0),
        "users_negative": int(row["users_negative"] or 0),
        "positive_user_stock": positive_user_stock,
        "net_user_stock": _money2(row["net_user_stock"]),
        "average_positive_balance": (
            _money2(row["average_positive_balance"])
            if row["average_positive_balance"] is not None
            else None
        ),
        "max_balance": _money2(row["max_balance"]),
        "professional_network_accounts_total": int(
            professional_row["professional_network_accounts_total"] or 0
        ),
        "professional_network_accounts_positive": int(
            professional_row["professional_network_accounts_positive"] or 0
        ),
        "professional_network_accounts_zero": int(
            professional_row["professional_network_accounts_zero"] or 0
        ),
        "professional_network_accounts_negative": int(
            professional_row["professional_network_accounts_negative"] or 0
        ),
        "gonette_business_accounts_total": int(
            professional_row["gonette_business_accounts_total"] or 0
        ),
        "gonette_business_accounts_positive": int(
            professional_row["gonette_business_accounts_positive"] or 0
        ),
        "gonette_business_accounts_zero": int(
            professional_row["gonette_business_accounts_zero"] or 0
        ),
        "gonette_business_accounts_negative": int(
            professional_row["gonette_business_accounts_negative"] or 0
        ),
        "positive_professional_network_stock": positive_professional_network_stock,
        "positive_gonette_business_accounts_stock": (
            positive_gonette_business_accounts_stock
        ),
        "positive_professional_total_stock": positive_professional_total_stock,
        "numeric_mass": numeric_mass,
        "user_stock_share_of_numeric_mass": _ratio(
            positive_user_stock,
            numeric_mass,
        ),
        "professional_network_stock_share_of_numeric_mass": _ratio(
            positive_professional_network_stock,
            numeric_mass,
        ),
        "gonette_business_accounts_stock_share_of_numeric_mass": _ratio(
            positive_gonette_business_accounts_stock,
            numeric_mass,
        ),
        "professional_total_stock_share_of_numeric_mass": _ratio(
            positive_professional_total_stock,
            numeric_mass,
        ),
    }


def _load_user_activity_days(cur, max_day: str) -> dict[str, list[str]]:
    rows = cur.execute("""
        SELECT actor, tx_day
        FROM (
            SELECT
                from_label AS actor,
                substr(date, 1, 10) AS tx_day
            FROM transactions
            WHERE substr(date, 1, 10) <= ?
              AND from_label LIKE 'U_%'

            UNION ALL

            SELECT
                to_label AS actor,
                substr(date, 1, 10) AS tx_day
            FROM transactions
            WHERE substr(date, 1, 10) <= ?
              AND to_label LIKE 'U_%'
        )
        WHERE actor IS NOT NULL
          AND actor != ''
          AND tx_day IS NOT NULL
          AND tx_day != ''
        ORDER BY actor ASC, tx_day ASC
    """, (
        max_day,
        max_day,
    )).fetchall()

    activity_days = defaultdict(list)

    for row in rows:
        actor = str(row["actor"] or "").strip()
        tx_day = str(row["tx_day"] or "").strip()

        if not actor or not tx_day:
            continue

        bucket = activity_days[actor]
        if not bucket or bucket[-1] != tx_day:
            bucket.append(tx_day)

    return dict(activity_days)


def _last_activity_on_or_before(
    activity_days: dict[str, list[str]],
    pseudonym: str,
    reference_day: str,
) -> str | None:
    days = activity_days.get(pseudonym) or []
    if not days:
        return None

    index = bisect_right(days, reference_day) - 1
    if index < 0:
        return None

    return days[index]


def _dormancy_bucket_key(reference_day: str, last_activity_day: str | None) -> str:
    if last_activity_day is None:
        return "no_activity"

    days_since = (
        _date_value(reference_day) - _date_value(last_activity_day)
    ).days

    if days_since <= 30:
        return "active_30"
    if days_since <= 90:
        return "dormant_31_90"
    if days_since <= 180:
        return "dormant_91_180"
    return "dormant_gt_180"


def _compute_dormancy_snapshot(
    cur,
    *,
    reference_day: str,
    activity_days: dict[str, list[str]],
) -> dict:
    rows = cur.execute("""
        SELECT
            pseudonym,
            balance
        FROM cyclos_individual_daily_balances
        WHERE balance_date = ?
          AND balance > 0
        ORDER BY pseudonym ASC
    """, (reference_day,)).fetchall()

    raw = {
        item["key"]: {
            "key": item["key"],
            "label": item["label"],
            "user_count": 0,
            "positive_user_stock": 0.0,
        }
        for item in DORMANCY_BUCKET_DEFINITIONS
    }

    total_positive_stock = 0.0

    for row in rows:
        pseudonym = str(row["pseudonym"] or "").strip()
        balance = float(row["balance"] or 0.0)

        if not pseudonym or balance <= 0:
            continue

        total_positive_stock += balance

        last_activity_day = _last_activity_on_or_before(
            activity_days,
            pseudonym,
            reference_day,
        )
        bucket_key = _dormancy_bucket_key(
            reference_day,
            last_activity_day,
        )

        raw[bucket_key]["user_count"] += 1
        raw[bucket_key]["positive_user_stock"] += balance

    total_positive_stock = _money2(total_positive_stock)

    buckets = []

    for definition in DORMANCY_BUCKET_DEFINITIONS:
        item = raw[definition["key"]]
        positive_user_stock = _money2(item["positive_user_stock"])

        buckets.append({
            "key": item["key"],
            "label": item["label"],
            "user_count": int(item["user_count"] or 0),
            "positive_user_stock": positive_user_stock,
            "stock_share_of_positive_user_stock": _ratio(
                positive_user_stock,
                total_positive_stock,
            ),
        })

    return {
        "reference_date": reference_day,
        "positive_user_stock": total_positive_stock,
        "buckets": buckets,
    }


def _compute_economic_up_flows(rows: list[dict]) -> dict:
    transaction_count = 0
    volume = 0.0

    for row in rows:
        classification = _classify_analytical_transaction(row)

        if not classification["is_activity"]:
            continue

        if _structural_flow_key(row) != "U→P":
            continue

        transaction_count += 1
        volume += float(row.get("amount") or 0.0)

    return {
        "economic_up_transaction_count": transaction_count,
        "economic_up_volume": _money2(volume),
    }


def _economic_up_flows_by_month(rows: list[dict]) -> dict[str, dict]:
    monthly = defaultdict(lambda: {
        "economic_up_transaction_count": 0,
        "economic_up_volume": 0.0,
    })

    for row in rows:
        classification = _classify_analytical_transaction(row)

        if not classification["is_activity"]:
            continue

        if _structural_flow_key(row) != "U→P":
            continue

        raw_date = str(row.get("date") or "")
        month_key = raw_date[:7]

        if len(month_key) != 7:
            continue

        bucket = monthly[month_key]
        bucket["economic_up_transaction_count"] += 1
        bucket["economic_up_volume"] += float(row.get("amount") or 0.0)

    return {
        month_key: {
            "economic_up_transaction_count": int(values["economic_up_transaction_count"]),
            "economic_up_volume": _money2(values["economic_up_volume"]),
        }
        for month_key, values in monthly.items()
    }


def _get_opening_balance_day(cur, effective_start: str) -> str | None:
    row = cur.execute("""
        SELECT MAX(balance_date) AS opening_balance_day
        FROM cyclos_individual_daily_balances
        WHERE balance_date < ?
    """, (effective_start,)).fetchone()

    if row is None:
        return None

    return row["opening_balance_day"]


def _compute_reactivation_metrics(
    cur,
    *,
    effective_start: str,
    effective_end: str,
    activity_days: dict[str, list[str]],
    period_transactions: list[dict],
) -> dict:
    opening_day = _get_opening_balance_day(cur, effective_start)

    if opening_day is None:
        return {
            "opening_balance_date": None,
            "dormant_gt_90_opening_user_count": None,
            "dormant_gt_90_opening_stock": None,
            "opening_positive_users_without_prior_activity": None,
            "reactivated_user_count": None,
            "reactivated_opening_stock": None,
            "reactivated_user_share_of_dormant_gt_90_opening_users": None,
            "reactivated_stock_share_of_dormant_gt_90_opening_stock": None,
            "economic_up_transaction_count_from_reactivated_users": None,
            "economic_up_volume_from_reactivated_users": None,
            "economic_up_volume_per_reactivated_opening_stock": None,
        }

    opening_rows = cur.execute("""
        SELECT
            pseudonym,
            balance
        FROM cyclos_individual_daily_balances
        WHERE balance_date = ?
          AND balance > 0
    """, (opening_day,)).fetchall()

    dormant_gt_90 = {}
    positive_without_prior_activity = 0

    for row in opening_rows:
        pseudonym = str(row["pseudonym"] or "").strip()
        balance = float(row["balance"] or 0.0)

        if not pseudonym or balance <= 0:
            continue

        last_activity_day = _last_activity_on_or_before(
            activity_days,
            pseudonym,
            opening_day,
        )

        if last_activity_day is None:
            positive_without_prior_activity += 1
            continue

        inactivity_days = (
            _date_value(opening_day) - _date_value(last_activity_day)
        ).days

        if inactivity_days > 90:
            dormant_gt_90[pseudonym] = balance

    dormant_opening_stock = _money2(sum(dormant_gt_90.values()))

    reactivated_users = set()

    for row in period_transactions:
        from_label = str(row.get("from_label") or "").strip()
        to_label = str(row.get("to_label") or "").strip()

        if from_label in dormant_gt_90:
            reactivated_users.add(from_label)

        if to_label in dormant_gt_90:
            reactivated_users.add(to_label)

    reactivated_opening_stock = _money2(
        sum(dormant_gt_90[user] for user in reactivated_users)
    )

    economic_up_transaction_count = 0
    economic_up_volume = 0.0

    for row in period_transactions:
        from_label = str(row.get("from_label") or "").strip()

        if from_label not in reactivated_users:
            continue

        classification = _classify_analytical_transaction(row)

        if not classification["is_activity"]:
            continue

        if _structural_flow_key(row) != "U→P":
            continue

        economic_up_transaction_count += 1
        economic_up_volume += float(row.get("amount") or 0.0)

    economic_up_volume = _money2(economic_up_volume)

    return {
        "opening_balance_date": opening_day,
        "dormant_gt_90_opening_user_count": len(dormant_gt_90),
        "dormant_gt_90_opening_stock": dormant_opening_stock,
        "opening_positive_users_without_prior_activity": positive_without_prior_activity,
        "reactivated_user_count": len(reactivated_users),
        "reactivated_opening_stock": reactivated_opening_stock,
        "reactivated_user_share_of_dormant_gt_90_opening_users": _ratio(
            len(reactivated_users),
            len(dormant_gt_90),
        ),
        "reactivated_stock_share_of_dormant_gt_90_opening_stock": _ratio(
            reactivated_opening_stock,
            dormant_opening_stock,
        ),
        "economic_up_transaction_count_from_reactivated_users": (
            economic_up_transaction_count
        ),
        "economic_up_volume_from_reactivated_users": economic_up_volume,
        "economic_up_volume_per_reactivated_opening_stock": _ratio(
            economic_up_volume,
            reactivated_opening_stock,
        ),
    }


def get_pilotage_holdings_summary(requested_start, requested_end) -> dict:
    conn = get_connection()
    cur = conn.cursor()

    try:
        period = _resolve_holdings_period(
            cur,
            requested_start,
            requested_end,
        )
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
            "holdings_reference": None,
            "flow_reference": None,
            "holdings_metrics": None,
        }

    effective_start = period["effective_start"]
    effective_end = period["effective_end"]

    averages = _fetch_aligned_period_averages(
        cur,
        effective_start,
        effective_end,
    )

    closing_snapshot = _fetch_closing_snapshot(
        cur,
        effective_end,
    )

    activity_days = _load_user_activity_days(cur, effective_end)

    dormancy = _compute_dormancy_snapshot(
        cur,
        reference_day=effective_end,
        activity_days=activity_days,
    )

    period_transactions = fetch_transactions(
        start=effective_start,
        end=effective_end,
        year=None,
    )

    economic_up_flows = _compute_economic_up_flows(
        period_transactions,
    )

    reactivation = _compute_reactivation_metrics(
        cur,
        effective_start=effective_start,
        effective_end=effective_end,
        activity_days=activity_days,
        period_transactions=period_transactions,
    )

    conn.close()

    average_user_stock = averages["average_positive_user_stock"]
    economic_up_volume = economic_up_flows["economic_up_volume"]
    mobilization_ratio = _ratio(
        economic_up_volume,
        average_user_stock,
    )

    return {
        "bounds": period["bounds"],
        "requested_period": {
            "start": period["requested_start"],
            "end": period["requested_end"],
        },
        "effective_period": {
            "start": effective_start,
            "end": effective_end,
        },
        "semantics": {
            "effective_period": (
                "La période est bornée sur l'intersection entre les soldes "
                "quotidiens particuliers et les stocks monétaires Odoo quotidiens."
            ),
            "average_positive_user_stock": (
                "Moyenne quotidienne du stock positif détenu par les particuliers "
                "sur les jours communs U × Odoo."
            ),
            "average_positive_professional_network_stock": (
                "Moyenne quotidienne du stock positif détenu par les professionnels "
                "du réseau, hors comptes entreprise Gonette P0000 et P9999, sur "
                "les jours communs U × P × Odoo."
            ),
            "average_positive_gonette_business_accounts_stock": (
                "Moyenne quotidienne du stock positif porté par les comptes entreprise "
                "de la Gonette P0000 et P9999, isolés du reste des professionnels."
            ),
            "professional_network_stock_share_of_numeric_mass": (
                "Rapport entre le stock positif moyen des professionnels du réseau "
                "et la masse numérique Odoo moyenne de la période."
            ),
            "user_stock_share_of_numeric_mass": (
                "Rapport entre le stock positif moyen des particuliers et la "
                "masse numérique Odoo moyenne de la période."
            ),
            "dormancy": (
                "La dormance repose sur l'absence de toute transaction impliquant "
                "le compte particulier jusqu'à la date de référence."
            ),
            "economic_up_volume": (
                "Le volume U→P correspond aux paiements économiques des particuliers "
                "vers les professionnels, selon la classification analytique MLCFlux."
            ),
            "individual_stock_mobilization_ratio": (
                "Volume économique U→P de la période divisé par le stock positif "
                "moyen détenu par les particuliers."
            ),
            "reactivation": (
                "Un compte réactivé était porteur d'un solde positif et dormant "
                "depuis plus de 90 jours à l'ouverture, puis a eu au moins une "
                "transaction durant la période."
            ),
        },
        "holdings_reference": {
            **averages,
            "closing_snapshot": closing_snapshot,
        },
        "flow_reference": economic_up_flows,
        "holdings_metrics": {
            "mobilization": {
                "individual_stock_mobilization_ratio": mobilization_ratio,
                "economic_up_volume_per_100_g_average_user_stock": (
                    _money2(mobilization_ratio * 100)
                    if mobilization_ratio is not None
                    else None
                ),
            },
            "dormancy": dormancy,
            "reactivation": reactivation,
        },
    }


def _fetch_monthly_aligned_rows(cur, effective_start: str, effective_end: str):
    return cur.execute("""
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
        ),
        aligned AS (
            SELECT
                daily_user_stock.day AS day,
                substr(daily_user_stock.day, 1, 7) AS month_key,
                CAST(substr(daily_user_stock.day, 1, 4) AS INTEGER) AS year,
                CAST(substr(daily_user_stock.day, 6, 2) AS INTEGER) AS month,
                daily_user_stock.positive_user_stock AS positive_user_stock,
                daily_professional_stock.positive_professional_network_stock
                    AS positive_professional_network_stock,
                daily_professional_stock.positive_gonette_business_accounts_stock
                    AS positive_gonette_business_accounts_stock,
                daily_professional_stock.positive_professional_total_stock
                    AS positive_professional_total_stock,
                daily_numeric_mass.numeric_mass AS numeric_mass
            FROM daily_user_stock
            JOIN daily_professional_stock
              ON daily_professional_stock.day = daily_user_stock.day
            JOIN daily_numeric_mass
              ON daily_numeric_mass.day = daily_user_stock.day
        )
        SELECT
            month_key,
            year,
            month,
            COUNT(*) AS aligned_day_count,
            AVG(positive_user_stock) AS average_positive_user_stock,
            AVG(
                positive_professional_network_stock
            ) AS average_positive_professional_network_stock,
            AVG(
                positive_gonette_business_accounts_stock
            ) AS average_positive_gonette_business_accounts_stock,
            AVG(
                positive_professional_total_stock
            ) AS average_positive_professional_total_stock,
            AVG(numeric_mass) AS average_numeric_mass,
            AVG(
                CASE
                    WHEN numeric_mass > 0
                    THEN positive_user_stock / numeric_mass
                    ELSE NULL
                END
            ) AS average_daily_user_stock_share_of_numeric_mass,
            AVG(
                CASE
                    WHEN numeric_mass > 0
                    THEN positive_professional_network_stock / numeric_mass
                    ELSE NULL
                END
            ) AS average_daily_professional_network_stock_share_of_numeric_mass,
            AVG(
                CASE
                    WHEN numeric_mass > 0
                    THEN positive_gonette_business_accounts_stock / numeric_mass
                    ELSE NULL
                END
            ) AS average_daily_gonette_business_accounts_stock_share_of_numeric_mass,
            AVG(
                CASE
                    WHEN numeric_mass > 0
                    THEN positive_professional_total_stock / numeric_mass
                    ELSE NULL
                END
            ) AS average_daily_professional_total_stock_share_of_numeric_mass,
            MAX(day) AS closing_snapshot_date
        FROM aligned
        GROUP BY month_key, year, month
        ORDER BY month_key ASC
    """, (
        effective_start,
        effective_end,
        effective_start,
        effective_end,
        effective_start,
        effective_end,
    )).fetchall()


def get_pilotage_holdings_timeseries(requested_start, requested_end) -> dict:
    conn = get_connection()
    cur = conn.cursor()

    try:
        period = _resolve_holdings_period(
            cur,
            requested_start,
            requested_end,
        )
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

    effective_start = period["effective_start"]
    effective_end = period["effective_end"]

    monthly_rows = _fetch_monthly_aligned_rows(
        cur,
        effective_start,
        effective_end,
    )

    activity_days = _load_user_activity_days(cur, effective_end)

    period_transactions = fetch_transactions(
        start=effective_start,
        end=effective_end,
        year=None,
    )

    up_by_month = _economic_up_flows_by_month(
        period_transactions,
    )

    items = []

    for row in monthly_rows:
        month_key = row["month_key"]
        average_positive_user_stock = _money2(
            row["average_positive_user_stock"]
        )
        average_positive_professional_network_stock = _money2(
            row["average_positive_professional_network_stock"]
        )
        average_positive_gonette_business_accounts_stock = _money2(
            row["average_positive_gonette_business_accounts_stock"]
        )
        average_positive_professional_total_stock = _money2(
            row["average_positive_professional_total_stock"]
        )
        average_numeric_mass = _money2(
            row["average_numeric_mass"]
        )

        up_flows = up_by_month.get(month_key) or {
            "economic_up_transaction_count": 0,
            "economic_up_volume": 0.0,
        }

        mobilization_ratio = _ratio(
            up_flows["economic_up_volume"],
            average_positive_user_stock,
        )

        closing_snapshot_date = row["closing_snapshot_date"]

        closing_snapshot = _fetch_closing_snapshot(
            cur,
            closing_snapshot_date,
        )

        dormancy = _compute_dormancy_snapshot(
            cur,
            reference_day=closing_snapshot_date,
            activity_days=activity_days,
        )

        items.append({
            "month_key": month_key,
            "year": int(row["year"]),
            "month": int(row["month"]),
            "aligned_day_count": int(row["aligned_day_count"] or 0),
            "average_positive_user_stock": average_positive_user_stock,
            "average_positive_professional_network_stock": (
                average_positive_professional_network_stock
            ),
            "average_positive_gonette_business_accounts_stock": (
                average_positive_gonette_business_accounts_stock
            ),
            "average_positive_professional_total_stock": (
                average_positive_professional_total_stock
            ),
            "average_numeric_mass": average_numeric_mass,
            "average_user_stock_share_of_numeric_mass": _ratio(
                average_positive_user_stock,
                average_numeric_mass,
            ),
            "average_professional_network_stock_share_of_numeric_mass": _ratio(
                average_positive_professional_network_stock,
                average_numeric_mass,
            ),
            "average_gonette_business_accounts_stock_share_of_numeric_mass": _ratio(
                average_positive_gonette_business_accounts_stock,
                average_numeric_mass,
            ),
            "average_professional_total_stock_share_of_numeric_mass": _ratio(
                average_positive_professional_total_stock,
                average_numeric_mass,
            ),
            "average_daily_user_stock_share_of_numeric_mass": (
                round(
                    float(row["average_daily_user_stock_share_of_numeric_mass"] or 0.0),
                    6,
                )
                if row["average_daily_user_stock_share_of_numeric_mass"] is not None
                else None
            ),
            "average_daily_professional_network_stock_share_of_numeric_mass": (
                round(
                    float(
                        row[
                            "average_daily_professional_network_stock_share_of_numeric_mass"
                        ] or 0.0
                    ),
                    6,
                )
                if row[
                    "average_daily_professional_network_stock_share_of_numeric_mass"
                ] is not None
                else None
            ),
            "average_daily_gonette_business_accounts_stock_share_of_numeric_mass": (
                round(
                    float(
                        row[
                            "average_daily_gonette_business_accounts_stock_share_of_numeric_mass"
                        ] or 0.0
                    ),
                    6,
                )
                if row[
                    "average_daily_gonette_business_accounts_stock_share_of_numeric_mass"
                ] is not None
                else None
            ),
            "average_daily_professional_total_stock_share_of_numeric_mass": (
                round(
                    float(
                        row[
                            "average_daily_professional_total_stock_share_of_numeric_mass"
                        ] or 0.0
                    ),
                    6,
                )
                if row[
                    "average_daily_professional_total_stock_share_of_numeric_mass"
                ] is not None
                else None
            ),
            "economic_up_transaction_count": int(
                up_flows["economic_up_transaction_count"] or 0
            ),
            "economic_up_volume": _money2(
                up_flows["economic_up_volume"]
            ),
            "individual_stock_mobilization_ratio": mobilization_ratio,
            "economic_up_volume_per_100_g_average_user_stock": (
                _money2(mobilization_ratio * 100)
                if mobilization_ratio is not None
                else None
            ),
            "closing_snapshot": closing_snapshot,
            "dormancy": dormancy,
        })

    conn.close()

    return {
        "bounds": period["bounds"],
        "requested_period": {
            "start": period["requested_start"],
            "end": period["requested_end"],
        },
        "effective_period": {
            "start": effective_start,
            "end": effective_end,
        },
        "semantics": {
            "monthly_averages": (
                "Les stocks U, les stocks P — professionnels du réseau et comptes "
                "entreprise Gonette — ainsi que la masse numérique Odoo sont moyennés "
                "sur les jours effectivement communs de chaque mois."
            ),
            "monthly_mobilization": (
                "Le volume U→P du mois est divisé par le stock U positif "
                "moyen de ce même mois."
            ),
            "monthly_dormancy": (
                "La structure actif / dormant est évaluée sur la dernière "
                "date commune disponible dans chaque mois."
            ),
            "partial_months": (
                "Le premier et le dernier mois peuvent être partiels lorsque "
                "la période sélectionnée ne couvre pas un mois complet."
            ),
        },
        "items": items,
    }
