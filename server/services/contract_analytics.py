from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
import sqlite3
from typing import Any


class ContractAnalyticsError(ValueError):
    pass


def _table_exists(
    connection: sqlite3.Connection,
    name: str,
) -> bool:
    row = connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type IN ('table', 'view')
          AND name = ?
        LIMIT 1
        """,
        (name,),
    ).fetchone()

    return row is not None


def _parse_date(
    value: str | None,
    *,
    field_name: str,
) -> date | None:
    if value is None:
        return None

    text = str(value).strip()

    if not text:
        return None

    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise ContractAnalyticsError(
            f"{field_name} doit être au format YYYY-MM-DD."
        ) from exc


def _period_bounds(
    start: str | None,
    end: str | None,
) -> tuple[int | None, int | None, str | None, str | None]:
    start_date = _parse_date(
        start,
        field_name="start",
    )

    end_date = _parse_date(
        end,
        field_name="end",
    )

    if (
        start_date is not None
        and end_date is not None
        and start_date > end_date
    ):
        raise ContractAnalyticsError(
            "start ne peut pas être postérieur à end."
        )

    start_ts = None
    end_exclusive_ts = None

    if start_date is not None:
        start_ts = int(
            datetime.combine(
                start_date,
                time.min,
                tzinfo=UTC,
            ).timestamp()
        )

    if end_date is not None:
        end_exclusive_ts = int(
            datetime.combine(
                end_date + timedelta(days=1),
                time.min,
                tzinfo=UTC,
            ).timestamp()
        )

    return (
        start_ts,
        end_exclusive_ts,
        (
            start_date.isoformat()
            if start_date is not None
            else None
        ),
        (
            end_date.isoformat()
            if end_date is not None
            else None
        ),
    )


def _where_period(
    start_ts: int | None,
    end_exclusive_ts: int | None,
    *,
    alias: str = "t",
) -> tuple[str, list[int]]:
    conditions = []
    params: list[int] = []

    if start_ts is not None:
        conditions.append(
            f"{alias}.received_at >= ?"
        )
        params.append(start_ts)

    if end_exclusive_ts is not None:
        conditions.append(
            f"{alias}.received_at < ?"
        )
        params.append(end_exclusive_ts)

    if not conditions:
        return "", params

    return (
        " WHERE " + " AND ".join(conditions),
        params,
    )


def _runtime_state(
    connection: sqlite3.Connection,
) -> dict[str, dict[str, Any]]:
    if not _table_exists(
        connection,
        "contract_runtime_state",
    ):
        return {}

    rows = connection.execute(
        """
        SELECT
            contract_name,
            contract_version,
            status,
            source_instance_id,
            source_ref,
            refreshed_at,
            row_count
        FROM contract_runtime_state
        ORDER BY contract_name
        """
    ).fetchall()

    return {
        row["contract_name"]: dict(row)
        for row in rows
    }


def get_contract_overview(
    connection: sqlite3.Connection,
    *,
    start: str | None = None,
    end: str | None = None,
    recent_limit: int = 12,
) -> dict[str, Any]:
    required = (
        "contract001_transactions",
        "contract001_transaction_partners",
        "contract002_partners",
    )

    missing = [
        name
        for name in required
        if not _table_exists(
            connection,
            name,
        )
    ]

    if missing:
        return {
            "available": False,
            "reason": "contract_runtime_missing",
            "missing": missing,
            "source": _runtime_state(connection),
        }

    (
        start_ts,
        end_exclusive_ts,
        requested_start,
        requested_end,
    ) = _period_bounds(
        start,
        end,
    )

    where_sql, params = _where_period(
        start_ts,
        end_exclusive_ts,
    )

    summary = connection.execute(
        f"""
        SELECT
            COUNT(*) AS transaction_count,
            COUNT(
                DISTINCT date(
                    t.received_at,
                    'unixepoch'
                )
            ) AS active_days,
            MIN(t.received_at) AS min_ts,
            MAX(t.received_at) AS max_ts
        FROM contract001_transactions AS t
        {where_sql}
        """,
        params,
    ).fetchone()

    partner_summary = connection.execute(
        f"""
        SELECT
            COUNT(DISTINCT l.partner_id)
                AS referenced_partners,
            COUNT(
                DISTINCT CASE
                    WHEN l.side = 'sender'
                    THEN l.partner_id
                END
            ) AS sender_partners,
            COUNT(
                DISTINCT CASE
                    WHEN l.side = 'receiver'
                    THEN l.partner_id
                END
            ) AS receiver_partners,
            COUNT(
                DISTINCT CASE
                    WHEN p.partner_id IS NOT NULL
                    THEN l.partner_id
                END
            ) AS resolved_partners
        FROM contract001_transaction_partners AS l
        JOIN contract001_transactions AS t
          ON t.hash = l.hash
        LEFT JOIN contract002_partners AS p
          ON p.partner_id = l.partner_id
        {where_sql}
        """,
        params,
    ).fetchone()

    shared = connection.execute(
        f"""
        SELECT
            COUNT(*) AS shared_sides,
            COUNT(DISTINCT grouped.hash)
                AS shared_transactions
        FROM (
            SELECT
                t.hash AS hash,
                l.side AS side,
                COUNT(DISTINCT l.partner_id)
                    AS owner_count
            FROM contract001_transactions AS t
            JOIN contract001_transaction_partners AS l
              ON l.hash = t.hash
            {where_sql}
            GROUP BY
                t.hash,
                l.side
            HAVING COUNT(DISTINCT l.partner_id) > 1
        ) AS grouped
        """,
        params,
    ).fetchone()

    daily_rows = connection.execute(
        f"""
        SELECT
            date(
                t.received_at,
                'unixepoch'
            ) AS day,
            COUNT(*) AS transaction_count
        FROM contract001_transactions AS t
        {where_sql}
        GROUP BY day
        ORDER BY day
        """,
        params,
    ).fetchall()

    type_rows = connection.execute(
        f"""
        SELECT
            COALESCE(t.type, 'unknown')
                AS native_type,
            COALESCE(t.fn_abi, 'unknown')
                AS native_subtype,
            COUNT(*) AS transaction_count
        FROM contract001_transactions AS t
        {where_sql}
        GROUP BY
            COALESCE(t.type, 'unknown'),
            COALESCE(t.fn_abi, 'unknown')
        ORDER BY
            transaction_count DESC,
            native_type,
            native_subtype
        """,
        params,
    ).fetchall()

    partner_activity = connection.execute(
        f"""
        SELECT
            l.partner_id,
            COALESCE(
                p.name,
                'Partner #' || l.partner_id
            ) AS partner_name,
            COUNT(DISTINCT l.hash)
                AS transaction_count,
            COUNT(
                DISTINCT CASE
                    WHEN l.side = 'sender'
                    THEN l.hash
                END
            ) AS sender_transaction_count,
            COUNT(
                DISTINCT CASE
                    WHEN l.side = 'receiver'
                    THEN l.hash
                END
            ) AS receiver_transaction_count
        FROM contract001_transaction_partners AS l
        JOIN contract001_transactions AS t
          ON t.hash = l.hash
        LEFT JOIN contract002_partners AS p
          ON p.partner_id = l.partner_id
        {where_sql}
        GROUP BY
            l.partner_id,
            p.name
        ORDER BY
            transaction_count DESC,
            partner_name
        LIMIT 20
        """,
        params,
    ).fetchall()

    recent_where = where_sql

    recent_rows = connection.execute(
        f"""
        SELECT
            t.hash,
            t.received_at,
            t.type,
            t.fn_abi,
            t.is_sender_external,
            t.is_receiver_external,

            (
                SELECT GROUP_CONCAT(
                    COALESCE(
                        p.name,
                        'Partner #' || l.partner_id
                    ),
                    ', '
                )
                FROM contract001_transaction_partners AS l
                LEFT JOIN contract002_partners AS p
                  ON p.partner_id = l.partner_id
                WHERE l.hash = t.hash
                  AND l.side = 'sender'
            ) AS sender_partners,

            (
                SELECT GROUP_CONCAT(
                    COALESCE(
                        p.name,
                        'Partner #' || l.partner_id
                    ),
                    ', '
                )
                FROM contract001_transaction_partners AS l
                LEFT JOIN contract002_partners AS p
                  ON p.partner_id = l.partner_id
                WHERE l.hash = t.hash
                  AND l.side = 'receiver'
            ) AS receiver_partners

        FROM contract001_transactions AS t
        {recent_where}
        ORDER BY
            t.received_at DESC,
            t.hash DESC
        LIMIT ?
        """,
        [
            *params,
            max(
                1,
                min(
                    int(recent_limit),
                    100,
                ),
            ),
        ],
    ).fetchall()

    min_ts = (
        summary["min_ts"]
        if summary
        else None
    )

    max_ts = (
        summary["max_ts"]
        if summary
        else None
    )

    def iso_date(
        timestamp: int | None,
    ) -> str | None:
        if timestamp is None:
            return None

        return datetime.fromtimestamp(
            timestamp,
            tz=UTC,
        ).date().isoformat()

    def iso_datetime(
        timestamp: int | None,
    ) -> str | None:
        if timestamp is None:
            return None

        return datetime.fromtimestamp(
            timestamp,
            tz=UTC,
        ).isoformat()

    states = _runtime_state(
        connection
    )

    tx_state = states.get(
        "transactions",
        {},
    )

    return {
        "available": True,
        "grain": "financial_event_hash",
        "monetary_amounts_available": False,
        "monetary_amounts_reason": (
            "unit_code_and_exponent_not_configured"
        ),
        "period": {
            "requested_start": requested_start,
            "requested_end": requested_end,
            "available_start": iso_date(
                min_ts
            ),
            "available_end": iso_date(
                max_ts
            ),
        },
        "summary": {
            "transaction_count": int(
                summary["transaction_count"]
                if summary
                else 0
            ),
            "active_days": int(
                summary["active_days"]
                if summary
                else 0
            ),
            "referenced_partners": int(
                partner_summary[
                    "referenced_partners"
                ]
                if partner_summary
                else 0
            ),
            "resolved_partners": int(
                partner_summary[
                    "resolved_partners"
                ]
                if partner_summary
                else 0
            ),
            "sender_partners": int(
                partner_summary[
                    "sender_partners"
                ]
                if partner_summary
                else 0
            ),
            "receiver_partners": int(
                partner_summary[
                    "receiver_partners"
                ]
                if partner_summary
                else 0
            ),
            "shared_sides": int(
                shared["shared_sides"]
                if shared
                else 0
            ),
            "shared_transactions": int(
                shared[
                    "shared_transactions"
                ]
                if shared
                else 0
            ),
        },
        "daily": [
            {
                "date": row["day"],
                "transactions": int(
                    row["transaction_count"]
                ),
            }
            for row in daily_rows
        ],
        "native_types": [
            {
                "type": row["native_type"],
                "subtype": row[
                    "native_subtype"
                ],
                "transactions": int(
                    row[
                        "transaction_count"
                    ]
                ),
            }
            for row in type_rows
        ],
        "partner_activity": [
            {
                "partner_id": row[
                    "partner_id"
                ],
                "name": row[
                    "partner_name"
                ],
                "transactions": int(
                    row[
                        "transaction_count"
                    ]
                ),
                "sender_transactions": int(
                    row[
                        "sender_transaction_count"
                    ]
                ),
                "receiver_transactions": int(
                    row[
                        "receiver_transaction_count"
                    ]
                ),
            }
            for row in partner_activity
        ],
        "recent": [
            {
                "hash": row["hash"],
                "received_at": iso_datetime(
                    row["received_at"]
                ),
                "type": row["type"],
                "subtype": row["fn_abi"],
                "sender_partners": (
                    row["sender_partners"]
                    or None
                ),
                "receiver_partners": (
                    row["receiver_partners"]
                    or None
                ),
                "sender_external": bool(
                    row[
                        "is_sender_external"
                    ]
                ),
                "receiver_external": bool(
                    row[
                        "is_receiver_external"
                    ]
                ),
            }
            for row in recent_rows
        ],
        "source": {
            "instance_id": (
                tx_state.get(
                    "source_instance_id"
                )
            ),
            "reference": (
                tx_state.get(
                    "source_ref"
                )
            ),
            "refreshed_at": (
                tx_state.get(
                    "refreshed_at"
                )
            ),
            "contract_version": (
                tx_state.get(
                    "contract_version"
                )
            ),
            "states": states,
        },
    }
