from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, insert

from server.financial_core import publication as publication_module
from server.financial_core.reader import (
    FinancialCoreReadError,
    get_current_publication_id,
    read_current_financial_core,
)
from server.financial_core.schema import metadata


NOW = datetime(2026, 9, 15, 12, 0, tzinfo=UTC)


def _table(name):
    return metadata.tables[name]


def _engine():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
    )
    metadata.create_all(engine)
    return engine


def _seed_current_and_stale_publication(engine):
    datasets = _table("financial_core_datasets")
    publications = _table("financial_core_publications")
    capabilities = _table(
        "financial_core_publication_capabilities"
    )
    accounts = _table("financial_core_accounts")
    events = _table("financial_core_events")
    effects = _table("financial_core_account_effects")

    with engine.begin() as conn:
        conn.execute(
            insert(datasets),
            [{
                "dataset_id": "dataset-1",
                "contract_version": "financial-core-v0.1",
                "source_system": "test",
                "source_instance_id": "instance-1",
                "current_publication_id": "publication-b",
                "created_at": NOW,
                "updated_at": NOW,
            }],
        )

        conn.execute(
            insert(publications),
            [
                {
                    "publication_id": "publication-a",
                    "dataset_id": "dataset-1",
                    "created_at": NOW,
                    "coverage_from": NOW,
                    "coverage_to": NOW,
                    "source_cursor": None,
                    "source_snapshot_ref": None,
                    "adapter_name": "test",
                    "adapter_version": "1",
                    "content_hash": None,
                    "status": "valid",
                },
                {
                    "publication_id": "publication-b",
                    "dataset_id": "dataset-1",
                    "created_at": NOW,
                    "coverage_from": NOW,
                    "coverage_to": NOW,
                    "source_cursor": None,
                    "source_snapshot_ref": None,
                    "adapter_name": "test",
                    "adapter_version": "2",
                    "content_hash": None,
                    "status": "valid",
                },
            ],
        )

        conn.execute(
            insert(capabilities),
            [
                {
                    "publication_id": "publication-a",
                    "capability": "events",
                    "status": "partial",
                    "detail_json": None,
                },
                {
                    "publication_id": "publication-b",
                    "capability": "events",
                    "status": "available",
                    "detail_json": None,
                },
            ],
        )

        conn.execute(
            insert(accounts),
            [
                {
                    "dataset_id": "dataset-1",
                    "account_id": "old-account",
                    "publication_id": "publication-a",
                },
                {
                    "dataset_id": "dataset-1",
                    "account_id": "new-account",
                    "publication_id": "publication-b",
                },
            ],
        )

        conn.execute(
            insert(events),
            [
                {
                    "dataset_id": "dataset-1",
                    "event_id": "old-event",
                    "publication_id": "publication-a",
                    "event_kind": "transfer",
                    "execution_state": "executed",
                    "time_precision": "instant",
                    "occurred_at": NOW,
                },
                {
                    "dataset_id": "dataset-1",
                    "event_id": "new-event",
                    "publication_id": "publication-b",
                    "event_kind": "transfer",
                    "execution_state": "executed",
                    "time_precision": "instant",
                    "occurred_at": NOW,
                },
            ],
        )

        conn.execute(
            insert(effects),
            [
                {
                    "dataset_id": "dataset-1",
                    "effect_id": "old-effect",
                    "publication_id": "publication-a",
                    "event_id": "old-event",
                    "account_id": "old-account",
                    "amount_minor": -100,
                    "unit_code": "TEST",
                    "unit_exponent": 2,
                    "monetary_dimension": "digital",
                    "origin": "native",
                },
                {
                    "dataset_id": "dataset-1",
                    "effect_id": "new-effect",
                    "publication_id": "publication-b",
                    "event_id": "new-event",
                    "account_id": "new-account",
                    "amount_minor": 100,
                    "unit_code": "TEST",
                    "unit_exponent": 2,
                    "monetary_dimension": "digital",
                    "origin": "native",
                },
            ],
        )


def test_reader_uses_only_current_publication():
    engine = _engine()
    _seed_current_and_stale_publication(engine)

    snapshot = read_current_financial_core(
        engine,
        "dataset-1",
    )

    assert snapshot.publication_id == "publication-b"
    assert snapshot.dataset_id == "dataset-1"

    assert [row["account_id"] for row in snapshot.accounts] == [
        "new-account"
    ]
    assert [row["event_id"] for row in snapshot.events] == [
        "new-event"
    ]
    assert [row["effect_id"] for row in snapshot.account_effects] == [
        "new-effect"
    ]

    assert len(snapshot.capabilities) == 1
    assert snapshot.capabilities[0]["status"] == "available"


def test_reader_counts_are_publication_scoped():
    engine = _engine()
    _seed_current_and_stale_publication(engine)

    snapshot = read_current_financial_core(
        engine,
        "dataset-1",
    )

    assert snapshot.counts() == {
        "capabilities": 1,
        "accounts": 1,
        "events": 1,
        "account_effects": 1,
        "actors": 0,
        "identity_links": 0,
        "balance_observations": 0,
        "monetary_observations": 0,
        "account_replacements": 0,
    }


def test_get_current_publication_id_is_diagnostic_only():
    engine = _engine()
    _seed_current_and_stale_publication(engine)

    assert get_current_publication_id(
        engine,
        "dataset-1",
    ) == "publication-b"

    assert get_current_publication_id(
        engine,
        "missing",
    ) is None


def test_reader_rejects_dataset_without_current_publication():
    engine = _engine()

    with engine.begin() as conn:
        conn.execute(
            insert(_table("financial_core_datasets")),
            [{
                "dataset_id": "dataset-empty",
                "contract_version": "financial-core-v0.1",
                "source_system": "test",
                "source_instance_id": "instance-1",
                "current_publication_id": None,
                "created_at": NOW,
                "updated_at": NOW,
            }],
        )

    with pytest.raises(
        FinancialCoreReadError,
        match="n'a pas de publication courante",
    ):
        read_current_financial_core(
            engine,
            "dataset-empty",
        )


def test_reader_rejects_dangling_publication_pointer():
    engine = _engine()

    with engine.begin() as conn:
        conn.execute(
            insert(_table("financial_core_datasets")),
            [{
                "dataset_id": "dataset-broken",
                "contract_version": "financial-core-v0.1",
                "source_system": "test",
                "source_instance_id": "instance-1",
                "current_publication_id": "missing-publication",
                "created_at": NOW,
                "updated_at": NOW,
            }],
        )

    with pytest.raises(
        FinancialCoreReadError,
        match="publication absente",
    ):
        read_current_financial_core(
            engine,
            "dataset-broken",
        )


def test_prepare_candidate_validates_without_writing(monkeypatch):
    payload = object()
    calls = []

    def fake_validate(candidate_payload):
        calls.append(candidate_payload)
        return {
            "valid": True,
            "relation_counts": {"events": 1},
        }

    monkeypatch.setattr(
        publication_module,
        "validate_financial_core_payload",
        fake_validate,
    )

    candidate = publication_module.prepare_financial_core_candidate(
        payload
    )

    assert candidate.payload is payload
    assert candidate.validation["valid"] is True
    assert calls == [payload]


def test_publish_candidate_revalidates_before_writer(monkeypatch):
    payload = object()
    events = []

    def fake_validate(candidate_payload):
        assert candidate_payload is payload
        events.append("validate")
        return {"valid": True}

    def fake_publish(engine, candidate_payload):
        assert engine == "engine"
        assert candidate_payload is payload
        events.append("publish")
        return "publication-1"

    monkeypatch.setattr(
        publication_module,
        "validate_financial_core_payload",
        fake_validate,
    )
    monkeypatch.setattr(
        publication_module,
        "publish_financial_core",
        fake_publish,
    )

    candidate = publication_module.prepare_financial_core_candidate(
        payload
    )

    publication_id = (
        publication_module.publish_financial_core_candidate(
            "engine",
            candidate,
        )
    )

    assert publication_id == "publication-1"
    assert events == [
        "validate",
        "validate",
        "publish",
    ]


def test_validate_and_publish_follows_full_lifecycle(monkeypatch):
    payload = object()
    calls = []

    monkeypatch.setattr(
        publication_module,
        "validate_financial_core_payload",
        lambda candidate_payload: (
            calls.append("validate") or {"valid": True}
        ),
    )

    monkeypatch.setattr(
        publication_module,
        "publish_financial_core",
        lambda engine, candidate_payload: (
            calls.append("publish") or "publication-2"
        ),
    )

    publication_id = (
        publication_module.validate_and_publish_financial_core(
            "engine",
            payload,
        )
    )

    assert publication_id == "publication-2"
    assert calls == [
        "validate",
        "validate",
        "publish",
    ]
