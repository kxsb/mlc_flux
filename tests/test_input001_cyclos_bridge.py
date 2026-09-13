from datetime import UTC, datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine

from server.input_contract.reader import FinancialContractReader
from server.input_contract.writer import materialize_financial_dataset
from server.providers import cyclos_dataset
from server.providers.cyclos_dataset import (
    CyclosDatasetError,
    build_cyclos_financial_dataset,
)
from server.providers.cyclos_normalized import CyclosCurrencySpec


SPECS = {
    "graine34": CyclosCurrencySpec(
        native_currency_id="graine34",
        currency_code="GRAINE",
        currency_exponent=2,
    )
}


def actor(
    actor_id,
    *,
    number=None,
    account_type="monCompte",
    user_id=None,
    display=None,
):
    return {
        "id": actor_id,
        "number": number,
        "type": {
            "internalName": account_type,
        },
        "user": {
            "id": user_id,
            "display": display,
        },
    }


def transaction(
    tx_id,
    *,
    source=None,
    destination=None,
    amount="12.50",
    date="2026-09-12T14:30:00Z",
):
    return {
        "id": tx_id,
        "transactionNumber": f"N-{tx_id}",
        "date": date,
        "currency": "graine34",
        "amount": amount,
        "kind": "transfer",
        "creationType": "manual",
        "type": {
            "internalName": "payment",
            "name": "Paiement",
        },
        "from": source,
        "to": destination,
    }


def raw_dataset():
    account_a = actor(
        "account-a",
        user_id="user-a",
        display="Alice",
    )
    account_b = actor(
        "account-b",
        number="P0001",
        account_type="MonComptePro",
        user_id="user-b",
        display="P0001 - Commerce",
    )
    account_c = actor(
        "account-c",
        user_id="user-c",
        display="Claire",
    )

    return [
        transaction(
            "tx-001",
            source=account_a,
            destination=account_b,
            amount="12.50",
        ),
        transaction(
            "tx-002",
            source=account_b,
            destination=account_c,
            amount="2.75",
            date="2026-09-12T15:00:00+00:00",
        ),
    ]


def test_builds_complete_cyclos_payload():
    payload = build_cyclos_financial_dataset(
        raw_dataset(),
        dataset_id="graine-reference",
        currency_specs=SPECS,
    )

    assert payload.dataset_metadata["source_system"] == "cyclos"
    assert payload.dataset_metadata["contract_version"] == "input001-v0.1"

    assert payload.dataset_metadata["account_state_history"] is False
    assert payload.dataset_metadata["balances"] is False
    assert payload.dataset_metadata["account_replacements"] is False

    assert [
        row["account_id"]
        for row in payload.accounts
    ] == [
        "account-a",
        "account-b",
        "account-c",
    ]

    assert len(payload.transactions) == 2
    assert payload.transactions[0]["amount_minor"] == 1250
    assert payload.transactions[1]["amount_minor"] == 275


def test_shared_account_is_deduplicated_and_enriched():
    rows = raw_dataset()

    # Première observation partielle du compte B.
    rows[0]["to"] = actor(
        "account-b",
        account_type="MonComptePro",
        user_id=None,
        display=None,
    )

    payload = build_cyclos_financial_dataset(
        rows,
        dataset_id="merge-reference",
        currency_specs=SPECS,
    )

    account_b = next(
        row
        for row in payload.accounts
        if row["account_id"] == "account-b"
    )

    # La seconde observation complète les champs absents.
    assert account_b["native_account_number"] == "P0001"
    assert account_b["native_owner_id"] == "user-b"
    assert account_b["display_label"] == "P0001 - Commerce"


def test_conflicting_native_account_fact_fails_closed():
    rows = raw_dataset()

    rows[1]["from"] = actor(
        "account-b",
        number="P9999",
        account_type="MonComptePro",
        user_id="user-b",
        display="P0001 - Commerce",
    )

    with pytest.raises(
        CyclosDatasetError,
        match="fait natif contradictoire.*native_account_number",
    ):
        build_cyclos_financial_dataset(
            rows,
            dataset_id="conflict-reference",
            currency_specs=SPECS,
        )


def test_missing_actor_stays_null_without_inventing_account():
    rows = [
        transaction(
            "tx-missing-source",
            source=None,
            destination=actor("account-b"),
        )
    ]

    payload = build_cyclos_financial_dataset(
        rows,
        dataset_id="missing-actor-reference",
        currency_specs=SPECS,
    )

    assert [
        row["account_id"]
        for row in payload.accounts
    ] == ["account-b"]

    tx = payload.transactions[0]

    assert tx["source_account_id"] is None
    assert tx["destination_account_id"] == "account-b"


def test_duplicate_transaction_id_is_rejected_before_sql():
    rows = raw_dataset()
    rows[1]["id"] = "tx-001"

    with pytest.raises(
        CyclosDatasetError,
        match="dupliquée",
    ):
        build_cyclos_financial_dataset(
            rows,
            dataset_id="duplicate-reference",
            currency_specs=SPECS,
        )


def test_coverage_is_explicit_not_inferred():
    payload = build_cyclos_financial_dataset(
        raw_dataset(),
        dataset_id="coverage-none",
        currency_specs=SPECS,
    )

    assert payload.dataset_metadata["coverage_from"] is None
    assert payload.dataset_metadata["coverage_to"] is None

    plus_two = timezone(timedelta(hours=2))

    payload = build_cyclos_financial_dataset(
        raw_dataset(),
        dataset_id="coverage-explicit",
        currency_specs=SPECS,
        coverage_from=datetime(
            2026, 9, 1, 0, 0, tzinfo=plus_two
        ),
        coverage_to=datetime(
            2026, 9, 13, 0, 0, tzinfo=plus_two
        ),
        snapshot_ref="cyclos-export-reference",
    )

    assert payload.dataset_metadata["coverage_from"] == datetime(
        2026, 8, 31, 22, 0, tzinfo=UTC
    )
    assert payload.dataset_metadata["coverage_to"] == datetime(
        2026, 9, 12, 22, 0, tzinfo=UTC
    )
    assert (
        payload.dataset_metadata["snapshot_ref"]
        == "cyclos-export-reference"
    )


def test_naive_coverage_is_rejected():
    with pytest.raises(
        CyclosDatasetError,
        match="coverage_from.*timezone-aware",
    ):
        build_cyclos_financial_dataset(
            raw_dataset(),
            dataset_id="bad-coverage",
            currency_specs=SPECS,
            coverage_from=datetime(2026, 9, 1),
        )


def test_bridge_materializes_and_reads_input001():
    engine = create_engine("sqlite+pysqlite:///:memory:")

    payload = build_cyclos_financial_dataset(
        raw_dataset(),
        dataset_id="graine-roundtrip",
        currency_specs=SPECS,
        snapshot_ref="test-snapshot",
    )

    materialize_financial_dataset(engine, payload)

    reader = FinancialContractReader(engine)

    reader.validate_required_relations()

    metadata = reader.metadata_row()
    accounts = reader.fetch_accounts()
    transactions = reader.fetch_transactions()

    assert metadata["dataset_id"] == "graine-roundtrip"
    assert metadata["source_system"] == "cyclos"
    assert metadata["snapshot_ref"] == "test-snapshot"

    assert len(accounts) == 3
    assert len(transactions) == 2

    assert transactions[0]["transaction_id"] == "tx-001"
    assert transactions[0]["amount_minor"] == 1250
    assert transactions[0]["source_account_id"] == "account-a"
    assert transactions[0]["destination_account_id"] == "account-b"

    assert transactions[1]["transaction_id"] == "tx-002"
    assert transactions[1]["amount_minor"] == 275

    capabilities = reader.capabilities()

    assert capabilities.account_state_history is False
    assert capabilities.balances is False
    assert capabilities.account_replacements is False


def test_bridge_has_no_legacy_business_dependencies():
    import inspect

    source = inspect.getsource(cyclos_dataset)

    forbidden = (
        "anonymize",
        "get_mlc_profile",
        "transaction_semantics",
        "odoo",
    )

    for value in forbidden:
        assert value not in source
