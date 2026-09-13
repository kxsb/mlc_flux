from __future__ import annotations

from sqlalchemy import create_engine, inspect as sa_inspect, update
import pytest

from server.input_contract import shadow
from server.input_contract.reader import FinancialContractReader
from server.input_contract.schema import (
    dataset_metadata,
    transactions,
)
from server.input_contract.shadow import (
    CyclosShadowConfig,
    materialize_cyclos_shadow,
)
from server.input_contract.shadow_lifecycle import (
    SHADOW_RUNTIME_STATE_TABLE,
    SHADOW_STORAGE_SCHEMA_VERSION,
    Input001ShadowStorageError,
    prepare_shadow_storage,
    read_shadow_health,
    shadow_runtime_state,
)


def _actor(actor_id: str) -> dict:
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


def _raw_transaction(*, currency: str = "native-test") -> dict:
    return {
        "id": "tx-shadow-lifecycle-001",
        "transactionNumber": "N-LIFECYCLE-001",
        "date": "2026-09-13T12:00:00Z",
        "currency": currency,
        "amount": "12.50",
        "kind": "transfer",
        "creationType": "manual",
        "type": {
            "internalName": "payment",
            "name": "Paiement",
        },
        "from": _actor("account-a"),
        "to": _actor("account-b"),
    }


def _config(*, native_currency_id: str = "native-test") -> CyclosShadowConfig:
    return CyclosShadowConfig(
        enabled=True,
        dataset_id="lifecycle-test",
        native_currency_id=native_currency_id,
        currency_code="LOCAL",
        currency_exponent=2,
    )


def test_fresh_shadow_storage_is_initialized_with_physical_version():
    engine = create_engine("sqlite+pysqlite:///:memory:")

    result = prepare_shadow_storage(engine)
    health = read_shadow_health(engine)

    assert result == {
        "action": "initialized",
        "storage_schema_version": SHADOW_STORAGE_SCHEMA_VERSION,
        "reason": None,
    }
    assert health["storage_schema_version"] == SHADOW_STORAGE_SCHEMA_VERSION
    assert health["status"] == "unknown"
    assert SHADOW_RUNTIME_STATE_TABLE in sa_inspect(engine).get_table_names()


def test_current_shadow_is_not_rebuilt_on_next_materialization(monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    monkeypatch.setattr(shadow, "create_input001_engine", lambda: engine)

    first = materialize_cyclos_shadow(
        [_raw_transaction()],
        config=_config(),
        snapshot_ref="shadow:first",
    )
    second = materialize_cyclos_shadow(
        [_raw_transaction()],
        config=_config(),
        snapshot_ref="shadow:second",
    )

    assert first["storage"]["action"] == "initialized"
    assert second["storage"]["action"] == "compatible"
    assert second["health"]["status"] == "success"
    assert second["health"]["snapshot_ref"] == "shadow:second"
    assert second["health"]["last_attempt_at"] is not None
    assert second["health"]["last_success_at"] is not None

    # La table opérationnelle du shadow ne devient pas une relation INPUT001.
    assert SHADOW_RUNTIME_STATE_TABLE not in FinancialContractReader(
        engine
    ).relation_names()


def test_stale_contract_schema_is_reconstructed_before_materialization(monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:")

    # Forme historique volontairement incomplète : accounts ne possède pas
    # native_account_kind, alors que contract_version peut toujours être v0.1.
    with engine.begin() as conn:
        conn.exec_driver_sql("""
            CREATE TABLE accounts (
                account_id TEXT PRIMARY KEY,
                native_account_number TEXT,
                native_account_type TEXT,
                native_account_type_label TEXT,
                native_status TEXT,
                display_label TEXT,
                native_owner_id TEXT,
                source_system VARCHAR(64) NOT NULL
            )
        """)
        transactions.create(conn)
        dataset_metadata.create(conn)

    monkeypatch.setattr(shadow, "create_input001_engine", lambda: engine)

    result = materialize_cyclos_shadow(
        [_raw_transaction()],
        config=_config(),
        snapshot_ref="shadow:rebuilt",
    )

    assert result["storage"]["action"] == "reconstructed"
    assert "native_account_kind" in result["storage"]["reason"]

    columns = {
        column["name"]
        for column in sa_inspect(engine).get_columns("accounts")
    }
    assert "native_account_kind" in columns
    assert result["health"]["status"] == "success"


def test_shadow_failure_is_recorded_and_next_valid_batch_recovers(monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    monkeypatch.setattr(shadow, "create_input001_engine", lambda: engine)

    with pytest.raises(ValueError, match="Devise Cyclos inconnue"):
        materialize_cyclos_shadow(
            [_raw_transaction(currency="native-test")],
            config=_config(native_currency_id="other-currency"),
            snapshot_ref="shadow:failure",
        )

    failed = read_shadow_health(engine)
    assert failed["status"] == "error"
    assert failed["error_type"] == "ValueError"
    assert failed["last_attempt_at"] is not None
    assert failed["last_success_at"] is None

    recovered = materialize_cyclos_shadow(
        [_raw_transaction()],
        config=_config(),
        snapshot_ref="shadow:recovered",
    )

    assert recovered["health"]["status"] == "success"
    assert recovered["health"]["error_type"] is None
    assert recovered["health"]["error"] is None
    assert recovered["health"]["last_success_at"] is not None
    assert recovered["health"]["snapshot_ref"] == "shadow:recovered"


def test_newer_shadow_storage_version_is_never_downgraded_silently():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    prepare_shadow_storage(engine)

    with engine.begin() as conn:
        conn.execute(
            update(shadow_runtime_state)
            .where(shadow_runtime_state.c.state_id == 1)
            .values(
                storage_schema_version=(
                    SHADOW_STORAGE_SCHEMA_VERSION + 1
                )
            )
        )

    with pytest.raises(
        Input001ShadowStorageError,
        match="version de stockage plus récente",
    ):
        prepare_shadow_storage(engine)
