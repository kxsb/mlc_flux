from decimal import Decimal, localcontext

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
        "native_transaction_type_name": "Paiement",
        "native_transaction_kind": "transfer",
        "native_creation_type": "manual",
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


def test_decimal_conversion_is_independent_from_ambient_context():
    with localcontext() as context:
        context.prec = 8

        row = cyclos_transaction_row(
            transaction(
                amount_raw="1234567.89",
                amount_decimal=Decimal("1234567.89"),
            ),
            currency_specs=SPECS,
        )

    assert row["amount_minor"] == 123456789


def test_very_small_subminor_fraction_is_rejected_without_rounding():
    with pytest.raises(
        CyclosTransactionError,
        match="précision supérieure",
    ):
        cyclos_transaction_row(
            transaction(
                amount_raw="1.00000000000000000000000000001",
                amount_decimal=Decimal(
                    "1.00000000000000000000000000001"
                ),
            ),
            currency_specs=SPECS,
        )


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
def test_non_finite_amount_is_rejected(value):
    with pytest.raises(
        CyclosTransactionError,
        match="non fini",
    ):
        cyclos_transaction_row(
            transaction(
                amount_raw=value,
                amount_decimal=Decimal(value),
            ),
            currency_specs=SPECS,
        )


def test_bigint_maximum_is_accepted():
    row = cyclos_transaction_row(
        transaction(
            amount_raw="92233720368547758.07",
            amount_decimal=Decimal("92233720368547758.07"),
        ),
        currency_specs=SPECS,
    )

    assert row["amount_minor"] == 9223372036854775807


def test_bigint_overflow_is_rejected():
    with pytest.raises(
        CyclosTransactionError,
        match="hors plage BIGINT",
    ):
        cyclos_transaction_row(
            transaction(
                amount_raw="92233720368547758.08",
                amount_decimal=Decimal("92233720368547758.08"),
            ),
            currency_specs=SPECS,
        )
