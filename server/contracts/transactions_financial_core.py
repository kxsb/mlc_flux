from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime

from server.financial_core.schema import (
    CONTRACT_VERSION as FINANCIAL_CORE_VERSION,
)
from server.financial_core.writer import FinancialCorePayload
from server.contracts.transactions_v1 import TransactionContractRow


@dataclass(frozen=True)
class TransactionFinancialCoreSpec:
    unit_code: str
    unit_exponent: int
    monetary_dimension: str


def _json(value) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _actor_id(partner_id: int) -> str:
    return f"partner:{partner_id}"


def _endpoint_id(tx_hash: str, side: str) -> str:
    return f"transaction-endpoint:{tx_hash}:{side}"


def _native_attributes(tx: TransactionContractRow) -> dict:
    return {
        "amount": tx.amount,
        "received_at": tx.received_at,
        "hash": tx.hash,
        "fn_abi": tx.fn_abi,
        "type": tx.type,
        "sender_partner_id": tx.sender_partner_id,
        "receiver_partner_id": tx.receiver_partner_id,
        "is_sender_external": tx.is_sender_external,
        "is_receiver_external": tx.is_receiver_external,
    }


def build_transaction_contract_payload(
    transactions: tuple[TransactionContractRow, ...],
    *,
    spec: TransactionFinancialCoreSpec,
    dataset_id: str,
    publication_id: str,
    source_instance_id: str,
    source_snapshot_ref: str | None = None,
) -> FinancialCorePayload:
    accounts = []
    events = []
    effects = []
    actors_by_id = {}
    identity_links = []

    occurred = []

    for tx in transactions:
        occurred_at = datetime.fromtimestamp(
            tx.received_at,
            tz=UTC,
        )
        occurred.append(occurred_at)

        native = _native_attributes(tx)

        events.append({
            "event_id": tx.hash,
            "native_event_id": tx.hash,
            "native_event_number": None,
            "event_kind": "normalized_transaction",
            "native_event_type": tx.type,
            "native_event_subtype": tx.fn_abi,
            "native_method": tx.fn_abi,
            "native_status": None,
            "execution_state": "unknown",
            "time_precision": "instant",
            "occurred_at": occurred_at,
            "occurred_date": None,
            "business_timezone": None,
            "native_amount_minor": tx.amount,
            "native_unit_code": spec.unit_code,
            "native_unit_exponent": spec.unit_exponent,
            "native_monetary_dimension": spec.monetary_dimension,
            "native_attributes_json": _json(native),
            "provenance_ref": f"contract001:{tx.hash}",
            "provenance_hash": None,
        })

        sides = (
            (
                "sender",
                tx.sender_partner_id,
                tx.is_sender_external,
                -tx.amount,
            ),
            (
                "receiver",
                tx.receiver_partner_id,
                tx.is_receiver_external,
                tx.amount,
            ),
        )

        for side, partner_id, is_external, amount in sides:
            account_id = _endpoint_id(tx.hash, side)

            account_attributes = {
                "side": side,
                "partner_id": partner_id,
                "is_external": is_external,
            }

            actor_id = (
                _actor_id(partner_id)
                if partner_id is not None
                else None
            )

            accounts.append({
                "account_id": account_id,
                "native_account_id": None,
                "native_account_number": None,
                "native_account_type": None,
                "native_account_kind": "normalized_transaction_endpoint",
                "native_status": None,
                "display_label": None,
                "native_owner_id": actor_id,
                "native_attributes_json": _json(account_attributes),
                "provenance_ref": f"contract001:{tx.hash}:{side}",
                "provenance_hash": None,
            })

            effects.append({
                "effect_id": f"{tx.hash}:{side}",
                "event_id": tx.hash,
                "account_id": account_id,
                "amount_minor": amount,
                "unit_code": spec.unit_code,
                "unit_exponent": spec.unit_exponent,
                "monetary_dimension": spec.monetary_dimension,
                "origin": "derived",
                "native_effect_id": None,
                "native_attributes_json": _json(account_attributes),
                "provenance_ref": f"contract001:{tx.hash}:{side}",
                "provenance_hash": None,
            })

            if partner_id is not None:
                actors_by_id.setdefault(
                    actor_id,
                    {
                        "actor_id": actor_id,
                        "source_system": "normalized_transactions_contract",
                        "native_actor_id": str(partner_id),
                        "native_actor_kind": None,
                        "display_label": None,
                        "native_attributes_json": _json({
                            "partner_id": partner_id,
                        }),
                        "provenance_ref": f"contract001:partner:{partner_id}",
                        "provenance_hash": None,
                    },
                )

                identity_links.append({
                    "identity_link_id": (
                        f"{tx.hash}:{side}:partner:{partner_id}"
                    ),
                    "subject_kind": "account",
                    "subject_id": account_id,
                    "target_kind": "actor",
                    "target_id": actor_id,
                    "link_kind": "contract_partner_id",
                    "status": "resolved",
                    "confidence": None,
                    "source_system": "normalized_transactions_contract",
                    "valid_from": None,
                    "valid_to": None,
                    "evidence_json": _json({
                        "partner_id": partner_id,
                    }),
                })

    canonical = _json({
        "transactions": [
            _native_attributes(tx)
            for tx in transactions
        ],
    }).encode("utf-8")

    return FinancialCorePayload(
        dataset={
            "dataset_id": dataset_id,
            "contract_version": FINANCIAL_CORE_VERSION,
            "source_system": "normalized_transactions",
            "source_instance_id": source_instance_id,
        },
        publication={
            "publication_id": publication_id,
            "coverage_from": min(occurred) if occurred else None,
            "coverage_to": max(occurred) if occurred else None,
            "source_cursor": None,
            "source_snapshot_ref": source_snapshot_ref,
            "adapter_name": "contract001-transactions",
            "adapter_version": "1",
            "content_hash": hashlib.sha256(canonical).hexdigest(),
        },
        accounts=accounts,
        events=events,
        effects=effects,
        actors=list(actors_by_id.values()),
        identity_links=identity_links,
        capabilities={},
    )
