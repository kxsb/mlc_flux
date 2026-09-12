from decimal import Decimal
import inspect

from server.providers import cyclos_facts
from server.providers.cyclos_facts import (
    extract_cyclos_actor_facts,
    extract_cyclos_transaction_facts,
)


def test_extract_gonette_actor_facts():
    actor = {
        "id": "account-123",
        "number": "P0001",
        "type": {
            "internalName": "comptepro",
            "name": "Compte professionnel",
        },
        "user": {
            "id": "user-456",
            "display": "P0001 - Boulangerie exemple",
        },
    }

    facts = extract_cyclos_actor_facts(actor)

    assert facts is not None
    assert facts.actor_id == "account-123"
    assert facts.actor_number == "P0001"
    assert facts.native_account_type == "comptepro"
    assert facts.user_id == "user-456"
    assert facts.user_display == "P0001 - Boulangerie exemple"


def test_extract_graine_actor_facts_without_interpreting_type():
    actor = {
        "id": "graine-account",
        "number": "external-reference",
        "type": {
            "internalName": "MonComptePro",
        },
        "user": {
            "id": "graine-user",
            "display": "Exemple",
        },
    }

    facts = extract_cyclos_actor_facts(actor)

    assert facts is not None
    assert facts.native_account_type == "MonComptePro"
    assert facts.actor_number == "external-reference"


def test_missing_actor_remains_missing():
    assert extract_cyclos_actor_facts(None) is None
    assert extract_cyclos_actor_facts(False) is None
    assert extract_cyclos_actor_facts("unexpected") is None


def test_extract_transaction_preserves_native_facts():
    transaction = {
        "id": "tx-internal-id",
        "transactionNumber": "TX-001",
        "date": "2026-01-12T10:15:00Z",
        "amount": "12.50",
        "currency": "unit",
        "kind": "payment",
        "creationType": "manual",
        "type": {
            "internalName": "internalPayment",
            "name": "Paiement",
        },
        "from": {
            "id": "source-account",
            "number": "U123",
            "type": {
                "internalName": "compteparticulier",
            },
            "user": {
                "id": "source-user",
                "display": "Utilisateur exemple",
            },
        },
        "to": {
            "id": "destination-account",
            "number": "P0001",
            "type": {
                "internalName": "comptepro",
            },
            "user": {
                "id": "destination-user",
                "display": "Professionnel exemple",
            },
        },
    }

    facts = extract_cyclos_transaction_facts(transaction)

    assert facts.transaction_id == "tx-internal-id"
    assert facts.transaction_number == "TX-001"
    assert facts.occurred_at == "2026-01-12T10:15:00Z"

    assert facts.native_currency_id == "unit"
    assert facts.amount_raw == "12.50"
    assert facts.amount_decimal == Decimal("12.50")

    assert facts.native_transaction_type == "internalPayment"
    assert facts.native_transaction_label == "Paiement"
    assert facts.native_transaction_group == "payment"

    assert facts.source_actor is not None
    assert facts.source_actor.actor_id == "source-account"

    assert facts.destination_actor is not None
    assert facts.destination_actor.actor_number == "P0001"


def test_creation_type_is_used_when_kind_is_missing():
    facts = extract_cyclos_transaction_facts({
        "id": "tx-2",
        "amount": "3,25",
        "creationType": "scheduled",
        "type": {
            "internalName": "transfer",
        },
        "from": None,
        "to": {
            "id": "destination",
            "type": {
                "internalName": "MonComptePro",
            },
        },
    })

    assert facts.amount_decimal == Decimal("3.25")
    assert facts.native_transaction_label == "transfer"
    assert facts.native_transaction_group == "scheduled"

    assert facts.source_actor is None
    assert facts.destination_actor is not None


def test_extractor_has_no_business_or_io_dependencies():
    source = inspect.getsource(cyclos_facts)

    forbidden = (
        "get_mlc_profile",
        "get_or_create_professional_ref",
        "get_or_create_private_ref",
        "requests.",
        "sqlite3",
        "get_connection",
    )

    for value in forbidden:
        assert value not in source

    actor_fields = set(
        cyclos_facts.CyclosActorFacts.__dataclass_fields__
    )
    transaction_fields = set(
        cyclos_facts.CyclosTransactionFacts.__dataclass_fields__
    )

    classification_fields = {
        "family",
        "actor_family",
        "from_family",
        "to_family",
        "label",
        "confidence",
        "reason",
    }

    assert actor_fields.isdisjoint(classification_fields)
    assert transaction_fields.isdisjoint(classification_fields)
