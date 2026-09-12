from __future__ import annotations

from datetime import datetime, UTC
from typing import Any

from server.database import get_connection, init_db
from server.services.cyclos_actor_classifier import classify_cyclos_transaction
from server.services.cyclos_client import get_transactions


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _parse_amount(value: Any) -> float | None:
    if value in (None, False, ""):
        return None

    try:
        return float(str(value).replace(",", ".").strip())
    except (TypeError, ValueError):
        return None


def _transaction_key(row: dict[str, Any]) -> tuple[str | None, str | None]:
    transaction_number = row.get("transaction_number")
    cyclos_id = row.get("cyclos_id")

    transaction_number = str(transaction_number).strip() if transaction_number else None
    cyclos_id = str(cyclos_id).strip() if cyclos_id else None

    return transaction_number, cyclos_id


def _store_classified_transaction_rows(rows: list[dict[str, Any]]) -> dict[str, int]:
    init_db()

    conn = get_connection()
    cur = conn.cursor()

    inserted = 0
    updated = 0
    skipped = 0

    for row in rows:
        transaction_number, cyclos_id = _transaction_key(row)

        # La table historique a transaction_number comme clé primaire.
        # Si Cyclos ne fournit pas de transactionNumber, on utilise cyclos_id
        # comme clé de substitution stable.
        storage_transaction_number = transaction_number or cyclos_id

        if not storage_transaction_number and not cyclos_id:
            skipped += 1
            continue

        existing = None

        if cyclos_id:
            existing = cur.execute(
                """
                SELECT rowid
                FROM transactions
                WHERE cyclos_id = ?
                LIMIT 1
                """,
                (cyclos_id,),
            ).fetchone()

        if existing is None and storage_transaction_number:
            existing = cur.execute(
                """
                SELECT rowid
                FROM transactions
                WHERE transaction_number = ?
                LIMIT 1
                """,
                (storage_transaction_number,),
            ).fetchone()

        params = (
            storage_transaction_number,
            cyclos_id,
            row.get("date"),
            row.get("group_label"),
            row.get("from_label"),
            row.get("to_label"),
            _parse_amount(row.get("amount")),
            row.get("type_label"),
        )

        if existing is None:
            cur.execute(
                """
                INSERT INTO transactions (
                    transaction_number,
                    cyclos_id,
                    date,
                    group_label,
                    from_label,
                    to_label,
                    amount,
                    type_label
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                params,
            )
            inserted += 1
        else:
            cur.execute(
                """
                UPDATE transactions
                SET
                    transaction_number = ?,
                    cyclos_id = ?,
                    date = ?,
                    group_label = ?,
                    from_label = ?,
                    to_label = ?,
                    amount = ?,
                    type_label = ?
                WHERE rowid = ?
                """,
                (*params, existing["rowid"]),
            )
            updated += 1

    conn.commit()
    conn.close()

    return {
        "inserted": inserted,
        "updated": updated,
        "skipped": skipped,
    }


def classify_transaction_for_storage(
    transaction: dict[str, Any],
    *,
    mlc_id: str,
) -> dict[str, Any]:
    classified = classify_cyclos_transaction(transaction, mlc_id=mlc_id)

    return {
        "transaction_number": classified.get("transaction_number"),
        "cyclos_id": classified.get("cyclos_id"),
        "date": classified.get("date"),
        "group_label": transaction.get("kind") or transaction.get("creationType"),
        "from_label": classified.get("from_label"),
        "to_label": classified.get("to_label"),
        "amount": classified.get("amount"),
        "type_label": classified.get("type_label"),
        "type_internal": classified.get("type_internal"),
        "from_family": classified.get("from_family"),
        "to_family": classified.get("to_family"),
    }


def sync_cyclos_transactions(
    *,
    mlc_id: str,
    days: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int | None = None,
    reset: bool = False,
    write: bool = True,
) -> dict[str, Any]:
    deleted = 0

    raw_transactions = get_transactions(
        days=days,
        date_from=date_from,
        date_to=date_to,
    )

    if limit is not None:
        selected_transactions = raw_transactions[:max(0, int(limit))]
    else:
        selected_transactions = raw_transactions

    rows = [
        classify_transaction_for_storage(transaction, mlc_id=mlc_id)
        for transaction in selected_transactions
    ]

    unknown_rows = [
        row for row in rows
        if row.get("from_family") == "X" or row.get("to_family") == "X"
    ]

    if unknown_rows:
        return {
            "mlc_id": mlc_id,
            "write": False,
            "reset": reset,
            "deleted": deleted,
            "fetched": len(raw_transactions),
            "selected": len(rows),
            "unknown_count": len(unknown_rows),
            "error": "Classification incomplète : des acteurs restent en famille X.",
            "unknown_samples": unknown_rows[:10],
            "synced_at": _utc_now(),
        }

    write_result = {
        "inserted": 0,
        "updated": 0,
        "skipped": 0,
    }

    if write:
        write_result = _store_classified_transaction_rows(rows)

    return {
        "mlc_id": mlc_id,
        "write": write,
        "reset": reset,
        "deleted": deleted,
        "fetched": len(raw_transactions),
        "selected": len(rows),
        "unknown_count": 0,
        **write_result,
        "synced_at": _utc_now(),
    }
