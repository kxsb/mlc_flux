import sqlite3

from server.contract_store import (
    init_contract_tables,
    record_contract_state,
    replace_partner_snapshot,
    replace_transaction_snapshot,
)
from server.contracts.partners_v1 import (
    PartnerContractRow,
)
from server.contracts.transactions_v1 import (
    TransactionContractRow,
)


def _connection():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute(
        "PRAGMA foreign_keys = ON"
    )
    init_contract_tables(connection)
    return connection


def _transaction(
    tx_hash,
    *,
    amount=100,
    sender=10,
    receiver=20,
    sender_external=False,
    receiver_external=False,
):
    return TransactionContractRow(
        amount=amount,
        received_at=1000,
        hash=tx_hash,
        fn_abi="nativeMethod",
        type="transfer",
        sender_partner_id=sender,
        receiver_partner_id=receiver,
        is_sender_external=sender_external,
        is_receiver_external=receiver_external,
    )


def _partner(
    partner_id,
    *,
    name=None,
    is_company=None,
):
    return PartnerContractRow(
        partner_id=partner_id,
        name=name,
        is_company=is_company,
        member_type=None,
        industry_code=None,
        industry_name=None,
        siret=None,
        siren=None,
        legal_activity_code=None,
        city=None,
        zip=None,
        latitude=None,
        longitude=None,
        active=None,
        is_published=None,
    )


def test_transaction_snapshot_replaces_previous_rows():
    connection = _connection()

    with connection:
        replace_transaction_snapshot(
            connection,
            (
                _transaction("tx-1"),
            ),
        )

    with connection:
        count = replace_transaction_snapshot(
            connection,
            (
                _transaction("tx-2"),
            ),
        )

    assert count == 1

    rows = connection.execute(
        """
        SELECT hash
        FROM contract001_transactions
        ORDER BY hash
        """
    ).fetchall()

    assert [
        row["hash"]
        for row in rows
    ] == [
        "tx-2",
    ]


def test_shared_owner_creates_one_event_and_many_links():
    connection = _connection()

    rows = (
        _transaction(
            "shared",
            sender=10,
            receiver=30,
        ),
        _transaction(
            "shared",
            sender=20,
            receiver=30,
        ),
    )

    with connection:
        count = replace_transaction_snapshot(
            connection,
            rows,
        )

    assert count == 1

    event_count = connection.execute(
        """
        SELECT COUNT(*)
        FROM contract001_transactions
        """
    ).fetchone()[0]

    links = connection.execute(
        """
        SELECT side, partner_id
        FROM contract001_transaction_partners
        WHERE hash = 'shared'
        ORDER BY side, partner_id
        """
    ).fetchall()

    assert event_count == 1

    assert [
        tuple(row)
        for row in links
    ] == [
        ("receiver", 30),
        ("sender", 10),
        ("sender", 20),
    ]


def test_event_context_never_multiplies_transaction():
    connection = _connection()

    with connection:
        replace_transaction_snapshot(
            connection,
            (
                _transaction(
                    "shared",
                    sender=10,
                    receiver=30,
                ),
                _transaction(
                    "shared",
                    sender=20,
                    receiver=30,
                ),
            ),
        )

    rows = connection.execute(
        """
        SELECT *
        FROM contract_transaction_context_v1
        """
    ).fetchall()

    assert len(rows) == 1

    row = rows[0]

    assert row["transaction_id"] == "shared"
    assert row["amount_minor"] == 100
    assert row["sender_partner_count"] == 2
    assert row["receiver_partner_count"] == 1


def test_partner_context_expands_only_associations():
    connection = _connection()

    with connection:
        replace_partner_snapshot(
            connection,
            (
                _partner(
                    10,
                    name="Owner A",
                ),
                _partner(
                    20,
                    name="Owner B",
                ),
                _partner(
                    30,
                    name="Receiver",
                ),
            ),
        )

        replace_transaction_snapshot(
            connection,
            (
                _transaction(
                    "shared",
                    sender=10,
                    receiver=30,
                ),
                _transaction(
                    "shared",
                    sender=20,
                    receiver=30,
                ),
            ),
        )

    rows = connection.execute(
        """
        SELECT
            transaction_id,
            side,
            partner_id,
            partner_name
        FROM contract_transaction_partner_context_v1
        ORDER BY side, partner_id
        """
    ).fetchall()

    assert len(rows) == 3

    assert [
        tuple(row)
        for row in rows
    ] == [
        (
            "shared",
            "receiver",
            30,
            "Receiver",
        ),
        (
            "shared",
            "sender",
            10,
            "Owner A",
        ),
        (
            "shared",
            "sender",
            20,
            "Owner B",
        ),
    ]


def test_missing_partner_profile_is_preserved():
    connection = _connection()

    with connection:
        replace_transaction_snapshot(
            connection,
            (
                _transaction(
                    "tx",
                    sender=10,
                    receiver=None,
                ),
            ),
        )

    row = connection.execute(
        """
        SELECT
            partner_id,
            partner_profile_resolved
        FROM contract_transaction_partner_context_v1
        """
    ).fetchone()

    assert row["partner_id"] == 10
    assert row["partner_profile_resolved"] == 0


def test_partner_snapshot_preserves_nullable_boolean():
    connection = _connection()

    partner = PartnerContractRow(
        partner_id=10,
        name="Test",
        is_company=False,
        member_type=None,
        industry_code=None,
        industry_name=None,
        siret=None,
        siren=None,
        legal_activity_code=None,
        city=None,
        zip=None,
        latitude=0.0,
        longitude=0.0,
        active=None,
        is_published=False,
    )

    with connection:
        count = replace_partner_snapshot(
            connection,
            (partner,),
        )

    assert count == 1

    row = connection.execute(
        """
        SELECT *
        FROM contract002_partners
        WHERE partner_id = 10
        """
    ).fetchone()

    assert row["is_company"] == 0
    assert row["latitude"] == 0.0
    assert row["longitude"] == 0.0
    assert row["active"] is None
    assert row["is_published"] == 0


def test_runtime_state_upsert():
    connection = _connection()

    with connection:
        record_contract_state(
            connection,
            contract_name="transactions",
            contract_version="TRANSACTIONS001",
            row_count=3,
            source_instance_id="test-source",
            source_ref=(
                "postgresql:public.transactions_test"
            ),
        )

        record_contract_state(
            connection,
            contract_name="transactions",
            contract_version="TRANSACTIONS001",
            row_count=5,
            source_instance_id="test-source",
            source_ref=(
                "postgresql:public.transactions_test"
            ),
        )

    row = connection.execute(
        """
        SELECT
            contract_version,
            status,
            source_instance_id,
            source_ref,
            row_count
        FROM contract_runtime_state
        WHERE contract_name = 'transactions'
        """
    ).fetchone()

    assert tuple(row) == (
        "TRANSACTIONS001",
        "available",
        "test-source",
        "postgresql:public.transactions_test",
        5,
    )
