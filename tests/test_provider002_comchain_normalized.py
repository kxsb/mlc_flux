import inspect

import pytest

from server.providers import comchain_normalized
from server.providers.comchain_facts import (
    extract_comchain_transaction_facts,
)
from server.providers.comchain_normalized import (
    ComChainIdentityError,
    comchain_account_row,
    comchain_transaction_account_rows,
)


def facts(**overrides):
    row = {
        "hash": "0xTx",
        "block": 123,
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
    row.update(overrides)

    return extract_comchain_transaction_facts(
        row,
        native_currency_id="currency-example",
    )


def test_comchain_account_identity_is_native_endpoint():
    row = comchain_account_row("0xAbCdEf")

    assert row is not None
    assert row["account_id"] == "0xAbCdEf"
    assert row["source_system"] == "comchain"

    assert row["native_account_number"] is None
    assert row["native_account_type"] is None
    assert row["native_status"] is None
    assert row["display_label"] is None
    assert row["native_owner_id"] is None


def test_comchain_identity_preserves_case_and_prefix():
    prefixed = comchain_account_row("0xAbCdEf")
    unprefixed = comchain_account_row("AbCdEf")
    other_case = comchain_account_row("0xabcdef")

    assert prefixed["account_id"] == "0xAbCdEf"
    assert unprefixed["account_id"] == "AbCdEf"
    assert other_case["account_id"] == "0xabcdef"

    assert prefixed["account_id"] != unprefixed["account_id"]
    assert prefixed["account_id"] != other_case["account_id"]


def test_missing_endpoint_remains_missing():
    assert comchain_account_row(None) is None


def test_empty_endpoint_fails_closed():
    for value in ("", "   "):
        with pytest.raises(
            ComChainIdentityError,
            match="vide",
        ):
            comchain_account_row(value)


def test_sender_and_receiver_become_financial_accounts():
    source, destination = comchain_transaction_account_rows(
        facts()
    )

    assert source is not None
    assert destination is not None

    assert source["account_id"] == "0xSenderAbC"
    assert destination["account_id"] == "ReceiverDEF"


def test_caller_is_not_used_as_owner_or_account_identity():
    transaction = facts(
        caller="0xDelegate",
        sender="0xOwner",
    )

    source, _ = comchain_transaction_account_rows(
        transaction
    )

    assert source["account_id"] == "0xOwner"
    assert source["native_owner_id"] is None
    assert transaction.caller == "0xDelegate"


def test_admin_sentinel_is_not_silently_dropped_or_classified():
    source, _ = comchain_transaction_account_rows(
        facts(sender="admin")
    )

    assert source is not None
    assert source["account_id"] == "admin"
    assert source["native_account_type"] is None


def test_normalizer_has_no_odoo_or_business_dependencies():
    source = inspect.getsource(comchain_normalized)

    forbidden = (
        "res_partner",
        "comchain_id",
        "is_sender_external",
        "is_receiver_external",
        "get_mlc_profile",
        "family",
        "lower(",
        "lstrip(",
        "removeprefix(",
    )

    for value in forbidden:
        assert value not in source
