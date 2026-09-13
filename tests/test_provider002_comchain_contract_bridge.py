from datetime import UTC, datetime

from sqlalchemy import create_engine, insert

from server.input_contract.reader import FinancialContractReader
from server.input_contract.schema import (
    accounts,
    dataset_metadata,
    transactions,
)
from server.providers.comchain_facts import (
    extract_comchain_transaction_facts,
)
from server.providers.comchain_normalized import (
    ComChainCurrencySpec,
    comchain_transaction_account_rows,
    comchain_transaction_row,
)


SPECS = {
    "monnaie-test": ComChainCurrencySpec(
        native_currency_id="monnaie-test",
        currency_code="LOCAL",
        currency_exponent=2,
        amount_representation="minor",
    )
}


def source_rows():
    # Forme calquée sur la table `transactions` produite
    # par pyc3l-cli 0.6.0.
    return [
        {
            "hash": "0xTx001",
            "block": 1001,
            "received_at": 1789234567,
            "caller": "0xCaller1",
            "contract": "0xContract",
            "contract_abi": "Currency",
            "type": "transfer",
            "sender": "0xAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAa",
            "receiver": "BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
            "amount": 1250,
            "fn": "transfer",
            "fn_abi": "transfer(address,uint256)",
            "status": "",
        },
        {
            "hash": "0xTx002",
            "block": 1002,
            "received_at": 1789234667,
            "caller": "0xCaller2",
            "contract": "0xContract",
            "contract_abi": "Currency",
            "type": "transfer",
            "sender": "BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
            "receiver": "0xcccccccccccccccccccccccccccccccccccccccc",
            "amount": 275,
            "fn": "transfer",
            "fn_abi": "transfer(address,uint256)",
            "status": "",
        },
    ]


def test_pyc3l_shaped_rows_roundtrip_through_input001():
    facts = [
        extract_comchain_transaction_facts(
            row,
            native_currency_id="monnaie-test",
        )
        for row in source_rows()
    ]

    account_rows_by_id = {}

    for item in facts:
        source, destination = (
            comchain_transaction_account_rows(item)
        )

        for account in (source, destination):
            if account is not None:
                account_rows_by_id[
                    account["account_id"]
                ] = account

    transaction_rows = [
        comchain_transaction_row(
            item,
            currency_specs=SPECS,
        )
        for item in facts
    ]

    engine = create_engine(
        "sqlite+pysqlite:///:memory:"
    )

    accounts.create(engine)
    transactions.create(engine)
    dataset_metadata.create(engine)

    with engine.begin() as conn:
        conn.execute(
            insert(accounts),
            list(account_rows_by_id.values()),
        )

        conn.execute(
            insert(transactions),
            transaction_rows,
        )

        conn.execute(
            insert(dataset_metadata),
            [{
                "dataset_id": "comchain-pyc3l-shape",
                "contract_version": "input001-v0.1",
                "source_system": "comchain",
                "account_state_history": False,
                "balances": False,
                "account_replacements": False,
            }],
        )

    reader = FinancialContractReader(engine)

    reader.validate_required_relations()

    stored_accounts = reader.fetch_accounts()
    stored_transactions = reader.fetch_transactions()

    assert [
        row["account_id"]
        for row in stored_accounts
    ] == [
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        "cccccccccccccccccccccccccccccccccccccccc",
    ]

    for account in stored_accounts:
        assert account["native_account_type"] is None
        assert account["native_status"] is None
        assert account["native_owner_id"] is None

    assert len(stored_transactions) == 2

    first = stored_transactions[0]
    second = stored_transactions[1]

    assert first["transaction_id"] == "0xTx001"
    assert first["source_account_id"] == "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    assert first["destination_account_id"] == "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    assert first["amount_minor"] == 1250

    assert second["transaction_id"] == "0xTx002"
    assert second["source_account_id"] == "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    assert second["destination_account_id"] == "cccccccccccccccccccccccccccccccccccccccc"
    assert second["amount_minor"] == 275

    for row in stored_transactions:
        assert row["native_currency_id"] == "monnaie-test"
        assert row["currency_code"] == "LOCAL"
        assert row["currency_exponent"] == 2
        assert row["occurred_at"].tzinfo is not None
        assert row["occurred_at"].utcoffset().total_seconds() == 0

    assert first["occurred_at"] == datetime.fromtimestamp(
        1789234567,
        tz=UTC,
    )


def test_account_registry_is_observed_not_administrative():
    facts = [
        extract_comchain_transaction_facts(
            source_rows()[0],
            native_currency_id="monnaie-test",
        )
    ]

    source, destination = (
        comchain_transaction_account_rows(facts[0])
    )

    assert source["account_id"] == "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    assert destination["account_id"] == "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"

    assert source["display_label"] is None
    assert source["native_owner_id"] is None
    assert source["native_account_type"] is None
    assert source["native_status"] is None
