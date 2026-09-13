from contextlib import nullcontext

import pytest
from sqlalchemy import create_engine

from server.input_contract import shadow
from server.input_contract.reader import FinancialContractReader
from server.input_contract.shadow import (
    CyclosShadowConfig,
    Input001ShadowConfigError,
    get_cyclos_shadow_config,
    materialize_cyclos_shadow,
)


def actor(actor_id):
    return {
        "id": actor_id,
        "type": {
            "internalName": "monCompte",
        },
        "user": {
            "id": f"user-{actor_id}",
            "display": f"User {actor_id}",
        },
    }


def raw_transactions():
    return [
        {
            "id": "tx-shadow-001",
            "transactionNumber": "N-001",
            "date": "2026-09-13T12:00:00Z",
            "currency": "native-test",
            "amount": "12.50",
            "kind": "transfer",
            "creationType": "manual",
            "type": {
                "internalName": "payment",
                "name": "Paiement",
            },
            "from": actor("account-a"),
            "to": actor("account-b"),
        }
    ]


def clear_shadow_environment(monkeypatch):
    names = (
        "MLCFLUX_INPUT001_SHADOW_ENABLED",
        "MLCFLUX_INPUT001_DATASET_ID",
        "MLCFLUX_INPUT001_CYCLOS_NATIVE_CURRENCY_ID",
        "MLCFLUX_INPUT001_CURRENCY_CODE",
        "MLCFLUX_INPUT001_CURRENCY_EXPONENT",
    )

    for name in names:
        monkeypatch.delenv(name, raising=False)


def test_shadow_is_disabled_by_default(monkeypatch):
    clear_shadow_environment(monkeypatch)

    config = get_cyclos_shadow_config()

    assert config.enabled is False

    result = materialize_cyclos_shadow(
        raw_transactions(),
        config=config,
    )

    assert result == {
        "enabled": False,
        "status": "disabled",
    }


def test_enabled_shadow_requires_explicit_configuration(
    monkeypatch,
):
    clear_shadow_environment(monkeypatch)

    monkeypatch.setenv(
        "MLCFLUX_INPUT001_SHADOW_ENABLED",
        "1",
    )

    with pytest.raises(
        Input001ShadowConfigError,
        match="MLCFLUX_INPUT001_DATASET_ID",
    ):
        get_cyclos_shadow_config()


def test_currency_exponent_must_be_explicit_integer(
    monkeypatch,
):
    clear_shadow_environment(monkeypatch)

    monkeypatch.setenv(
        "MLCFLUX_INPUT001_SHADOW_ENABLED",
        "true",
    )
    monkeypatch.setenv(
        "MLCFLUX_INPUT001_DATASET_ID",
        "test-dataset",
    )
    monkeypatch.setenv(
        "MLCFLUX_INPUT001_CYCLOS_NATIVE_CURRENCY_ID",
        "native-test",
    )
    monkeypatch.setenv(
        "MLCFLUX_INPUT001_CURRENCY_CODE",
        "LOCAL",
    )
    monkeypatch.setenv(
        "MLCFLUX_INPUT001_CURRENCY_EXPONENT",
        "abc",
    )

    with pytest.raises(
        Input001ShadowConfigError,
        match="doit être un entier",
    ):
        get_cyclos_shadow_config()


def test_shadow_materializes_last_cyclos_batch(
    monkeypatch,
):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:"
    )

    monkeypatch.setattr(
        shadow,
        "create_input001_engine",
        lambda: engine,
    )

    config = CyclosShadowConfig(
        enabled=True,
        dataset_id="test-dataset",
        native_currency_id="native-test",
        currency_code="LOCAL",
        currency_exponent=2,
    )

    result = materialize_cyclos_shadow(
        raw_transactions(),
        config=config,
        snapshot_ref="shadow:test",
    )

    assert result["status"] == "success"
    assert result["accounts"] == 2
    assert result["transactions"] == 1
    assert result["snapshot_ref"] == "shadow:test"

    reader = FinancialContractReader(engine)

    assert (
        reader.metadata_row()["dataset_id"]
        == "test-dataset"
    )

    tx = reader.fetch_transactions()[0]

    assert tx["transaction_id"] == "tx-shadow-001"
    assert tx["amount_minor"] == 1250


def test_unknown_native_currency_fails_closed(
    monkeypatch,
):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:"
    )

    monkeypatch.setattr(
        shadow,
        "create_input001_engine",
        lambda: engine,
    )

    config = CyclosShadowConfig(
        enabled=True,
        dataset_id="test-dataset",
        native_currency_id="other-currency",
        currency_code="LOCAL",
        currency_exponent=2,
    )

    with pytest.raises(
        ValueError,
        match="Devise Cyclos inconnue",
    ):
        materialize_cyclos_shadow(
            raw_transactions(),
            config=config,
        )


def test_runtime_shadow_failure_does_not_break_legacy(
    monkeypatch,
):
    import server.sync_transactions as sync

    raw = raw_transactions()
    safe = [{"legacy": True}]

    class FakeApp:
        def app_context(self):
            return nullcontext()

    monkeypatch.setattr(
        sync,
        "create_app",
        lambda: FakeApp(),
    )
    monkeypatch.setattr(
        sync,
        "init_db",
        lambda: None,
    )
    monkeypatch.setattr(
        sync,
        "get_transactions",
        lambda **kwargs: raw,
    )
    monkeypatch.setattr(
        sync,
        "anonymize_transactions",
        lambda rows: safe,
    )

    legacy_calls = []

    def fake_insert(rows):
        legacy_calls.append(rows)
        return 1

    monkeypatch.setattr(
        sync,
        "insert_transactions",
        fake_insert,
    )

    sync_states = []

    monkeypatch.setattr(
        sync,
        "save_sync_state",
        lambda status, message: sync_states.append(
            (status, message)
        ),
    )

    def fail_shadow(rows):
        assert rows is raw
        raise RuntimeError("shadow failure")

    monkeypatch.setattr(
        sync,
        "materialize_cyclos_shadow",
        fail_shadow,
    )

    result = sync.run_sync(days=1)

    assert legacy_calls == [safe]
    assert result["fetched"] == 1
    assert result["written"] == 1

    assert (
        result["input001_shadow"]["status"]
        == "error"
    )
    assert (
        result["input001_shadow"]["error_type"]
        == "RuntimeError"
    )

    assert sync_states
    assert sync_states[-1][0] == "success"
    assert (
        "INPUT001 shadow=error"
        in sync_states[-1][1]
    )


def test_runtime_shadow_receives_raw_transactions(
    monkeypatch,
):
    import server.sync_transactions as sync

    raw = raw_transactions()
    safe = [{"anonymized": True}]

    class FakeApp:
        def app_context(self):
            return nullcontext()

    monkeypatch.setattr(
        sync,
        "create_app",
        lambda: FakeApp(),
    )
    monkeypatch.setattr(
        sync,
        "init_db",
        lambda: None,
    )
    monkeypatch.setattr(
        sync,
        "get_transactions",
        lambda **kwargs: raw,
    )
    monkeypatch.setattr(
        sync,
        "anonymize_transactions",
        lambda rows: safe,
    )
    monkeypatch.setattr(
        sync,
        "insert_transactions",
        lambda rows: 1,
    )
    monkeypatch.setattr(
        sync,
        "save_sync_state",
        lambda status, message: None,
    )

    received = []

    def fake_shadow(rows):
        received.append(rows)
        return {
            "enabled": True,
            "status": "success",
            "transactions": 1,
        }

    monkeypatch.setattr(
        sync,
        "materialize_cyclos_shadow",
        fake_shadow,
    )

    result = sync.run_sync(days=1)

    assert received == [raw]
    assert received[0] is raw

    assert (
        result["input001_shadow"]["status"]
        == "success"
    )
