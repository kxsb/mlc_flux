import json
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine, insert

from server.input_contract.reader import (
    FinancialContractReader,
    InputContractError,
)
from server.input_contract.schema import (
    account_replacements,
    account_states,
    accounts,
    balances,
    dataset_metadata,
    transactions,
)


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


def _load_fixture():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _dataset(name):
    return next(
        item
        for item in _load_fixture()["datasets"]
        if item["name"] == name
    )


def _build_sqlite_dataset(dataset):
    engine = create_engine("sqlite+pysqlite:///:memory:")

    required_tables = [
        accounts,
        transactions,
        dataset_metadata,
    ]

    for table in required_tables:
        table.create(engine)

    capabilities = dataset["metadata"]

    if capabilities.get("account_state_history"):
        account_states.create(engine)

    if capabilities.get("balances"):
        balances.create(engine)

    if capabilities.get("account_replacements"):
        account_replacements.create(engine)

    source_system = capabilities["source_system"]

    account_rows = [
        {
            "account_id": row["account_id"],
            "native_account_number": row.get("native_account_number"),
            "native_account_type": row.get("native_account_type"),
            "native_status": row.get("native_status"),
            "display_label": row.get("display_label"),
            "native_owner_id": row.get("native_owner_id"),
            "source_system": source_system,
        }
        for row in dataset["accounts"]
    ]

    transaction_rows = [
        {
            "transaction_id": row["transaction_id"],
            "occurred_at": _dt(row["occurred_at"]),
            "source_account_id": row["source_account_id"],
            "destination_account_id": row["destination_account_id"],
            "amount_minor": row["amount_minor"],
            "currency_code": row["currency_code"],
            "currency_exponent": row.get("currency_exponent", 2),
            "native_transaction_type": row.get(
                "native_transaction_type"
            ),
            "native_transaction_label": row.get(
                "native_transaction_label"
            ),
            "native_transaction_group": row.get(
                "native_transaction_group"
            ),
        }
        for row in dataset["transactions"]
    ]

    metadata_row = {
        "dataset_id": dataset["name"],
        "contract_version": "input001-v0.1",
        "source_system": source_system,
        "account_state_history": capabilities.get(
            "account_state_history", False
        ),
        "balances": capabilities.get("balances", False),
        "account_replacements": capabilities.get(
            "account_replacements", False
        ),
    }

    with engine.begin() as conn:
        conn.execute(insert(accounts), account_rows)
        conn.execute(insert(transactions), transaction_rows)
        conn.execute(insert(dataset_metadata), [metadata_row])

        if capabilities.get("account_state_history"):
            rows = [
                {
                    **row,
                    "valid_from": _dt(row["valid_from"]),
                    "valid_to": _dt(row.get("valid_to")),
                }
                for row in dataset.get("account_states", [])
            ]
            if rows:
                conn.execute(insert(account_states), rows)

        if capabilities.get("account_replacements"):
            rows = [
                {
                    **row,
                    "effective_at": _dt(row["effective_at"]),
                }
                for row in dataset.get("account_replacements", [])
            ]
            if rows:
                conn.execute(insert(account_replacements), rows)

    return engine


def test_reader_reads_gonette_contract_from_sqlite():
    engine = _build_sqlite_dataset(
        _dataset("gonette_cyclos_reference")
    )
    reader = FinancialContractReader(engine)

    reader.validate_required_relations()

    assert reader.metadata_row()["source_system"] == "cyclos"
    assert len(reader.fetch_accounts()) == 3
    assert len(reader.fetch_transactions()) == 2

    transaction = reader.fetch_transactions()[0]

    assert transaction["transaction_id"] == "gonette-tx-001"
    assert transaction["amount_minor"] == 1250


def test_reader_reads_graine_contract_from_sqlite():
    engine = _build_sqlite_dataset(
        _dataset("graine_cyclos_reference")
    )
    reader = FinancialContractReader(engine)

    account_rows = reader.fetch_accounts()
    assert len(account_rows) == 3
    assert len(reader.fetch_transactions()) == 2

    professional = next(
        row
        for row in account_rows
        if row["account_id"] == "graine-p-001"
    )
    assert (
        professional["native_account_number"]
        == "graine-pro-reference-001"
    )

    missing_actor = next(
        row
        for row in reader.fetch_transactions()
        if row["transaction_id"] == "graine-tx-missing-actor"
    )

    assert missing_actor["source_account_id"] is None
    assert missing_actor["destination_account_id"] == "graine-p-001"
    assert missing_actor["native_transaction_group"] == "reference-case"


def test_gonette_does_not_expose_optional_relations():
    engine = _build_sqlite_dataset(
        _dataset("gonette_cyclos_reference")
    )

    capabilities = FinancialContractReader(engine).capabilities()

    assert capabilities.account_state_history is False
    assert capabilities.balances is False
    assert capabilities.account_replacements is False

    assert "account_states" not in capabilities.relations
    assert "balances" not in capabilities.relations
    assert "account_replacements" not in capabilities.relations


def test_comchain_exposes_declared_optional_relations():
    engine = _build_sqlite_dataset(
        _dataset("comchain_account_replacement_reference")
    )

    capabilities = FinancialContractReader(engine).capabilities()

    assert capabilities.account_state_history is True
    assert capabilities.balances is True
    assert capabilities.account_replacements is True

    assert "account_states" in capabilities.relations
    assert "balances" in capabilities.relations
    assert "account_replacements" in capabilities.relations


def test_reader_rejects_missing_required_relation():
    engine = create_engine("sqlite+pysqlite:///:memory:")

    accounts.create(engine)
    dataset_metadata.create(engine)

    reader = FinancialContractReader(engine)

    with pytest.raises(
        InputContractError,
        match="transactions",
    ):
        reader.validate_required_relations()


def test_reader_requires_exactly_one_metadata_row():
    engine = create_engine("sqlite+pysqlite:///:memory:")

    accounts.create(engine)
    transactions.create(engine)
    dataset_metadata.create(engine)

    reader = FinancialContractReader(engine)

    with pytest.raises(
        InputContractError,
        match="exactly one row",
    ):
        reader.metadata_row()


def _build_empty_required_contract(
    *,
    contract_version="input001-v0.1",
    balances_enabled=False,
):
    engine = create_engine("sqlite+pysqlite:///:memory:")

    accounts.create(engine)
    transactions.create(engine)
    dataset_metadata.create(engine)

    with engine.begin() as conn:
        conn.execute(
            insert(dataset_metadata),
            [{
                "dataset_id": "validation-test",
                "contract_version": contract_version,
                "source_system": "synthetic",
                "account_state_history": False,
                "balances": balances_enabled,
                "account_replacements": False,
            }],
        )

    return engine


def test_reader_rejects_unknown_contract_version():
    engine = _build_empty_required_contract(
        contract_version="input001-v999"
    )

    with pytest.raises(
        InputContractError,
        match="Unsupported financial contract version",
    ):
        FinancialContractReader(engine).metadata_row()


def test_reader_rejects_declared_capability_without_relation():
    engine = _build_empty_required_contract(
        balances_enabled=True
    )

    with pytest.raises(
        InputContractError,
        match="balances",
    ):
        FinancialContractReader(engine).capabilities()


def test_reader_rejects_required_relations_with_wrong_columns():
    engine = create_engine("sqlite+pysqlite:///:memory:")

    with engine.begin() as conn:
        for relation_name in (
            "accounts",
            "transactions",
            "dataset_metadata",
        ):
            conn.exec_driver_sql(
                f"CREATE VIEW {relation_name} "
                "AS SELECT 1 AS wrong_column"
            )

    with pytest.raises(
        InputContractError,
        match="missing columns",
    ):
        FinancialContractReader(
            engine
        ).validate_required_relations()


def test_reader_rejects_empty_dataset_identity():
    engine = create_engine("sqlite+pysqlite:///:memory:")

    accounts.create(engine)
    transactions.create(engine)
    dataset_metadata.create(engine)

    with engine.begin() as conn:
        conn.execute(
            insert(dataset_metadata),
            [{
                "dataset_id": "",
                "contract_version": "input001-v0.1",
                "source_system": "synthetic",
                "account_state_history": False,
                "balances": False,
                "account_replacements": False,
            }],
        )

    with pytest.raises(
        InputContractError,
        match="dataset_metadata.dataset_id",
    ):
        FinancialContractReader(engine).metadata_row()
