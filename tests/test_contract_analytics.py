import sqlite3

from server.contract_store import (
    init_contract_tables,
    replace_partner_snapshot,
    replace_transaction_snapshot,
)
from server.contracts.partners_v1 import (
    PartnerContractRow,
)
from server.contracts.transactions_v1 import (
    TransactionContractRow,
)
from server.services.contract_analytics import (
    ContractAnalyticsError,
    get_contract_overview,
)


def _connection():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute(
        "PRAGMA foreign_keys = ON"
    )
    init_contract_tables(connection)
    return connection


def _tx(
    tx_hash,
    timestamp,
    sender,
    receiver,
):
    return TransactionContractRow(
        amount=100,
        received_at=timestamp,
        hash=tx_hash,
        fn_abi="method",
        type="transfer",
        sender_partner_id=sender,
        receiver_partner_id=receiver,
        is_sender_external=False,
        is_receiver_external=False,
    )


def _partner(
    partner_id,
    name,
):
    return PartnerContractRow(
        partner_id=partner_id,
        name=name,
        is_company=None,
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


def test_overview_counts_events_not_owner_rows():
    connection = _connection()

    with connection:
        replace_partner_snapshot(
            connection,
            (
                _partner(10, "Owner A"),
                _partner(20, "Owner B"),
                _partner(30, "Receiver"),
            ),
        )

        replace_transaction_snapshot(
            connection,
            (
                _tx(
                    "shared",
                    1786711751,
                    10,
                    30,
                ),
                _tx(
                    "shared",
                    1786711751,
                    20,
                    30,
                ),
            ),
        )

    result = get_contract_overview(
        connection
    )

    assert result["available"] is True

    assert (
        result["summary"][
            "transaction_count"
        ]
        == 1
    )

    assert (
        result["summary"][
            "referenced_partners"
        ]
        == 3
    )

    assert (
        result["summary"][
            "shared_transactions"
        ]
        == 1
    )

    assert (
        result["summary"][
            "shared_sides"
        ]
        == 1
    )

    assert len(
        result["daily"]
    ) == 1


def test_overview_period_filter():
    connection = _connection()

    with connection:
        replace_transaction_snapshot(
            connection,
            (
                _tx(
                    "day1",
                    1786711751,
                    None,
                    None,
                ),
                _tx(
                    "day2",
                    1786798151,
                    None,
                    None,
                ),
            ),
        )

    first = get_contract_overview(
        connection,
        start="2026-08-14",
        end="2026-08-14",
    )

    assert (
        first["summary"][
            "transaction_count"
        ]
        == 1
    )


def test_invalid_period_is_rejected():
    connection = _connection()

    try:
        get_contract_overview(
            connection,
            start="2026-09-10",
            end="2026-09-01",
        )
    except ContractAnalyticsError:
        pass
    else:
        raise AssertionError(
            "ContractAnalyticsError attendu"
        )
