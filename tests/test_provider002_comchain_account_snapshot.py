from datetime import UTC, datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, insert, select

from server.input_contract.reader import FinancialContractReader
from server.input_contract.schema import (
    accounts,
    balances,
    dataset_metadata,
    transactions,
)
from server.providers.comchain_facts import (
    ComChainFactsError,
    extract_comchain_account_snapshot_facts,
)
from server.providers.comchain_normalized import (
    ComChainAccountSnapshotError,
    ComChainCurrencySpec,
    comchain_account_snapshot_row,
    comchain_balance_rows,
    comchain_replacement_target,
)


ADDRESS = "0xAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAa"
ADDRESS_CANONICAL = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

NEW_ADDRESS = "0xBbBbBbBbBbBbBbBbBbBbBbBbBbBbBbBbBbBbBbBb"
NEW_ADDRESS_CANONICAL = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"

ZERO_ADDRESS = "0x" + ("0" * 40)


SPEC = ComChainCurrencySpec(
    native_currency_id="currency-example",
    currency_code="LOCAL",
    currency_exponent=2,
    amount_representation="minor",
)


def snapshot(**overrides):
    row = {
        "address": ADDRESS,
        "block": 123456,
        "accountType": 1,
        "accountStatus": True,
        "balanceEL": 1250,
        "balanceCM": -300,
        "newAddress": ZERO_ADDRESS,
    }
    row.update(overrides)
    return extract_comchain_account_snapshot_facts(row)


def test_extract_native_account_snapshot_facts():
    facts = snapshot()

    assert facts.account_address == ADDRESS
    assert facts.block_number == 123456
    assert facts.native_account_type == 1
    assert facts.native_account_status is True
    assert facts.balance_el_minor == 1250
    assert facts.balance_cm_minor == -300
    assert facts.replacement_address == ZERO_ADDRESS


def test_numeric_boolean_status_is_accepted():
    assert snapshot(accountStatus=1).native_account_status is True
    assert snapshot(accountStatus=0).native_account_status is False


def test_float_balance_is_rejected():
    with pytest.raises(
        ComChainFactsError,
        match="balanceEL.*non entier",
    ):
        snapshot(balanceEL=12.5)


def test_snapshot_enriches_account_native_facts():
    row = comchain_account_snapshot_row(snapshot())

    assert row["account_id"] == ADDRESS_CANONICAL
    assert row["native_account_type"] == "1"
    assert row["native_status"] == "accountStatus:true"
    assert row["native_owner_id"] is None
    assert row["source_system"] == "comchain"


def test_false_account_status_remains_distinct():
    row = comchain_account_snapshot_row(
        snapshot(accountStatus=False)
    )

    assert row["native_status"] == "accountStatus:false"


def test_balance_components_are_preserved_separately():
    observed = datetime(
        2026,
        9,
        13,
        12,
        30,
        tzinfo=UTC,
    )

    rows = comchain_balance_rows(
        snapshot(),
        observed_at=observed,
        currency_spec=SPEC,
    )

    assert len(rows) == 2

    assert rows[0]["balance_component"] == "balanceEL"
    assert rows[0]["amount_minor"] == 1250

    assert rows[1]["balance_component"] == "balanceCM"
    assert rows[1]["amount_minor"] == -300

    for row in rows:
        assert row["account_id"] == ADDRESS_CANONICAL
        assert row["observed_at"] == observed
        assert row["currency_code"] == "LOCAL"
        assert row["currency_exponent"] == 2
        assert row["source_system"] == "comchain"


def test_balance_observation_is_normalized_to_utc():
    observed = datetime(
        2026,
        9,
        13,
        14,
        30,
        tzinfo=timezone_plus_two(),
    )

    rows = comchain_balance_rows(
        snapshot(),
        observed_at=observed,
        currency_spec=SPEC,
    )

    assert rows[0]["observed_at"] == datetime(
        2026,
        9,
        13,
        12,
        30,
        tzinfo=UTC,
    )


def timezone_plus_two():
    return timezone_offset(2)


def timezone_offset(hours):
    return timezone(timedelta(hours=hours))


def test_naive_observation_time_is_rejected():
    with pytest.raises(
        ComChainAccountSnapshotError,
        match="timezone-aware",
    ):
        comchain_balance_rows(
            snapshot(),
            observed_at=datetime(2026, 9, 13, 12, 30),
            currency_spec=SPEC,
        )


def test_balance_bigint_overflow_is_rejected():
    with pytest.raises(
        ComChainAccountSnapshotError,
        match="hors plage BIGINT",
    ):
        comchain_balance_rows(
            snapshot(balanceEL=9223372036854775808),
            observed_at=datetime(
                2026, 9, 13, 12, 30, tzinfo=UTC
            ),
            currency_spec=SPEC,
        )


def test_zero_replacement_address_means_no_replacement():
    assert comchain_replacement_target(snapshot()) is None


def test_replacement_target_is_canonical_but_not_historicized():
    target = comchain_replacement_target(
        snapshot(newAddress=NEW_ADDRESS)
    )

    assert target == NEW_ADDRESS_CANONICAL


def test_snapshot_roundtrips_through_input001_balances():
    observed = datetime(
        2026,
        9,
        13,
        12,
        30,
        tzinfo=UTC,
    )
    facts = snapshot()

    account_row = comchain_account_snapshot_row(facts)
    balance_rows = comchain_balance_rows(
        facts,
        observed_at=observed,
        currency_spec=SPEC,
    )

    engine = create_engine("sqlite+pysqlite:///:memory:")

    accounts.create(engine)
    transactions.create(engine)
    dataset_metadata.create(engine)
    balances.create(engine)

    with engine.begin() as conn:
        conn.execute(insert(accounts), [account_row])
        conn.execute(insert(balances), balance_rows)
        conn.execute(
            insert(dataset_metadata),
            [{
                "dataset_id": "comchain-snapshot",
                "contract_version": "input001-v0.1",
                "source_system": "comchain",
                "snapshot_ref": "comchain:block:123456",
                "account_state_history": False,
                "balances": True,
                "account_replacements": False,
            }],
        )

    reader = FinancialContractReader(engine)

    reader.validate_required_relations()
    capabilities = reader.capabilities()

    assert capabilities.balances is True
    assert capabilities.account_state_history is False
    assert capabilities.account_replacements is False

    stored_account = reader.fetch_accounts()[0]

    assert stored_account["account_id"] == ADDRESS_CANONICAL
    assert stored_account["native_account_type"] == "1"
    assert stored_account["native_status"] == "accountStatus:true"

    with engine.connect() as conn:
        stored_balances = [
            dict(row)
            for row in conn.execute(
                select(balances).order_by(
                    balances.c.balance_component
                )
            ).mappings()
        ]

    assert len(stored_balances) == 2

    by_component = {
        row["balance_component"]: row
        for row in stored_balances
    }

    assert by_component["balanceEL"]["amount_minor"] == 1250
    assert by_component["balanceCM"]["amount_minor"] == -300

    for row in stored_balances:
        assert row["observed_at"] == observed
