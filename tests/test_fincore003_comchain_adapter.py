from server.providers.comchain_financial_core import (
    ComChainFinancialCoreSpec,
    build_comchain_financial_core_batch,
)


SPEC = ComChainFinancialCoreSpec(
    native_currency_id="test-native",
    unit_code="TEST",
    unit_exponent=2,
    monetary_dimension="unqualified",
)


def _row(
    tx_hash,
    sender,
    receiver,
    amount,
    *,
    fn="a5f7c148",
    fn_abi="nantTransfer",
):
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
        "fn": fn,
        "fn_abi": fn_abi,
        "status": "",
    }


def test_one_native_transfer_becomes_one_event_two_effects():
    sender = "0x" + "aa" * 20
    receiver = "0x" + "bb" * 20

    batch = build_comchain_financial_core_batch(
        [_row("0xtx1", sender, receiver, 725)],
        spec=SPEC,
    )

    assert len(batch.accounts) == 2
    assert len(batch.events) == 1
    assert len(batch.account_effects) == 2

    event = batch.events[0]

    assert event["event_id"] == "0xtx1"
    assert event["event_kind"] == "native_transfer"
    assert event["native_event_subtype"] == "nantTransfer"
    assert event["execution_state"] == "unknown"
    assert event["native_status"] == ""

    amounts = sorted(
        effect["amount_minor"]
        for effect in batch.account_effects
    )

    assert amounts == [-725, 725]


def test_on_behalf_keeps_native_method_without_business_classification():
    sender = "0x" + "11" * 20
    receiver = "0x" + "22" * 20

    batch = build_comchain_financial_core_batch(
        [
            _row(
                "0xtx2",
                sender,
                receiver,
                10000,
                fn="1b6b1ee5",
                fn_abi="transferNantOnBehalf",
            )
        ],
        spec=SPEC,
    )

    event = batch.events[0]

    assert event["event_kind"] == "native_transfer"
    assert (
        event["native_event_subtype"]
        == "transferNantOnBehalf"
    )

    assert "payment" not in event["event_kind"]
    assert "conversion" not in event["event_kind"]


def test_repeated_address_is_one_account_not_one_actor():
    a = "0x" + "aa" * 20
    b = "0x" + "bb" * 20
    c = "0x" + "cc" * 20

    batch = build_comchain_financial_core_batch(
        [
            _row("0xtx1", a, b, 100),
            _row("0xtx2", a, c, 200),
        ],
        spec=SPEC,
    )

    assert len(batch.accounts) == 3
    assert len(batch.events) == 2
    assert len(batch.account_effects) == 4

    for account in batch.accounts:
        assert account["native_owner_id"] is None


def test_native_provenance_keeps_contract_and_function():
    sender = "0x" + "aa" * 20
    receiver = "0x" + "bb" * 20

    batch = build_comchain_financial_core_batch(
        [_row("0xtx1", sender, receiver, 100)],
        spec=SPEC,
    )

    raw = batch.events[0]["native_attributes_json"]

    assert '"contract_abi":"LEM-2"' in raw
    assert '"fn_abi":"nantTransfer"' in raw
    assert '"status":""' in raw
