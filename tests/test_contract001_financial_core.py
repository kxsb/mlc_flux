import json

from sqlalchemy import create_engine

from server.contracts.transactions_v1 import (
    normalize_transaction_rows,
)
from server.contracts.transactions_financial_core import (
    TransactionFinancialCoreSpec,
    build_transaction_contract_payload,
)
from server.financial_core.publication import (
    validate_and_publish_financial_core,
)
from server.financial_core.reader import (
    read_current_financial_core,
)
from server.financial_core.schema import metadata


def _row(
    tx_hash,
    sender,
    receiver,
    *,
    sender_external=False,
    receiver_external=False,
):
    return {
        "amount": 100,
        "received_at": 1786711751,
        "hash": tx_hash,
        "fn_abi": "native-operation-code",
        "type": "transfer",
        "sender_partner_id": sender,
        "receiver_partner_id": receiver,
        "is_sender_external": sender_external,
        "is_receiver_external": receiver_external,
    }


def test_contract_projects_without_fabricating_persistent_accounts():
    transactions = normalize_transaction_rows([
        _row("tx1", 10, 20),
        _row("tx2", 10, None),
    ])

    payload = build_transaction_contract_payload(
        transactions,
        spec=TransactionFinancialCoreSpec(
            unit_code="TEST",
            unit_exponent=2,
            monetary_dimension="local_currency",
        ),
        dataset_id="test",
        publication_id="p1",
        source_instance_id="fixture",
    )

    assert len(payload.events) == 2
    assert len(payload.effects) == 4

    # Deux endpoints par transaction, même si le partenaire se répète.
    assert len(payload.accounts) == 4

    # Les acteurs administratifs, eux, sont dédupliqués.
    assert {
        actor["native_actor_id"]
        for actor in payload.actors
    } == {"10", "20"}


def test_fn_abi_is_preserved_as_native_operation_subtype():
    transactions = normalize_transaction_rows([
        _row("tx1", 10, 20),
    ])

    payload = build_transaction_contract_payload(
        transactions,
        spec=TransactionFinancialCoreSpec(
            unit_code="TEST",
            unit_exponent=2,
            monetary_dimension="local_currency",
        ),
        dataset_id="test",
        publication_id="p1",
        source_instance_id="fixture",
    )

    event = payload.events[0]

    assert event["native_event_type"] == "transfer"
    assert (
        event["native_event_subtype"]
        == "native-operation-code"
    )


def test_null_partner_and_external_are_preserved_independently():
    transactions = normalize_transaction_rows([
        _row(
            "tx1",
            None,
            None,
            sender_external=False,
            receiver_external=True,
        ),
    ])

    payload = build_transaction_contract_payload(
        transactions,
        spec=TransactionFinancialCoreSpec(
            unit_code="TEST",
            unit_exponent=2,
            monetary_dimension="local_currency",
        ),
        dataset_id="test",
        publication_id="p1",
        source_instance_id="fixture",
    )

    assert payload.actors == []
    assert payload.identity_links == []

    attrs = [
        json.loads(account["native_attributes_json"])
        for account in payload.accounts
    ]

    assert attrs[0]["partner_id"] is None
    assert attrs[0]["is_external"] is False
    assert attrs[1]["partner_id"] is None
    assert attrs[1]["is_external"] is True


def test_contract_payload_publishes_and_reads():
    transactions = normalize_transaction_rows([
        _row("tx1", 10, 20),
    ])

    payload = build_transaction_contract_payload(
        transactions,
        spec=TransactionFinancialCoreSpec(
            unit_code="TEST",
            unit_exponent=2,
            monetary_dimension="local_currency",
        ),
        dataset_id="test",
        publication_id="p1",
        source_instance_id="fixture",
    )

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
    )

    metadata.create_all(engine)

    validate_and_publish_financial_core(
        engine,
        payload,
    )

    snapshot = read_current_financial_core(
        engine,
        "test",
    )

    assert len(snapshot.events) == 1
    assert len(snapshot.account_effects) == 2
    assert len(snapshot.actors) == 2
    assert len(snapshot.identity_links) == 2
