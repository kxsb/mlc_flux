import pytest

from server.contracts.transactions_v1 import (
    CONTRACT_VERSION,
    TransactionContractError,
    normalize_transaction_rows,
    transaction_from_mapping,
)


def _row(
    tx_hash="tx-1",
    *,
    amount=100,
    received_at=1786711751,
    sender_partner_id=10,
    receiver_partner_id=20,
    sender_external=False,
    receiver_external=False,
):
    return {
        "amount": amount,
        "received_at": received_at,
        "hash": tx_hash,
        "fn_abi": "transfer",
        "type": "transfer",
        "sender_partner_id": sender_partner_id,
        "receiver_partner_id": receiver_partner_id,
        "is_sender_external": sender_external,
        "is_receiver_external": receiver_external,
    }


def test_contract_version():
    assert CONTRACT_VERSION == "TRANSACTIONS001"


def test_transaction_preserves_administrative_identity():
    tx = transaction_from_mapping(
        _row(
            sender_partner_id=43,
            receiver_partner_id=579,
        )
    )

    assert tx.hash == "tx-1"
    assert tx.amount == 100
    assert tx.sender_partner_id == 43
    assert tx.receiver_partner_id == 579


def test_external_side_can_have_no_partner():
    tx = transaction_from_mapping(
        _row(
            sender_partner_id=None,
            sender_external=True,
        )
    )

    assert tx.sender_partner_id is None
    assert tx.is_sender_external is True


def test_exact_duplicates_are_collapsed():
    row = _row()

    transactions = normalize_transaction_rows(
        [
            row,
            dict(row),
            dict(row),
        ]
    )

    assert len(transactions) == 1


def test_same_hash_can_have_multiple_sender_owners():
    first = _row(
        tx_hash="shared",
        sender_partner_id=10,
        receiver_partner_id=30,
    )

    second = _row(
        tx_hash="shared",
        sender_partner_id=20,
        receiver_partner_id=30,
    )

    transactions = normalize_transaction_rows(
        [
            first,
            second,
        ]
    )

    assert len(transactions) == 2

    assert {
        tx.sender_partner_id
        for tx in transactions
    } == {
        10,
        20,
    }


def test_same_hash_can_have_multiple_receiver_owners():
    first = _row(
        tx_hash="shared",
        sender_partner_id=10,
        receiver_partner_id=30,
    )

    second = _row(
        tx_hash="shared",
        sender_partner_id=10,
        receiver_partner_id=40,
    )

    transactions = normalize_transaction_rows(
        [
            first,
            second,
        ]
    )

    assert len(transactions) == 2

    assert {
        tx.receiver_partner_id
        for tx in transactions
    } == {
        30,
        40,
    }


def test_same_hash_with_different_amount_is_rejected():
    first = _row(
        tx_hash="same",
        amount=100,
    )

    second = _row(
        tx_hash="same",
        amount=200,
    )

    with pytest.raises(
        TransactionContractError,
        match="faits financiers divergents",
    ):
        normalize_transaction_rows(
            [
                first,
                second,
            ]
        )


def test_same_hash_with_different_timestamp_is_rejected():
    first = _row(
        tx_hash="same",
        received_at=1000,
    )

    second = _row(
        tx_hash="same",
        received_at=2000,
    )

    with pytest.raises(
        TransactionContractError,
        match="faits financiers divergents",
    ):
        normalize_transaction_rows(
            [
                first,
                second,
            ]
        )


def test_same_hash_with_different_external_flag_is_rejected():
    first = _row(
        tx_hash="same",
        sender_external=False,
    )

    second = _row(
        tx_hash="same",
        sender_external=True,
    )

    with pytest.raises(
        TransactionContractError,
        match="faits financiers divergents",
    ):
        normalize_transaction_rows(
            [
                first,
                second,
            ]
        )


def test_bad_boolean_is_rejected():
    row = _row()
    row["is_sender_external"] = 0

    with pytest.raises(
        TransactionContractError
    ):
        transaction_from_mapping(
            row
        )


def test_unknown_column_is_rejected():
    row = _row()
    row["wallet_address"] = "0xabc"

    with pytest.raises(
        TransactionContractError,
        match="Colonnes inconnues",
    ):
        transaction_from_mapping(
            row
        )


def test_missing_partner_does_not_imply_external():
    tx = transaction_from_mapping(
        _row(
            sender_partner_id=None,
            sender_external=False,
            receiver_partner_id=None,
            receiver_external=False,
        )
    )

    assert tx.sender_partner_id is None
    assert tx.receiver_partner_id is None
    assert tx.is_sender_external is False
    assert tx.is_receiver_external is False
