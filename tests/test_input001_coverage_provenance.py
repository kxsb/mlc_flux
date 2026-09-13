from contextlib import nullcontext
from datetime import UTC, datetime
from types import SimpleNamespace

from sqlalchemy import create_engine

from server.input_contract import shadow
from server.input_contract.reader import FinancialContractReader
from server.input_contract.shadow import (
    CyclosShadowConfig,
    materialize_cyclos_shadow,
)
from server.services import cyclos_client
from server.services.cyclos_client import CyclosTransactionBatch


def _actor(actor_id):
    return {
        "id": actor_id,
        "type": {"internalName": "monCompte"},
        "user": {
            "id": f"user-{actor_id}",
            "display": f"User {actor_id}",
        },
    }


def _raw_transaction():
    return {
        "id": "tx-coverage-001",
        "transactionNumber": "N-COVERAGE-001",
        "date": "2026-09-12T12:00:00Z",
        "currency": "native-test",
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


def test_cyclos_batch_preserves_exact_requested_calendar_coverage(monkeypatch):
    class Response:
        headers = {"X-Has-Next-Page": "false"}

        def raise_for_status(self):
            return None

        def json(self):
            return []

    calls = []

    monkeypatch.setattr(
        cyclos_client,
        "get_cyclos_config",
        lambda: SimpleNamespace(base_url="https://cyclos.example.test"),
    )
    monkeypatch.setattr(
        cyclos_client,
        "create_session_token",
        lambda: "test-token",
    )

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return Response()

    monkeypatch.setattr(cyclos_client.requests, "get", fake_get)

    batch = cyclos_client.get_transactions(
        date_from="2026-09-01",
        date_to="2026-09-12",
    )

    assert isinstance(batch, list)
    assert batch == []
    assert batch.coverage_from == datetime(
        2026, 8, 31, 22, 0, tzinfo=UTC
    )
    assert batch.coverage_to == datetime(
        2026, 9, 12, 22, 0, tzinfo=UTC
    )

    assert len(calls) == 1
    params = calls[0][1]["params"]
    assert params["datePeriod"] == [
        "2026-08-31T22:00:00+00:00",
        "2026-09-12T22:00:00+00:00",
    ]


def test_shadow_materializes_explicit_coverage_without_inferring_from_rows(
    monkeypatch,
):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    monkeypatch.setattr(
        shadow,
        "create_input001_engine",
        lambda: engine,
    )

    config = CyclosShadowConfig(
        enabled=True,
        dataset_id="coverage-test",
        native_currency_id="native-test",
        currency_code="LOCAL",
        currency_exponent=2,
    )

    coverage_from = datetime(2026, 9, 1, 0, 0, tzinfo=UTC)
    coverage_to = datetime(2026, 9, 13, 0, 0, tzinfo=UTC)

    materialize_cyclos_shadow(
        [_raw_transaction()],
        config=config,
        snapshot_ref="coverage:test",
        coverage_from=coverage_from,
        coverage_to=coverage_to,
    )

    metadata = FinancialContractReader(engine).metadata_row()

    assert metadata["coverage_from"] == coverage_from
    assert metadata["coverage_to"] == coverage_to


def test_runtime_propagates_source_coverage_to_shadow(monkeypatch):
    import server.sync_transactions as sync

    coverage_from = datetime(2026, 6, 15, 8, 0, tzinfo=UTC)
    coverage_to = datetime(2026, 9, 13, 8, 0, tzinfo=UTC)

    raw = CyclosTransactionBatch(
        [_raw_transaction()],
        coverage_from=coverage_from,
        coverage_to=coverage_to,
    )

    class FakeApp:
        def app_context(self):
            return nullcontext()

    monkeypatch.setattr(sync, "create_app", lambda: FakeApp())
    monkeypatch.setattr(sync, "init_db", lambda: None)
    monkeypatch.setattr(sync, "get_transactions", lambda **kwargs: raw)
    monkeypatch.setattr(sync, "anonymize_transactions", lambda rows: [{"safe": True}])
    monkeypatch.setattr(sync, "insert_transactions", lambda rows: 1)
    monkeypatch.setattr(
        sync,
        "save_sync_state",
        lambda status, message, **kwargs: None,
    )

    received = {}

    def fake_shadow(rows, **kwargs):
        received["rows"] = rows
        received["kwargs"] = kwargs
        return {
            "enabled": True,
            "status": "success",
            "transactions": 1,
        }

    monkeypatch.setattr(sync, "materialize_cyclos_shadow", fake_shadow)

    result = sync.run_sync(reconcile_days=90)

    assert received["rows"] is raw
    assert received["kwargs"] == {
        "coverage_from": coverage_from,
        "coverage_to": coverage_to,
    }
    assert result["input001_shadow"]["status"] == "success"
