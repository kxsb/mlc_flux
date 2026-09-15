from sqlalchemy import create_engine

from server.financial_core.publication import (
    validate_and_publish_financial_core,
)
from server.financial_core.reader import (
    read_current_financial_core,
)
from server.financial_core.schema import metadata
from server.providers.comchain_financial_core import (
    ComChainFinancialCoreSpec,
    build_comchain_financial_core_batch,
)
from server.providers.comchain_financial_core_bridge import (
    build_comchain_financial_core_payload,
)


SPEC = ComChainFinancialCoreSpec(
    native_currency_id="test-native",
    unit_code="TEST",
    unit_exponent=2,
    monetary_dimension="unqualified",
)


def _row(tx_hash, sender, receiver, amount):
    return {
        "hash": tx_hash,
        "block": 5000000,
        "received_at": 1786711751,
        "caller": sender,
        "contract": "0xcontract",
        "contract_abi": "LEM-2",
        "type": "transfer",
        "sender": sender,
        "receiver": receiver,
        "amount": amount,
        "fn": "a5f7c148",
        "fn_abi": "nantTransfer",
        "status": "",
    }


def test_comchain_batch_can_be_published_and_read_back():
    a = "0x" + "aa" * 20
    b = "0x" + "bb" * 20
    c = "0x" + "cc" * 20

    batch = build_comchain_financial_core_batch(
        [
            _row("0xtx1", a, b, 100),
            _row("0xtx2", a, c, 250),
        ],
        spec=SPEC,
    )

    payload = build_comchain_financial_core_payload(
        batch,
        spec=SPEC,
        dataset_id="comchain-test",
        publication_id="publication-1",
        source_instance_id="test-instance",
        source_cursor="5000000",
        source_snapshot_ref="fixture",
    )

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
    )

    metadata.create_all(engine)

    publication_id = validate_and_publish_financial_core(
        engine,
        payload,
    )

    assert publication_id == "publication-1"

    snapshot = read_current_financial_core(
        engine,
        "comchain-test",
    )

    assert snapshot.publication_id == "publication-1"
    assert len(snapshot.accounts) == 3
    assert len(snapshot.events) == 2
    assert len(snapshot.account_effects) == 4

    assert {
        event["native_event_subtype"]
        for event in snapshot.events
    } == {"nantTransfer"}

    assert sorted(
        effect["amount_minor"]
        for effect in snapshot.account_effects
    ) == [-250, -100, 100, 250]


def test_bridge_does_not_create_odoo_entities():
    a = "0x" + "aa" * 20
    b = "0x" + "bb" * 20

    batch = build_comchain_financial_core_batch(
        [_row("0xtx1", a, b, 100)],
        spec=SPEC,
    )

    payload = build_comchain_financial_core_payload(
        batch,
        spec=SPEC,
        dataset_id="comchain-test",
        publication_id="publication-1",
        source_instance_id="test-instance",
    )

    assert list(payload.actors) == []
    assert list(payload.identity_links) == []
