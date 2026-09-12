from decimal import Decimal
import inspect

import pytest

from server.providers import comchain_facts
from server.providers.comchain_facts import (
    ComChainFactsError,
    extract_comchain_transaction_facts,
)


def source_row(**overrides):
    values = {
        "hash": "0xAbCdEf1234",
        "block": 123456,
        "received_at": 1789234567,
        "caller": "0xCallerABC",
        "contract": "0xContractDEF",
        "contract_abi": "Currency",
        "type": "transfer",
        "sender": "0xSenderABC",
        "receiver": "ReceiverWithoutPrefix",
        "amount": 1250,
        "fn": "transfer",
        "fn_abi": "transfer(address,uint256)",
        "status": "",
    }
    values.update(overrides)
    return values


def test_extract_comchain_native_facts():
    facts = extract_comchain_transaction_facts(
        source_row(),
        native_currency_id="currency-example",
    )

    assert facts.transaction_hash == "0xAbCdEf1234"
    assert facts.block_number == 123456
    assert facts.received_at_epoch == 1789234567

    assert facts.native_currency_id == "currency-example"

    assert facts.caller == "0xCallerABC"
    assert facts.contract == "0xContractDEF"
    assert facts.contract_abi == "Currency"

    assert facts.native_transaction_type == "transfer"

    assert facts.sender == "0xSenderABC"
    assert facts.receiver == "ReceiverWithoutPrefix"

    assert facts.amount_raw == "1250"
    assert facts.amount_decimal == Decimal("1250")

    assert facts.function_name == "transfer"
    assert facts.function_abi == "transfer(address,uint256)"

    # pyc3l-cli 0.6.0 écrit actuellement une chaîne vide.
    # Elle reste un fait natif distinct d'un champ absent.
    assert facts.native_status == ""


def test_addresses_are_not_normalized():
    facts = extract_comchain_transaction_facts(
        source_row(
            sender="0xAbCdEf",
            receiver="ABCdef",
        ),
        native_currency_id="currency-example",
    )

    assert facts.sender == "0xAbCdEf"
    assert facts.receiver == "ABCdef"


def test_caller_and_sender_remain_distinct():
    facts = extract_comchain_transaction_facts(
        source_row(
            caller="0xDelegate",
            sender="0xAccountOwner",
        ),
        native_currency_id="currency-example",
    )

    assert facts.caller == "0xDelegate"
    assert facts.sender == "0xAccountOwner"


def test_currency_comes_from_store_context():
    row = source_row()
    assert "currency" not in row

    facts = extract_comchain_transaction_facts(
        row,
        native_currency_id="monnaie-a",
    )

    assert facts.native_currency_id == "monnaie-a"


def test_numeric_zero_is_preserved():
    facts = extract_comchain_transaction_facts(
        source_row(
            block=0,
            received_at=0,
            amount=0,
        ),
        native_currency_id="currency-example",
    )

    assert facts.block_number == 0
    assert facts.received_at_epoch == 0
    assert facts.amount_raw == "0"
    assert facts.amount_decimal == Decimal("0")


def test_binary_float_amount_is_rejected():
    with pytest.raises(
        ComChainFactsError,
        match="non exacte",
    ):
        extract_comchain_transaction_facts(
            source_row(amount=12.5),
            native_currency_id="currency-example",
        )


def test_invalid_block_is_rejected():
    with pytest.raises(
        ComChainFactsError,
        match="block.*non entier",
    ):
        extract_comchain_transaction_facts(
            source_row(block="not-a-block"),
            native_currency_id="currency-example",
        )


def test_non_mapping_transaction_is_rejected():
    with pytest.raises(
        ComChainFactsError,
        match="mapping attendu",
    ):
        extract_comchain_transaction_facts(
            "unexpected",
            native_currency_id="currency-example",
        )


def test_extractor_has_no_business_or_io_dependencies():
    source = inspect.getsource(comchain_facts)

    forbidden = (
        "get_mlc_profile",
        "get_or_create_professional_ref",
        "get_or_create_private_ref",
        "requests.",
        "sqlite3",
        "get_connection",
        "res_partner",
        "is_sender_external",
        "is_receiver_external",
    )

    for value in forbidden:
        assert value not in source

    fields = set(
        comchain_facts
        .ComChainTransactionFacts
        .__dataclass_fields__
    )

    classification_fields = {
        "family",
        "actor_family",
        "from_family",
        "to_family",
        "label",
        "confidence",
        "reason",
        "is_external",
    }

    assert fields.isdisjoint(classification_fields)
