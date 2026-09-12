from decimal import Decimal

import pytest

from server.providers.cyclos_facts import (
    CyclosActorFacts,
    CyclosTransactionFacts,
)
from server.providers.cyclos_normalized import (
    CyclosCurrencySpec,
    CyclosTransactionError,
    cyclos_transaction_row,
)


def actor(actor_id):
    return CyclosActorFacts(
        actor_id=actor_id,
        actor_number=None,
        native_account_type="monCompte",
        user_id="owner-" + actor_id,
        user_display=None,
    )


def transaction(**overrides):
    values = {
        "transaction_id": "tx-123",
        "transaction_number": "TX-2026-123",
        "occurred_at": "2026-09-12T14:30:00Z",
        "native_currency_id": "graine34",
        "amount_raw": "12.50",
        "amount_decimal": Decimal("12.50"),
        "native_transaction_type": "payment",
        "native_transaction_label": "Paiement",
        "native_transaction_group": "transfer",
        "source_actor": actor("account-a"),
        "destination_actor": actor("account-b"),
    }
    values.update(overrides)
    return CyclosTransactionFacts(**values)


SPECS = {
    "graine34": CyclosCurrencySpec(
        native_currency_id="graine34",
        currency_code="graine",
        currency_exponent=2,
    )
}


def test_transaction_normalizes_without_losing_native_facts():
    row = cyclos_transaction_row(
        transaction(),
        currency_specs=SPECS,
    )

    assert row["transaction_id"] == "tx-123"
    assert row["native_transaction_number"] == "TX-2026-123"

    assert row["source_account_id"] == "account-a"
    assert row["destination_account_id"] == "account-b"

    assert row["amount_minor"] == 1250

    assert row["native_currency_id"] == "graine34"
    assert row["currency_code"] == "graine"
    assert row["currency_exponent"] == 2

    assert row["occurred_at"].tzinfo is not None

    assert row["native_transaction_type"] == "payment"
    assert row["native_transaction_label"] == "Paiement"
    assert row["native_transaction_group"] == "transfer"


def test_missing_actor_remains_null_endpoint():
    row = cyclos_transaction_row(
        transaction(source_actor=None),
        currency_specs=SPECS,
    )

    assert row["source_account_id"] is None
    assert row["destination_account_id"] == "account-b"


def test_currency_native_id_is_not_used_as_normalized_code():
    row = cyclos_transaction_row(
        transaction(),
        currency_specs=SPECS,
    )

    assert row["native_currency_id"] == "graine34"
    assert row["currency_code"] == "graine"


def test_unknown_native_currency_fails_closed():
    with pytest.raises(
        CyclosTransactionError,
        match="Devise Cyclos inconnue",
    ):
        cyclos_transaction_row(
            transaction(native_currency_id="unexpected"),
            currency_specs=SPECS,
        )


def test_subminor_precision_is_rejected():
    with pytest.raises(
        CyclosTransactionError,
        match="précision supérieure",
    ):
        cyclos_transaction_row(
            transaction(
                amount_raw="1.001",
                amount_decimal=Decimal("1.001"),
            ),
            currency_specs=SPECS,
        )


def test_missing_transaction_id_is_rejected():
    with pytest.raises(
        CyclosTransactionError,
        match="transaction.id",
    ):
        cyclos_transaction_row(
            transaction(transaction_id=None),
            currency_specs=SPECS,
        )


def test_naive_datetime_is_rejected():
    with pytest.raises(
        CyclosTransactionError,
        match="sans fuseau",
    ):
        cyclos_transaction_row(
            transaction(
                occurred_at="2026-09-12T14:30:00"
            ),
            currency_specs=SPECS,
        )
