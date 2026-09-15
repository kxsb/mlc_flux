from types import SimpleNamespace

from server.sync_contracts import (
    _filter_referenced_partners,
    _referenced_partner_ids,
)


def test_referenced_partner_ids():
    transactions = (
        SimpleNamespace(
            sender_partner_id=10,
            receiver_partner_id=20,
        ),
        SimpleNamespace(
            sender_partner_id=10,
            receiver_partner_id=None,
        ),
        SimpleNamespace(
            sender_partner_id=None,
            receiver_partner_id=30,
        ),
    )

    assert _referenced_partner_ids(
        transactions
    ) == {10, 20, 30}


def test_filter_referenced_partners():
    transactions = (
        SimpleNamespace(
            sender_partner_id=10,
            receiver_partner_id=20,
        ),
    )

    partners = (
        SimpleNamespace(partner_id=10),
        SimpleNamespace(partner_id=20),
        SimpleNamespace(partner_id=30),
    )

    filtered = _filter_referenced_partners(
        transactions,
        partners,
    )

    assert [
        partner.partner_id
        for partner in filtered
    ] == [10, 20]


def test_filter_with_no_partner_references():
    transactions = (
        SimpleNamespace(
            sender_partner_id=None,
            receiver_partner_id=None,
        ),
    )

    partners = (
        SimpleNamespace(partner_id=10),
        SimpleNamespace(partner_id=20),
    )

    assert _filter_referenced_partners(
        transactions,
        partners,
    ) == ()
