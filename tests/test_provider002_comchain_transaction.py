from datetime import UTC, datetime
from decimal import Decimal

import pytest

from server.providers.comchain_facts import (
    extract_comchain_transaction_facts,
)
from server.providers.comchain_normalized import (
    ComChainCurrencySpec,
    ComChainTransactionError,
    comchain_transaction_row,
)


def transaction(**overrides):
    values = {
        "hash": "0xTransactionABC",
        "block": 123456,
        "received_at": 1789234567,
        "caller": "0xDelegate",
        "contract": "0xContract",
        "contract_abi": "Currency",
        "type": "transfer",
        "sender": "0xSenderAbC",
        "receiver": "ReceiverDEF",
        "amount": 1250,
        "fn": "transfer",
        "fn_abi": "transfer(address,uint256)",
        "status": "",
    }
    values.update(overrides)

    return extract_comchain_transaction_facts(
        values,
        native_currency_id="currency-example",
    )


SPECS = {
    "currency-example": ComChainCurrencySpec(
        native_currency_id="currency-example",
        currency_code="LOCAL",
        currency_exponent=2,
        amount_representation="minor",
    )
}


def test_transaction_normalizes_to_input001():
    facts = transaction()

    row = comchain_transaction_row(
        facts,
        currency_specs=SPECS,
    )

    assert row["transaction_id"] == "0xTransactionABC"
    assert row["native_transaction_number"] is None

    assert row["source_account_id"] == "0xSenderAbC"
    assert row["destination_account_id"] == "ReceiverDEF"

    assert row["native_currency_id"] == "currency-example"
    assert row["currency_code"] == "LOCAL"
    assert row["currency_exponent"] == 2

    assert row["native_transaction_type"] == "transfer"


def test_native_minor_amount_is_not_scaled_again():
    row = comchain_transaction_row(
        transaction(amount=1250),
        currency_specs=SPECS,
    )

    # 1250 unités minimales reste 1250.
    # On ne fait surtout pas 1250 * 100.
    assert row["amount_minor"] == 1250


def test_received_at_epoch_becomes_utc_instant():
    facts = transaction(received_at=0)

    row = comchain_transaction_row(
        facts,
        currency_specs=SPECS,
    )

    assert row["occurred_at"] == datetime(
        1970, 1, 1, tzinfo=UTC
    )


def test_caller_is_not_used_as_financial_endpoint():
    facts = transaction(
        caller="0xDelegate",
        sender="0xActualSender",
    )

    row = comchain_transaction_row(
        facts,
        currency_specs=SPECS,
    )

    assert row["source_account_id"] == "0xActualSender"
    assert facts.caller == "0xDelegate"


def test_native_block_and_function_facts_remain_available():
    facts = transaction(
        block=987654,
        fn="delegatedTransfer",
    )

    row = comchain_transaction_row(
        facts,
        currency_specs=SPECS,
    )

    # Ils ne sont pas artificiellement projetés dans des champs
    # génériques INPUT001, mais ne sont pas perdus par le provider.
    assert facts.block_number == 987654
    assert facts.function_name == "delegatedTransfer"

    assert row["native_transaction_label"] is None
    assert row["native_transaction_group"] is None


def test_missing_hash_is_rejected():
    with pytest.raises(
        ComChainTransactionError,
        match="sans hash",
    ):
        comchain_transaction_row(
            transaction(hash=None),
            currency_specs=SPECS,
        )


def test_missing_block_is_rejected():
    with pytest.raises(
        ComChainTransactionError,
        match="sans numéro de bloc",
    ):
        comchain_transaction_row(
            transaction(block=None),
            currency_specs=SPECS,
        )


def test_unknown_currency_is_rejected():
    facts = extract_comchain_transaction_facts(
        {
            "hash": "0xTx",
            "block": 1,
            "received_at": 1,
            "sender": "A",
            "receiver": "B",
            "amount": 100,
        },
        native_currency_id="unknown",
    )

    with pytest.raises(
        ComChainTransactionError,
        match="Devise ComChain inconnue",
    ):
        comchain_transaction_row(
            facts,
            currency_specs=SPECS,
        )


def test_fractional_minor_amount_is_rejected():
    with pytest.raises(
        ComChainTransactionError,
        match="unité minimale.*pas entier",
    ):
        comchain_transaction_row(
            transaction(amount=Decimal("12.5")),
            currency_specs=SPECS,
        )


def test_bigint_maximum_is_accepted():
    row = comchain_transaction_row(
        transaction(
            amount=Decimal("9223372036854775807")
        ),
        currency_specs=SPECS,
    )

    assert row["amount_minor"] == 9223372036854775807


def test_bigint_overflow_is_rejected():
    with pytest.raises(
        ComChainTransactionError,
        match="hors plage BIGINT",
    ):
        comchain_transaction_row(
            transaction(
                amount=Decimal("9223372036854775808")
            ),
            currency_specs=SPECS,
        )


def test_major_unit_representation_is_not_assumed():
    specs = {
        "currency-example": ComChainCurrencySpec(
            native_currency_id="currency-example",
            currency_code="LOCAL",
            currency_exponent=2,
            amount_representation="major",
        )
    }

    with pytest.raises(
        ComChainTransactionError,
        match="Représentation monétaire.*non supportée",
    ):
        comchain_transaction_row(
            transaction(amount=Decimal("12.50")),
            currency_specs=specs,
        )
