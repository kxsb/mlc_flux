from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, func, select

from server.financial_core.schema import (
    CONTRACT_VERSION,
    account_effects,
    accounts,
    datasets,
    financial_events,
    identity_links,
)
from server.financial_core.writer import (
    FinancialCorePayload,
    FinancialCoreWriteError,
    publish_financial_core,
)


def _account(account_id: str) -> dict:
    return {
        "account_id": account_id,
        "native_account_id": account_id,
        "native_account_kind": "wallet",
    }


def _event(event_id: str, *, state: str = "realized") -> dict:
    return {
        "event_id": event_id,
        "native_event_id": event_id,
        "event_kind": "transfer",
        "execution_state": state,
        "time_precision": "instant",
        "occurred_at": datetime(2026, 9, 15, 12, 0, tzinfo=UTC),
        "occurred_date": None,
    }


def _effect(effect_id: str, event_id: str, account_id: str, amount_minor: int) -> dict:
    return {
        "effect_id": effect_id,
        "event_id": event_id,
        "account_id": account_id,
        "amount_minor": amount_minor,
        "unit_code": "EUR",
        "unit_exponent": 2,
        "monetary_dimension": "digital_mlc",
        "origin": "derived_from_native_transfer",
    }


def _payload(publication_id: str = "pub-1") -> FinancialCorePayload:
    return FinancialCorePayload(
        dataset={
            "dataset_id": "demo-ledger",
            "contract_version": CONTRACT_VERSION,
            "source_system": "test-ledger",
            "source_instance_id": "test-ledger:instance-1",
        },
        publication={
            "publication_id": publication_id,
            "coverage_from": datetime(2026, 9, 1, tzinfo=UTC),
            "coverage_to": datetime(2026, 9, 15, 23, 59, tzinfo=UTC),
            "adapter_name": "test-adapter",
            "adapter_version": "0.1",
        },
        accounts=[_account("A"), _account("B")],
        events=[_event("E1")],
        effects=[
            _effect("FX1", "E1", "A", -10000),
            _effect("FX2", "E1", "B", 10000),
        ],
        capabilities={
            "financial_events": "available",
            "account_effects": "available",
            "actors": {"status": "unavailable", "detail": {"reason": "not supplied"}},
        },
    )


def test_binary_payment_is_one_event_with_two_effects():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    publish_financial_core(engine, _payload())

    with engine.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(financial_events)) == 1
        assert conn.scalar(select(func.count()).select_from(account_effects)) == 2
        assert conn.scalar(select(func.sum(account_effects.c.amount_minor))) == 0


def test_scheduled_event_without_effects_is_valid():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    payload = _payload()
    payload = FinancialCorePayload(
        **{**payload.__dict__, "events": [_event("E1", state="scheduled")], "effects": []}
    )

    publish_financial_core(engine, payload)

    with engine.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(financial_events)) == 1
        assert conn.scalar(select(func.count()).select_from(account_effects)) == 0


def test_multi_effect_event_does_not_require_balancing():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    payload = _payload()
    payload = FinancialCorePayload(
        **{
            **payload.__dict__,
            "accounts": [_account("A"), _account("B"), _account("C"), _account("D")],
            "effects": [
                _effect("FX1", "E1", "A", 10000),
                _effect("FX2", "E1", "B", 10000),
                _effect("FX3", "E1", "C", 10000),
                _effect("FX4", "E1", "D", -10000),
            ],
        }
    )

    publish_financial_core(engine, payload)

    with engine.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(account_effects)) == 4
        assert conn.scalar(select(func.sum(account_effects.c.amount_minor))) == 20000


def test_account_without_actor_is_valid_and_ambiguous_candidates_are_preserved():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    payload = _payload()
    payload = FinancialCorePayload(
        **{
            **payload.__dict__,
            "actors": [
                {"actor_id": "ACT1", "source_system": "odoo", "native_actor_id": "1"},
                {"actor_id": "ACT2", "source_system": "odoo", "native_actor_id": "2"},
            ],
            "identity_links": [
                {
                    "identity_link_id": "L1",
                    "subject_kind": "account",
                    "subject_id": "A",
                    "target_kind": "actor",
                    "target_id": "ACT1",
                    "link_kind": "owner_candidate",
                    "status": "candidate",
                    "confidence": "medium",
                    "evidence_json": {"rule": "address+currency"},
                },
                {
                    "identity_link_id": "L2",
                    "subject_kind": "account",
                    "subject_id": "A",
                    "target_kind": "actor",
                    "target_id": "ACT2",
                    "link_kind": "owner_candidate",
                    "status": "candidate",
                    "confidence": "medium",
                    "evidence_json": {"rule": "address+currency"},
                },
            ],
        }
    )

    publish_financial_core(engine, payload)

    with engine.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(accounts)) == 2
        assert conn.scalar(select(func.count()).select_from(identity_links)) == 2


def test_float_minor_amount_is_rejected_before_sql():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    payload = _payload()
    bad_effect = dict(payload.effects[0])
    bad_effect["amount_minor"] = 12.5
    payload = FinancialCorePayload(
        **{**payload.__dict__, "effects": [bad_effect, payload.effects[1]]}
    )

    with pytest.raises(FinancialCoreWriteError, match="entier exact"):
        publish_financial_core(engine, payload)


def test_negative_exponent_is_rejected():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    payload = _payload()
    bad_effect = dict(payload.effects[0])
    bad_effect["unit_exponent"] = -2
    payload = FinancialCorePayload(
        **{**payload.__dict__, "effects": [bad_effect, payload.effects[1]]}
    )

    with pytest.raises(FinancialCoreWriteError, match="0 et 18"):
        publish_financial_core(engine, payload)


def test_second_publication_atomically_replaces_current_facts():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    publish_financial_core(engine, _payload("pub-1"))

    second = _payload("pub-2")
    second = FinancialCorePayload(
        **{
            **second.__dict__,
            "events": [_event("E2")],
            "effects": [
                _effect("FX3", "E2", "A", -500),
                _effect("FX4", "E2", "B", 500),
            ],
        }
    )
    publish_financial_core(engine, second)

    with engine.connect() as conn:
        current = conn.scalar(
            select(datasets.c.current_publication_id).where(datasets.c.dataset_id == "demo-ledger")
        )
        event_ids = set(conn.scalars(select(financial_events.c.event_id)))
        assert current == "pub-2"
        assert event_ids == {"E2"}


def test_dataset_identity_cannot_silently_change():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    publish_financial_core(engine, _payload("pub-1"))

    second = _payload("pub-2")
    changed_dataset = dict(second.dataset)
    changed_dataset["source_instance_id"] = "other-instance"
    second = FinancialCorePayload(**{**second.__dict__, "dataset": changed_dataset})

    with pytest.raises(FinancialCoreWriteError, match="source_instance_id ne peut pas changer"):
        publish_financial_core(engine, second)
