from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, select

from server.input_contract.reader import FinancialContractReader
from server.input_contract.schema import balances
from server.input_contract.writer import (
    FinancialDatasetPayload,
    InputContractWriteError,
    materialize_financial_dataset,
)


def minimal_payload(
    *,
    dataset_id="dataset-a",
    amount_minor=1250,
):
    return FinancialDatasetPayload(
        dataset_metadata={
            "dataset_id": dataset_id,
            "contract_version": "input001-v0.1",
            "source_system": "test-provider",
            "account_state_history": False,
            "balances": False,
            "account_replacements": False,
        },
        accounts=[
            {
                "account_id": "A",
                "source_system": "test-provider",
            },
            {
                "account_id": "B",
                "source_system": "test-provider",
            },
        ],
        transactions=[
            {
                "transaction_id": f"{dataset_id}-tx",
                "occurred_at": datetime(
                    2026, 9, 13, 12, 0, tzinfo=UTC
                ),
                "source_account_id": "A",
                "destination_account_id": "B",
                "amount_minor": amount_minor,
                "currency_code": "LOCAL",
                "currency_exponent": 2,
            }
        ],
    )


def test_materializes_minimal_contract():
    engine = create_engine("sqlite+pysqlite:///:memory:")

    materialize_financial_dataset(
        engine,
        minimal_payload(),
    )

    reader = FinancialContractReader(engine)

    assert reader.metadata_row()["dataset_id"] == "dataset-a"
    assert len(reader.fetch_accounts()) == 2
    assert len(reader.fetch_transactions()) == 1

    capabilities = reader.capabilities()

    assert capabilities.account_state_history is False
    assert capabilities.balances is False
    assert capabilities.account_replacements is False


def test_materializes_empty_optional_relation():
    engine = create_engine("sqlite+pysqlite:///:memory:")

    payload = minimal_payload()

    payload = FinancialDatasetPayload(
        dataset_metadata={
            **payload.dataset_metadata,
            "balances": True,
        },
        accounts=payload.accounts,
        transactions=payload.transactions,
        balances=[],
    )

    materialize_financial_dataset(engine, payload)

    reader = FinancialContractReader(engine)

    assert reader.capabilities().balances is True
    assert "balances" in reader.relation_names()


def test_capability_requires_corresponding_payload():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    payload = minimal_payload()

    bad = FinancialDatasetPayload(
        dataset_metadata={
            **payload.dataset_metadata,
            "balances": True,
        },
        accounts=payload.accounts,
        transactions=payload.transactions,
        balances=None,
    )

    with pytest.raises(
        InputContractWriteError,
        match="Capacité 'balances' incohérente",
    ):
        materialize_financial_dataset(engine, bad)


def test_optional_payload_requires_capability():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    payload = minimal_payload()

    bad = FinancialDatasetPayload(
        dataset_metadata=payload.dataset_metadata,
        accounts=payload.accounts,
        transactions=payload.transactions,
        balances=[],
    )

    with pytest.raises(
        InputContractWriteError,
        match="Capacité 'balances' incohérente",
    ):
        materialize_financial_dataset(engine, bad)


def test_unknown_transaction_account_is_rejected():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    payload = minimal_payload()

    bad_transaction = {
        **payload.transactions[0],
        "destination_account_id": "MISSING",
    }

    bad = FinancialDatasetPayload(
        dataset_metadata=payload.dataset_metadata,
        accounts=payload.accounts,
        transactions=[bad_transaction],
    )

    with pytest.raises(
        InputContractWriteError,
        match="compte absent",
    ):
        materialize_financial_dataset(engine, bad)


def test_account_source_system_must_match_dataset():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    payload = minimal_payload()

    bad_accounts = [
        dict(payload.accounts[0]),
        {
            **payload.accounts[1],
            "source_system": "other-provider",
        },
    ]

    bad = FinancialDatasetPayload(
        dataset_metadata=payload.dataset_metadata,
        accounts=bad_accounts,
        transactions=payload.transactions,
    )

    with pytest.raises(
        InputContractWriteError,
        match="source_system incohérent",
    ):
        materialize_financial_dataset(engine, bad)


def test_second_materialization_replaces_first_dataset():
    engine = create_engine("sqlite+pysqlite:///:memory:")

    materialize_financial_dataset(
        engine,
        minimal_payload(
            dataset_id="dataset-old",
            amount_minor=100,
        ),
    )

    materialize_financial_dataset(
        engine,
        minimal_payload(
            dataset_id="dataset-new",
            amount_minor=999,
        ),
    )

    reader = FinancialContractReader(engine)

    assert reader.metadata_row()["dataset_id"] == "dataset-new"

    rows = reader.fetch_transactions()

    assert len(rows) == 1
    assert rows[0]["transaction_id"] == "dataset-new-tx"
    assert rows[0]["amount_minor"] == 999


def test_removed_capability_clears_old_optional_rows():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    base = minimal_payload()

    with_balances = FinancialDatasetPayload(
        dataset_metadata={
            **base.dataset_metadata,
            "balances": True,
        },
        accounts=base.accounts,
        transactions=base.transactions,
        balances=[
            {
                "account_id": "A",
                "observed_at": datetime(
                    2026, 9, 13, 12, 0, tzinfo=UTC
                ),
                "balance_component": "test",
                "amount_minor": 500,
                "currency_code": "LOCAL",
                "currency_exponent": 2,
                "source_system": "test-provider",
            }
        ],
    )

    materialize_financial_dataset(
        engine,
        with_balances,
    )

    materialize_financial_dataset(
        engine,
        minimal_payload(dataset_id="without-balances"),
    )

    reader = FinancialContractReader(engine)

    assert reader.capabilities().balances is False

    with engine.connect() as conn:
        assert conn.execute(
            select(balances)
        ).mappings().all() == []


def test_failed_replacement_keeps_previous_dataset():
    engine = create_engine("sqlite+pysqlite:///:memory:")

    materialize_financial_dataset(
        engine,
        minimal_payload(dataset_id="stable"),
    )

    payload = minimal_payload(dataset_id="broken")

    bad_transaction = dict(payload.transactions[0])
    bad_transaction.pop("amount_minor")

    bad = FinancialDatasetPayload(
        dataset_metadata=payload.dataset_metadata,
        accounts=payload.accounts,
        transactions=[bad_transaction],
    )

    with pytest.raises(
        InputContractWriteError,
        match="Échec de matérialisation",
    ):
        materialize_financial_dataset(engine, bad)

    reader = FinancialContractReader(engine)

    assert reader.metadata_row()["dataset_id"] == "stable"
    assert (
        reader.fetch_transactions()[0]["transaction_id"]
        == "stable-tx"
    )
