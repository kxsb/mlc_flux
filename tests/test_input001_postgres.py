import json
import os
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine, insert

from server.input_contract.reader import FinancialContractReader
from server.input_contract.schema import (
    accounts,
    dataset_metadata,
    transactions,
)


POSTGRES_URL = os.environ.get("INPUT001_POSTGRES_URL")

FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "input001"
    / "normalized_reference_cases.json"
)


def _dt(value):
    if value is None:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _gonette_dataset():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))

    return next(
        item
        for item in payload["datasets"]
        if item["name"] == "gonette_cyclos_reference"
    )


@pytest.mark.skipif(
    not POSTGRES_URL,
    reason="INPUT001_POSTGRES_URL not configured",
)
def test_reader_reads_same_contract_from_postgresql():
    engine = create_engine(POSTGRES_URL)
    dataset = _gonette_dataset()

    # Base PostgreSQL dédiée et éphémère : on ne crée que
    # les trois relations obligatoires du contrat.
    with engine.begin() as conn:
        transactions.drop(conn, checkfirst=True)
        accounts.drop(conn, checkfirst=True)
        dataset_metadata.drop(conn, checkfirst=True)

        accounts.create(conn)
        transactions.create(conn)
        dataset_metadata.create(conn)

        source_system = dataset["metadata"]["source_system"]

        conn.execute(
            insert(accounts),
            [
                {
                    "account_id": row["account_id"],
                    "native_account_type": row.get(
                        "native_account_type"
                    ),
                    "native_status": row.get("native_status"),
                    "display_label": row.get("display_label"),
                    "native_owner_id": row.get("native_owner_id"),
                    "source_system": source_system,
                }
                for row in dataset["accounts"]
            ],
        )

        conn.execute(
            insert(transactions),
            [
                {
                    "transaction_id": row["transaction_id"],
                    "occurred_at": _dt(row["occurred_at"]),
                    "source_account_id": row[
                        "source_account_id"
                    ],
                    "destination_account_id": row[
                        "destination_account_id"
                    ],
                    "amount_minor": row["amount_minor"],
                    "currency_code": row["currency_code"],
                    "currency_exponent": row.get(
                        "currency_exponent", 2
                    ),
                    "native_transaction_type": row.get(
                        "native_transaction_type"
                    ),
                    "native_transaction_label": row.get(
                        "native_transaction_label"
                    ),
                }
                for row in dataset["transactions"]
            ],
        )

        conn.execute(
            insert(dataset_metadata),
            [
                {
                    "dataset_id": dataset["name"],
                    "contract_version": "input001-v0.1",
                    "source_system": source_system,
                    "account_state_history": False,
                    "balances": False,
                    "account_replacements": False,
                }
            ],
        )

    reader = FinancialContractReader(engine)

    reader.validate_required_relations()

    assert reader.metadata_row()["source_system"] == "cyclos"

    account_rows = reader.fetch_accounts()
    transaction_rows = reader.fetch_transactions()

    assert len(account_rows) == 3
    assert len(transaction_rows) == 2

    assert transaction_rows[0]["transaction_id"] == "gonette-tx-001"
    assert transaction_rows[0]["amount_minor"] == 1250
    assert transaction_rows[0]["currency_exponent"] == 2

    capabilities = reader.capabilities()

    assert capabilities.account_state_history is False
    assert capabilities.balances is False
    assert capabilities.account_replacements is False
