from __future__ import annotations

import math
import re
import sqlite3
import statistics
from datetime import date
from typing import Any

from server.database import DB_PATH


OPERATOR_ACCOUNT_REFS = {"P0000", "P9999"}
DEFAULT_NETWORK_LIMIT = 18
MAX_NETWORK_LIMIT = 40

PROFESSIONAL_REF_RE = re.compile(r"^P\d{4}$")

WEEKDAY_LABELS_MONDAY_FIRST = [
    "Lundi",
    "Mardi",
    "Mercredi",
    "Jeudi",
    "Vendredi",
    "Samedi",
    "Dimanche",
]


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_professional_ref(value: str | None) -> str:
    ref = str(value or "").strip().upper()
    if not PROFESSIONAL_REF_RE.match(ref):
        raise ValueError(f"Référence professionnelle invalide : {value!r}")
    return ref


def _parse_iso_date(value: str | None, field_name: str) -> str | None:
    text = _clean_text(value)
    if not text:
        return None

    try:
        return date.fromisoformat(text).isoformat()
    except ValueError as exc:
        raise ValueError(
            f"Date invalide pour {field_name}: {value!r}. Format attendu : YYYY-MM-DD."
        ) from exc


def _resolve_effective_period(
    conn: sqlite3.Connection,
    professional_ref: str,
    requested_start: str | None,
    requested_end: str | None,
) -> dict[str, str | None]:
    start = _parse_iso_date(requested_start, "start")
    end = _parse_iso_date(requested_end, "end")

    bounds_row = conn.execute(
        """
        SELECT
          MIN(balance_date) AS min_balance_date,
          MAX(balance_date) AS max_balance_date
        FROM cyclos_professional_daily_balances
        WHERE professional_ref = ?
        """,
        (professional_ref,),
    ).fetchone()

    min_balance_date = bounds_row["min_balance_date"] if bounds_row else None
    max_balance_date = bounds_row["max_balance_date"] if bounds_row else None

    transaction_bounds_row = conn.execute(
        """
        SELECT
          MIN(SUBSTR(date, 1, 10)) AS min_transaction_date,
          MAX(SUBSTR(date, 1, 10)) AS max_transaction_date
        FROM transactions
        WHERE SUBSTR(TRIM(from_label), 1, 5) = ?
           OR SUBSTR(TRIM(to_label), 1, 5) = ?
        """,
        (professional_ref, professional_ref),
    ).fetchone()

    min_transaction_date = (
        transaction_bounds_row["min_transaction_date"]
        if transaction_bounds_row
        else None
    )
    max_transaction_date = (
        transaction_bounds_row["max_transaction_date"]
        if transaction_bounds_row
        else None
    )

    default_start = min_balance_date or min_transaction_date
    default_end = max_balance_date or max_transaction_date

    effective_start = start or default_start
    effective_end = end or default_end

    if effective_start and effective_end and effective_start > effective_end:
        raise ValueError(
            f"Période invalide : start={effective_start} est postérieur à end={effective_end}."
        )

    return {
        "requested_start": start,
        "requested_end": end,
        "effective_start": effective_start,
        "effective_end": effective_end,
        "balance_min_date": min_balance_date,
        "balance_max_date": max_balance_date,
        "transaction_min_date": min_transaction_date,
        "transaction_max_date": max_transaction_date,
    }


def _professional_identity(
    conn: sqlite3.Connection,
    professional_ref: str,
) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT
          professional_ref,
          odoo_name,
          industry_name,
          detailed_activity,
          zip,
          city,
          cyclos_zip,
          cyclos_city
        FROM odoo_professional_enrichment
        WHERE professional_ref = ?
        """,
        (professional_ref,),
    ).fetchone()

    if not row:
        return {
            "professional_ref": professional_ref,
            "name": professional_ref,
            "industry_name": None,
            "detailed_activity": None,
            "zip": None,
            "city": None,
        }

    city = _clean_text(row["cyclos_city"]) or _clean_text(row["city"])
    zip_code = _clean_text(row["cyclos_zip"]) or _clean_text(row["zip"])

    return {
        "professional_ref": professional_ref,
        "name": _clean_text(row["odoo_name"]) or professional_ref,
        "industry_name": _clean_text(row["industry_name"]),
        "detailed_activity": _clean_text(row["detailed_activity"]),
        "zip": zip_code,
        "city": city,
    }


def _label_name_fallback(raw_label: str | None, professional_ref: str) -> str:
    label = str(raw_label or "").strip()
    prefix_dash = f"{professional_ref} - "
    prefix_long_dash = f"{professional_ref} — "

    if label.startswith(prefix_dash):
        return label[len(prefix_dash):].strip() or professional_ref
    if label.startswith(prefix_long_dash):
        return label[len(prefix_long_dash):].strip() or professional_ref

    return label or professional_ref


def _b2b_direction_rows(
    conn: sqlite3.Connection,
    *,
    professional_ref: str,
    start: str | None,
    end: str | None,
    direction: str,
) -> list[dict[str, Any]]:
    if direction == "inbound":
        counterparty_expr = "SUBSTR(TRIM(t.from_label), 1, 5)"
        center_expr = "SUBSTR(TRIM(t.to_label), 1, 5)"
        raw_label_expr = "MAX(t.from_label)"
    elif direction == "outbound":
        counterparty_expr = "SUBSTR(TRIM(t.to_label), 1, 5)"
        center_expr = "SUBSTR(TRIM(t.from_label), 1, 5)"
        raw_label_expr = "MAX(t.to_label)"
    else:
        raise ValueError(f"Direction B2B inconnue : {direction!r}")

    where_parts = [
        f"{center_expr} = ?",
        f"{counterparty_expr} GLOB 'P[0-9][0-9][0-9][0-9]'",
        f"{counterparty_expr} <> ?",
        f"{counterparty_expr} NOT IN ('P0000', 'P9999')",
    ]
    params: list[Any] = [professional_ref, professional_ref]

    if start:
        where_parts.append("SUBSTR(t.date, 1, 10) >= ?")
        params.append(start)

    if end:
        where_parts.append("SUBSTR(t.date, 1, 10) <= ?")
        params.append(end)

    sql = f"""
        WITH grouped AS (
          SELECT
            {counterparty_expr} AS counterparty_ref,
            {raw_label_expr} AS raw_label,
            COUNT(*) AS tx_count,
            COALESCE(SUM(t.amount), 0) AS volume,
            MIN(SUBSTR(t.date, 1, 10)) AS first_date,
            MAX(SUBSTR(t.date, 1, 10)) AS last_date
          FROM transactions t
          WHERE {" AND ".join(where_parts)}
          GROUP BY {counterparty_expr}
        )
        SELECT
          g.counterparty_ref,
          g.raw_label,
          g.tx_count,
          g.volume,
          g.first_date,
          g.last_date,
          e.odoo_name,
          e.industry_name,
          e.detailed_activity,
          e.zip,
          e.city,
          e.cyclos_zip,
          e.cyclos_city
        FROM grouped g
        LEFT JOIN odoo_professional_enrichment e
          ON e.professional_ref = g.counterparty_ref
        ORDER BY g.volume DESC, g.tx_count DESC, g.counterparty_ref ASC
    """

    rows = conn.execute(sql, params).fetchall()

    items: list[dict[str, Any]] = []

    for row in rows:
        counterparty_ref = row["counterparty_ref"]
        city = _clean_text(row["cyclos_city"]) or _clean_text(row["city"])
        zip_code = _clean_text(row["cyclos_zip"]) or _clean_text(row["zip"])
        odoo_name = _clean_text(row["odoo_name"])

        items.append(
            {
                "professional_ref": counterparty_ref,
                "name": odoo_name
                or _label_name_fallback(row["raw_label"], counterparty_ref),
                "industry_name": _clean_text(row["industry_name"]),
                "detailed_activity": _clean_text(row["detailed_activity"]),
                "zip": zip_code,
                "city": city,
                "tx_count": _safe_int(row["tx_count"]),
                "volume": _safe_float(row["volume"]),
                "first_date": row["first_date"],
                "last_date": row["last_date"],
            }
        )

    return items


def _operator_flow_summary(
    conn: sqlite3.Connection,
    *,
    professional_ref: str,
    start: str | None,
    end: str | None,
    direction: str,
) -> dict[str, Any]:
    if direction == "inbound":
        counterparty_expr = "SUBSTR(TRIM(from_label), 1, 5)"
        center_expr = "SUBSTR(TRIM(to_label), 1, 5)"
    elif direction == "outbound":
        counterparty_expr = "SUBSTR(TRIM(to_label), 1, 5)"
        center_expr = "SUBSTR(TRIM(from_label), 1, 5)"
    else:
        raise ValueError(f"Direction opérateur inconnue : {direction!r}")

    where_parts = [
        f"{center_expr} = ?",
        f"{counterparty_expr} IN ('P0000', 'P9999')",
    ]
    params: list[Any] = [professional_ref]

    if start:
        where_parts.append("SUBSTR(date, 1, 10) >= ?")
        params.append(start)

    if end:
        where_parts.append("SUBSTR(date, 1, 10) <= ?")
        params.append(end)

    row = conn.execute(
        f"""
        SELECT
          COUNT(*) AS tx_count,
          COALESCE(SUM(amount), 0) AS volume,
          COUNT(DISTINCT {counterparty_expr}) AS account_count
        FROM transactions
        WHERE {" AND ".join(where_parts)}
        """,
        params,
    ).fetchone()

    return {
        "tx_count": _safe_int(row["tx_count"] if row else 0),
        "volume": _safe_float(row["volume"] if row else 0.0),
        "account_count": _safe_int(row["account_count"] if row else 0),
    }


def _individual_payer_summary(
    conn: sqlite3.Connection,
    *,
    professional_ref: str,
    start: str | None,
    end: str | None,
) -> dict[str, Any]:
    where_parts = [
        "SUBSTR(TRIM(to_label), 1, 5) = ?",
        """(
          SUBSTR(TRIM(from_label), 1, 2) = 'U_'
          OR SUBSTR(TRIM(from_label), 1, 3) = 'UD_'
        )""",
    ]
    params: list[Any] = [professional_ref]

    if start:
        where_parts.append("SUBSTR(date, 1, 10) >= ?")
        params.append(start)

    if end:
        where_parts.append("SUBSTR(date, 1, 10) <= ?")
        params.append(end)

    row = conn.execute(
        f"""
        SELECT
          COUNT(DISTINCT TRIM(from_label)) AS distinct_payer_count,
          COUNT(*) AS tx_count,
          COALESCE(SUM(amount), 0) AS volume
        FROM transactions
        WHERE {" AND ".join(where_parts)}
        """,
        params,
    ).fetchone()

    distinct_payer_count = _safe_int(
        row["distinct_payer_count"] if row else 0
    )
    tx_count = _safe_int(row["tx_count"] if row else 0)
    volume = _safe_float(row["volume"] if row else 0.0)

    average_transaction_amount = (
        volume / tx_count
        if tx_count > 0
        else 0.0
    )

    average_volume_per_payer = (
        volume / distinct_payer_count
        if distinct_payer_count > 0
        else 0.0
    )

    return {
        "distinct_payer_count": distinct_payer_count,
        "tx_count": tx_count,
        "volume": volume,
        "average_transaction_amount": average_transaction_amount,
        "average_volume_per_payer": average_volume_per_payer,
    }


def _build_b2b_network(
    conn: sqlite3.Connection,
    *,
    professional_ref: str,
    start: str | None,
    end: str | None,
    network_limit: int,
) -> dict[str, Any]:
    center = _professional_identity(conn, professional_ref)

    inbound_all = _b2b_direction_rows(
        conn,
        professional_ref=professional_ref,
        start=start,
        end=end,
        direction="inbound",
    )
    outbound_all = _b2b_direction_rows(
        conn,
        professional_ref=professional_ref,
        start=start,
        end=end,
        direction="outbound",
    )

    inbound_refs = {item["professional_ref"] for item in inbound_all}
    outbound_refs = {item["professional_ref"] for item in outbound_all}
    reciprocal_refs = inbound_refs & outbound_refs

    individual_payers = _individual_payer_summary(
        conn,
        professional_ref=professional_ref,
        start=start,
        end=end,
    )

    def enrich_items(items: list[dict[str, Any]], direction: str) -> list[dict[str, Any]]:
        enriched = []
        for item in items[:network_limit]:
            enriched.append(
                {
                    **item,
                    "direction": direction,
                    "reciprocal": item["professional_ref"] in reciprocal_refs,
                }
            )
        return enriched

    inbound_items = enrich_items(inbound_all, "inbound")
    outbound_items = enrich_items(outbound_all, "outbound")

    inbound_summary = {
        "counterparty_count": len(inbound_all),
        "displayed_counterparty_count": len(inbound_items),
        "tx_count": sum(item["tx_count"] for item in inbound_all),
        "volume": sum(item["volume"] for item in inbound_all),
    }

    outbound_summary = {
        "counterparty_count": len(outbound_all),
        "displayed_counterparty_count": len(outbound_items),
        "tx_count": sum(item["tx_count"] for item in outbound_all),
        "volume": sum(item["volume"] for item in outbound_all),
    }

    nodes_by_ref: dict[str, dict[str, Any]] = {
        professional_ref: {
            "id": professional_ref,
            "professional_ref": professional_ref,
            "name": center["name"],
            "industry_name": center.get("industry_name"),
            "city": center.get("city"),
            "zip": center.get("zip"),
            "role": "center",
        }
    }

    links: list[dict[str, Any]] = []

    for item in inbound_items:
        ref = item["professional_ref"]
        nodes_by_ref.setdefault(
            ref,
            {
                "id": ref,
                "professional_ref": ref,
                "name": item["name"],
                "industry_name": item.get("industry_name"),
                "city": item.get("city"),
                "zip": item.get("zip"),
                "role": "counterparty",
                "directions": [],
                "reciprocal": item["reciprocal"],
            },
        )
        if "inbound" not in nodes_by_ref[ref].setdefault("directions", []):
            nodes_by_ref[ref]["directions"].append("inbound")

        links.append(
            {
                "source": ref,
                "target": professional_ref,
                "direction": "inbound",
                "tx_count": item["tx_count"],
                "volume": item["volume"],
                "reciprocal": item["reciprocal"],
            }
        )

    for item in outbound_items:
        ref = item["professional_ref"]
        nodes_by_ref.setdefault(
            ref,
            {
                "id": ref,
                "professional_ref": ref,
                "name": item["name"],
                "industry_name": item.get("industry_name"),
                "city": item.get("city"),
                "zip": item.get("zip"),
                "role": "counterparty",
                "directions": [],
                "reciprocal": item["reciprocal"],
            },
        )
        if "outbound" not in nodes_by_ref[ref].setdefault("directions", []):
            nodes_by_ref[ref]["directions"].append("outbound")

        links.append(
            {
                "source": professional_ref,
                "target": ref,
                "direction": "outbound",
                "tx_count": item["tx_count"],
                "volume": item["volume"],
                "reciprocal": item["reciprocal"],
            }
        )

    if individual_payers["distinct_payer_count"] > 0:
        nodes_by_ref["INDIVIDUAL_PAYERS"] = {
            "id": "INDIVIDUAL_PAYERS",
            "professional_ref": None,
            "name": "Particuliers payeurs",
            "industry_name": None,
            "city": None,
            "zip": None,
            "role": "individual_payers",
            "distinct_payer_count": individual_payers["distinct_payer_count"],
            "tx_count": individual_payers["tx_count"],
            "volume": individual_payers["volume"],
            "average_transaction_amount": individual_payers["average_transaction_amount"],
            "average_volume_per_payer": individual_payers["average_volume_per_payer"],
        }

        links.append(
            {
                "source": "INDIVIDUAL_PAYERS",
                "target": professional_ref,
                "direction": "individual_inbound",
                "tx_count": individual_payers["tx_count"],
                "volume": individual_payers["volume"],
                "reciprocal": False,
            }
        )

    excluded_operator_accounts = {
        "inbound": _operator_flow_summary(
            conn,
            professional_ref=professional_ref,
            start=start,
            end=end,
            direction="inbound",
        ),
        "outbound": _operator_flow_summary(
            conn,
            professional_ref=professional_ref,
            start=start,
            end=end,
            direction="outbound",
        ),
    }

    return {
        "center": center,
        "network_limit": network_limit,
        "operator_accounts_excluded": True,
        "excluded_operator_accounts": excluded_operator_accounts,
        "summary": {
            "inbound_counterparty_count": inbound_summary["counterparty_count"],
            "outbound_counterparty_count": outbound_summary["counterparty_count"],
            "reciprocal_counterparty_count": len(reciprocal_refs),
            "inbound_volume": inbound_summary["volume"],
            "outbound_volume": outbound_summary["volume"],
            "inbound_tx_count": inbound_summary["tx_count"],
            "outbound_tx_count": outbound_summary["tx_count"],
            "individual_payer_count": individual_payers["distinct_payer_count"],
            "individual_payer_tx_count": individual_payers["tx_count"],
            "individual_payer_volume": individual_payers["volume"],
        },
        "individual_payers": individual_payers,
        "inbound": {
            "summary": inbound_summary,
            "items": inbound_items,
        },
        "outbound": {
            "summary": outbound_summary,
            "items": outbound_items,
        },
        "nodes": list(nodes_by_ref.values()),
        "links": links,
    }


def _build_balance_timeseries(
    conn: sqlite3.Connection,
    *,
    professional_ref: str,
    start: str | None,
    end: str | None,
) -> dict[str, Any]:
    where_parts = ["professional_ref = ?"]
    params: list[Any] = [professional_ref]

    if start:
        where_parts.append("balance_date >= ?")
        params.append(start)

    if end:
        where_parts.append("balance_date <= ?")
        params.append(end)

    rows = conn.execute(
        f"""
        SELECT
          balance_date,
          balance
        FROM cyclos_professional_daily_balances
        WHERE {" AND ".join(where_parts)}
        ORDER BY balance_date ASC
        """,
        params,
    ).fetchall()

    items = [
        {
            "date": row["balance_date"],
            "balance": _safe_float(row["balance"]),
        }
        for row in rows
    ]

    balances = [item["balance"] for item in items]

    opening_balance = balances[0] if balances else None
    closing_balance = balances[-1] if balances else None
    balance_change = (
        closing_balance - opening_balance
        if opening_balance is not None and closing_balance is not None
        else None
    )

    return {
        "summary": {
            "point_count": len(items),
            "opening_date": items[0]["date"] if items else None,
            "closing_date": items[-1]["date"] if items else None,
            "opening_balance": opening_balance,
            "closing_balance": closing_balance,
            "balance_change": balance_change,
            "min_balance": min(balances) if balances else None,
            "max_balance": max(balances) if balances else None,
        },
        "items": items,
    }


def _build_individual_payment_rhythm(
    conn: sqlite3.Connection,
    *,
    professional_ref: str,
    start: str | None,
    end: str | None,
) -> dict[str, Any]:
    where_parts = [
        "SUBSTR(TRIM(to_label), 1, 5) = ?",
        """(
          SUBSTR(TRIM(from_label), 1, 2) = 'U_'
          OR SUBSTR(TRIM(from_label), 1, 3) = 'UD_'
        )""",
    ]
    params: list[Any] = [professional_ref]

    if start:
        where_parts.append("SUBSTR(date, 1, 10) >= ?")
        params.append(start)

    if end:
        where_parts.append("SUBSTR(date, 1, 10) <= ?")
        params.append(end)

    where_sql = " AND ".join(where_parts)

    total_row = conn.execute(
        f"""
        SELECT
          COUNT(*) AS tx_count,
          COALESCE(SUM(amount), 0) AS volume,
          COUNT(DISTINCT SUBSTR(date, 1, 10)) AS active_day_count
        FROM transactions
        WHERE {where_sql}
        """,
        params,
    ).fetchone()

    total_tx_count = _safe_int(total_row["tx_count"] if total_row else 0)
    total_volume = _safe_float(total_row["volume"] if total_row else 0.0)
    active_day_count = _safe_int(total_row["active_day_count"] if total_row else 0)

    grouped_rows = conn.execute(
        f"""
        SELECT
          CASE CAST(strftime('%w', SUBSTR(date, 1, 10)) AS INTEGER)
            WHEN 0 THEN 6
            ELSE CAST(strftime('%w', SUBSTR(date, 1, 10)) AS INTEGER) - 1
          END AS weekday_index,
          CAST(SUBSTR(date, 12, 2) AS INTEGER) AS hour,
          COUNT(*) AS tx_count,
          COALESCE(SUM(amount), 0) AS volume
        FROM transactions
        WHERE {where_sql}
          AND LENGTH(date) >= 13
          AND SUBSTR(date, 12, 2) GLOB '[0-2][0-9]'
          AND CAST(SUBSTR(date, 12, 2) AS INTEGER) BETWEEN 0 AND 23
        GROUP BY weekday_index, hour
        ORDER BY weekday_index ASC, hour ASC
        """,
        params,
    ).fetchall()

    weekday_totals = [
        {
            "weekday_index": index,
            "label": WEEKDAY_LABELS_MONDAY_FIRST[index],
            "tx_count": 0,
            "volume": 0.0,
        }
        for index in range(7)
    ]

    hour_totals = [
        {
            "hour": hour,
            "tx_count": 0,
            "volume": 0.0,
        }
        for hour in range(24)
    ]

    raw_cell_map: dict[tuple[int, int], dict[str, Any]] = {}

    for row in grouped_rows:
        weekday_index = _safe_int(row["weekday_index"], -1)
        hour = _safe_int(row["hour"], -1)
        tx_count = _safe_int(row["tx_count"])
        volume = _safe_float(row["volume"])

        if weekday_index < 0 or weekday_index > 6 or hour < 0 or hour > 23:
            continue

        raw_cell_map[(weekday_index, hour)] = {
            "weekday_index": weekday_index,
            "weekday_label": WEEKDAY_LABELS_MONDAY_FIRST[weekday_index],
            "hour": hour,
            "tx_count": tx_count,
            "volume": volume,
        }

        weekday_totals[weekday_index]["tx_count"] += tx_count
        weekday_totals[weekday_index]["volume"] += volume
        hour_totals[hour]["tx_count"] += tx_count
        hour_totals[hour]["volume"] += volume

    cells: list[dict[str, Any]] = []
    max_cell_tx_count = 0
    max_cell_volume = 0.0
    placed_tx_count = 0
    placed_volume = 0.0
    active_slot_count = 0

    for weekday_index in range(7):
        for hour in range(24):
            cell = raw_cell_map.get(
                (weekday_index, hour),
                {
                    "weekday_index": weekday_index,
                    "weekday_label": WEEKDAY_LABELS_MONDAY_FIRST[weekday_index],
                    "hour": hour,
                    "tx_count": 0,
                    "volume": 0.0,
                },
            )

            cells.append(cell)

            tx_count = _safe_int(cell["tx_count"])
            volume = _safe_float(cell["volume"])

            if tx_count > 0:
                active_slot_count += 1

            placed_tx_count += tx_count
            placed_volume += volume
            max_cell_tx_count = max(max_cell_tx_count, tx_count)
            max_cell_volume = max(max_cell_volume, volume)

    peak_cell = max(
        cells,
        key=lambda item: (
            _safe_int(item.get("tx_count")),
            _safe_float(item.get("volume")),
        ),
        default=None,
    )

    peak_weekday = max(
        weekday_totals,
        key=lambda item: (
            _safe_int(item.get("tx_count")),
            _safe_float(item.get("volume")),
        ),
        default=None,
    )

    peak_hour = max(
        hour_totals,
        key=lambda item: (
            _safe_int(item.get("tx_count")),
            _safe_float(item.get("volume")),
        ),
        default=None,
    )

    return {
        "summary": {
            "tx_count": total_tx_count,
            "volume": total_volume,
            "active_day_count": active_day_count,
            "active_slot_count": active_slot_count,
            "placed_tx_count": placed_tx_count,
            "placed_volume": placed_volume,
            "unplaced_tx_count": max(0, total_tx_count - placed_tx_count),
            "unplaced_volume": max(0.0, total_volume - placed_volume),
            "max_cell_tx_count": max_cell_tx_count,
            "max_cell_volume": max_cell_volume,
            "active_weekday_count": sum(
                1 for item in weekday_totals if _safe_int(item["tx_count"]) > 0
            ),
            "peak_cell": peak_cell,
            "peak_weekday": peak_weekday,
            "peak_hour": peak_hour,
        },
        "heatmap": {
            "weekdays": [
                {
                    "weekday_index": index,
                    "label": label,
                }
                for index, label in enumerate(WEEKDAY_LABELS_MONDAY_FIRST)
            ],
            "hours": list(range(24)),
            "cells": cells,
        },
        "weekday_items": weekday_totals,
        "hour_items": hour_totals,
    }


def _build_individual_customer_concentration(
    conn: sqlite3.Connection,
    *,
    professional_ref: str,
    start: str | None,
    end: str | None,
) -> dict[str, Any]:
    where_parts = [
        "SUBSTR(TRIM(to_label), 1, 5) = ?",
        """(
          SUBSTR(TRIM(from_label), 1, 2) = 'U_'
          OR SUBSTR(TRIM(from_label), 1, 3) = 'UD_'
        )""",
    ]
    params: list[Any] = [professional_ref]

    if start:
        where_parts.append("SUBSTR(date, 1, 10) >= ?")
        params.append(start)

    if end:
        where_parts.append("SUBSTR(date, 1, 10) <= ?")
        params.append(end)

    rows = conn.execute(
        f"""
        SELECT
          TRIM(from_label) AS payer_label,
          COUNT(*) AS tx_count,
          COALESCE(SUM(amount), 0) AS volume
        FROM transactions
        WHERE {" AND ".join(where_parts)}
        GROUP BY TRIM(from_label)
        ORDER BY volume DESC, tx_count DESC, payer_label ASC
        """,
        params,
    ).fetchall()

    payer_items = [
        {
            "payer_label": row["payer_label"],
            "tx_count": _safe_int(row["tx_count"]),
            "volume": _safe_float(row["volume"]),
        }
        for row in rows
    ]

    payer_count = len(payer_items)
    volumes_desc = [item["volume"] for item in payer_items]
    total_volume = sum(volumes_desc)
    tx_count = sum(item["tx_count"] for item in payer_items)

    if payer_count <= 0 or total_volume <= 0:
        return {
            "summary": {
                "payer_count": 0,
                "tx_count": 0,
                "total_volume": 0.0,
                "average_volume_per_payer": 0.0,
                "median_volume_per_payer": 0.0,
                "top_1_share_pct": 0.0,
                "top_3_share_pct": 0.0,
                "top_5_share_pct": 0.0,
                "effective_payer_count": 0.0,
                "concentration_ratio_effective_to_observed": 0.0,
                "hhi": 0.0,
            },
            "lorenz_points": [
                {"payer_share_pct": 0.0, "volume_share_pct": 0.0},
                {"payer_share_pct": 100.0, "volume_share_pct": 100.0},
            ],
        }

    def share_for_top(n: int) -> float:
        if n <= 0:
            return 0.0
        return 100.0 * sum(volumes_desc[:n]) / total_volume

    share_proportions = [
        volume / total_volume
        for volume in volumes_desc
        if volume > 0
    ]

    hhi = sum(share * share for share in share_proportions)
    effective_payer_count = (1.0 / hhi) if hhi > 0 else 0.0
    concentration_ratio = (
        effective_payer_count / payer_count
        if payer_count > 0
        else 0.0
    )

    volumes_asc = sorted(volumes_desc)
    cumulative_volumes = []
    cumulative = 0.0

    for volume in volumes_asc:
        cumulative += volume
        cumulative_volumes.append(cumulative)

    lorenz_points = [
        {"payer_share_pct": 0.0, "volume_share_pct": 0.0}
    ]

    # Échantillonnage à 2 points de pourcentage pour une courbe lisible
    # et un payload contenu.
    for payer_share_pct in range(2, 101, 2):
        payer_fraction = payer_share_pct / 100.0
        covered_payers = math.ceil(payer_fraction * payer_count)
        covered_payers = max(1, min(payer_count, covered_payers))

        cumulative_volume = cumulative_volumes[covered_payers - 1]
        volume_share_pct = 100.0 * cumulative_volume / total_volume

        lorenz_points.append({
            "payer_share_pct": float(payer_share_pct),
            "volume_share_pct": volume_share_pct,
        })

    if lorenz_points[-1]["payer_share_pct"] != 100.0:
        lorenz_points.append({
            "payer_share_pct": 100.0,
            "volume_share_pct": 100.0,
        })
    else:
        lorenz_points[-1]["volume_share_pct"] = 100.0

    return {
        "summary": {
            "payer_count": payer_count,
            "tx_count": tx_count,
            "total_volume": total_volume,
            "average_volume_per_payer": total_volume / payer_count,
            "median_volume_per_payer": statistics.median(volumes_desc),
            "top_1_share_pct": share_for_top(1),
            "top_3_share_pct": share_for_top(3),
            "top_5_share_pct": share_for_top(5),
            "effective_payer_count": effective_payer_count,
            "concentration_ratio_effective_to_observed": concentration_ratio,
            "hhi": hhi,
        },
        "lorenz_points": lorenz_points,
    }


def _build_individual_customer_loyalty(
    conn: sqlite3.Connection,
    *,
    professional_ref: str,
    start: str | None,
    end: str | None,
) -> dict[str, Any]:
    period_where_parts = [
        "SUBSTR(TRIM(to_label), 1, 5) = ?",
        """(
          SUBSTR(TRIM(from_label), 1, 2) = 'U_'
          OR SUBSTR(TRIM(from_label), 1, 3) = 'UD_'
        )""",
    ]
    period_params: list[Any] = [professional_ref]

    if start:
        period_where_parts.append("SUBSTR(date, 1, 10) >= ?")
        period_params.append(start)

    if end:
        period_where_parts.append("SUBSTR(date, 1, 10) <= ?")
        period_params.append(end)

    period_rows = conn.execute(
        f"""
        SELECT
          TRIM(from_label) AS payer_label,
          COUNT(*) AS tx_count,
          COALESCE(SUM(amount), 0) AS volume,
          MIN(SUBSTR(date, 1, 10)) AS first_payment_date,
          MAX(SUBSTR(date, 1, 10)) AS last_payment_date
        FROM transactions
        WHERE {" AND ".join(period_where_parts)}
        GROUP BY TRIM(from_label)
        ORDER BY volume DESC, tx_count DESC, payer_label ASC
        """,
        period_params,
    ).fetchall()

    prior_payers: set[str] = set()

    if start:
        prior_rows = conn.execute(
            """
            SELECT DISTINCT TRIM(from_label) AS payer_label
            FROM transactions
            WHERE SUBSTR(TRIM(to_label), 1, 5) = ?
              AND (
                SUBSTR(TRIM(from_label), 1, 2) = 'U_'
                OR SUBSTR(TRIM(from_label), 1, 3) = 'UD_'
              )
              AND SUBSTR(date, 1, 10) < ?
            """,
            (professional_ref, start),
        ).fetchall()

        prior_payers = {
            str(row["payer_label"]).strip()
            for row in prior_rows
            if str(row["payer_label"] or "").strip()
        }

    payer_items: list[dict[str, Any]] = []

    total_volume = 0.0
    total_tx_count = 0

    new_payer_count = 0
    returning_payer_count = 0
    new_payer_volume = 0.0
    returning_payer_volume = 0.0

    single_payment_payer_count = 0
    occasional_payer_count = 0
    frequent_payer_count = 0

    single_payment_volume = 0.0
    occasional_payer_volume = 0.0
    frequent_payer_volume = 0.0

    recurrent_payer_count = 0
    recurrent_payer_volume = 0.0

    for row in period_rows:
        payer_label = str(row["payer_label"] or "").strip()
        tx_count = _safe_int(row["tx_count"])
        volume = _safe_float(row["volume"])
        is_returning = payer_label in prior_payers

        payer_items.append({
            "payer_label": payer_label,
            "tx_count": tx_count,
            "volume": volume,
            "first_payment_date": row["first_payment_date"],
            "last_payment_date": row["last_payment_date"],
            "is_returning": is_returning,
        })

        total_volume += volume
        total_tx_count += tx_count

        if is_returning:
            returning_payer_count += 1
            returning_payer_volume += volume
        else:
            new_payer_count += 1
            new_payer_volume += volume

        if tx_count <= 1:
            single_payment_payer_count += 1
            single_payment_volume += volume
        elif tx_count <= 3:
            occasional_payer_count += 1
            occasional_payer_volume += volume
            recurrent_payer_count += 1
            recurrent_payer_volume += volume
        else:
            frequent_payer_count += 1
            frequent_payer_volume += volume
            recurrent_payer_count += 1
            recurrent_payer_volume += volume

    payer_count = len(payer_items)

    def share_pct(part: float, whole: float) -> float:
        return 100.0 * part / whole if whole > 0 else 0.0

    average_transactions_per_payer = (
        total_tx_count / payer_count
        if payer_count > 0
        else 0.0
    )

    return {
        "summary": {
            "payer_count": payer_count,
            "tx_count": total_tx_count,
            "total_volume": total_volume,
            "average_transactions_per_payer": average_transactions_per_payer,

            "new_payer_count": new_payer_count,
            "returning_payer_count": returning_payer_count,
            "new_payer_share_pct": share_pct(new_payer_count, payer_count),
            "returning_payer_share_pct": share_pct(returning_payer_count, payer_count),
            "new_payer_volume": new_payer_volume,
            "returning_payer_volume": returning_payer_volume,
            "new_payer_volume_share_pct": share_pct(new_payer_volume, total_volume),
            "returning_payer_volume_share_pct": share_pct(returning_payer_volume, total_volume),

            "single_payment_payer_count": single_payment_payer_count,
            "occasional_payer_count": occasional_payer_count,
            "frequent_payer_count": frequent_payer_count,
            "single_payment_payer_share_pct": share_pct(single_payment_payer_count, payer_count),
            "occasional_payer_share_pct": share_pct(occasional_payer_count, payer_count),
            "frequent_payer_share_pct": share_pct(frequent_payer_count, payer_count),

            "single_payment_volume": single_payment_volume,
            "occasional_payer_volume": occasional_payer_volume,
            "frequent_payer_volume": frequent_payer_volume,

            "recurrent_payer_count": recurrent_payer_count,
            "recurrent_payer_share_pct": share_pct(recurrent_payer_count, payer_count),
            "recurrent_payer_volume": recurrent_payer_volume,
            "recurrent_payer_volume_share_pct": share_pct(recurrent_payer_volume, total_volume),
        },
        "history_segments": [
            {
                "key": "new",
                "label": "Nouveaux pour ce pro",
                "payer_count": new_payer_count,
                "payer_share_pct": share_pct(new_payer_count, payer_count),
                "volume": new_payer_volume,
                "volume_share_pct": share_pct(new_payer_volume, total_volume),
            },
            {
                "key": "returning",
                "label": "Déjà vus avant la période",
                "payer_count": returning_payer_count,
                "payer_share_pct": share_pct(returning_payer_count, payer_count),
                "volume": returning_payer_volume,
                "volume_share_pct": share_pct(returning_payer_volume, total_volume),
            },
        ],
        "frequency_segments": [
            {
                "key": "single",
                "label": "1 paiement",
                "payer_count": single_payment_payer_count,
                "payer_share_pct": share_pct(single_payment_payer_count, payer_count),
                "volume": single_payment_volume,
            },
            {
                "key": "occasional",
                "label": "2 à 3 paiements",
                "payer_count": occasional_payer_count,
                "payer_share_pct": share_pct(occasional_payer_count, payer_count),
                "volume": occasional_payer_volume,
            },
            {
                "key": "frequent",
                "label": "4 paiements ou plus",
                "payer_count": frequent_payer_count,
                "payer_share_pct": share_pct(frequent_payer_count, payer_count),
                "volume": frequent_payer_volume,
            },
        ],
    }


def get_professional_detail_dynamics(
    professional_ref: str,
    *,
    start: str | None = None,
    end: str | None = None,
    network_limit: int = DEFAULT_NETWORK_LIMIT,
) -> dict[str, Any]:
    normalized_ref = _normalize_professional_ref(professional_ref)
    clean_limit = max(1, min(MAX_NETWORK_LIMIT, _safe_int(network_limit, DEFAULT_NETWORK_LIMIT)))

    with _connect() as conn:
        period = _resolve_effective_period(conn, normalized_ref, start, end)

        effective_start = period["effective_start"]
        effective_end = period["effective_end"]

        b2b_network = _build_b2b_network(
            conn,
            professional_ref=normalized_ref,
            start=effective_start,
            end=effective_end,
            network_limit=clean_limit,
        )

        balance_timeseries = _build_balance_timeseries(
            conn,
            professional_ref=normalized_ref,
            start=effective_start,
            end=effective_end,
        )

        individual_payment_rhythm = _build_individual_payment_rhythm(
            conn,
            professional_ref=normalized_ref,
            start=effective_start,
            end=effective_end,
        )

        individual_customer_concentration = _build_individual_customer_concentration(
            conn,
            professional_ref=normalized_ref,
            start=effective_start,
            end=effective_end,
        )

        individual_customer_loyalty = _build_individual_customer_loyalty(
            conn,
            professional_ref=normalized_ref,
            start=effective_start,
            end=effective_end,
        )

    return {
        "status": "ok",
        "professional_ref": normalized_ref,
        "requested_period": {
            "start": period["requested_start"],
            "end": period["requested_end"],
        },
        "effective_period": {
            "start": effective_start,
            "end": effective_end,
        },
        "bounds": {
            "balance_min_date": period["balance_min_date"],
            "balance_max_date": period["balance_max_date"],
            "transaction_min_date": period["transaction_min_date"],
            "transaction_max_date": period["transaction_max_date"],
        },
        "b2b_network": b2b_network,
        "balance_timeseries": balance_timeseries,
        "individual_payment_rhythm": individual_payment_rhythm,
        "individual_customer_concentration": individual_customer_concentration,
        "individual_customer_loyalty": individual_customer_loyalty,
    }
