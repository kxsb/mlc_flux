from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime

from server.contracts.transactions_v1 import (
    TransactionContractRow,
    transaction_event_signature,
)
from server.financial_core.schema import (
    CONTRACT_VERSION as FINANCIAL_CORE_VERSION,
)
from server.financial_core.writer import (
    FinancialCorePayload,
)


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


def _endpoint_id(
    tx_hash: str,
    side: str,
) -> str:
    return f"transaction-endpoint:{tx_hash}:{side}"


def _group_transactions(
    transactions: tuple[TransactionContractRow, ...],
):
    groups = {}

    for tx in transactions:
        signature = transaction_event_signature(tx)

        group = groups.get(tx.hash)

        if group is None:
            group = {
                "transaction": tx,
                "signature": signature,
                "sender_partner_ids": set(),
                "receiver_partner_ids": set(),
            }
            groups[tx.hash] = group

        elif group["signature"] != signature:
            raise ValueError(
                "Faits financiers divergents pour le hash "
                f"{tx.hash!r}."
            )

        if tx.sender_partner_id is not None:
            group["sender_partner_ids"].add(
                tx.sender_partner_id
            )

        if tx.receiver_partner_id is not None:
            group["receiver_partner_ids"].add(
                tx.receiver_partner_id
            )

    return tuple(
        sorted(
            groups.values(),
            key=lambda group: (
                group["transaction"].received_at,
                group["transaction"].hash,
            ),
        )
    )


def _native_attributes(group) -> dict:
    tx = group["transaction"]

    return {
        "amount": tx.amount,
        "received_at": tx.received_at,
        "hash": tx.hash,
        "fn_abi": tx.fn_abi,
        "type": tx.type,
        "sender_partner_ids": sorted(
            group["sender_partner_ids"]
        ),
        "receiver_partner_ids": sorted(
            group["receiver_partner_ids"]
        ),
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

    groups = _group_transactions(transactions)

    for group in groups:
        tx = group["transaction"]

        occurred_at = datetime.fromtimestamp(
            tx.received_at,
            tz=UTC,
        )
        occurred.append(occurred_at)

        native = _native_attributes(group)

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
            "native_monetary_dimension": (
                spec.monetary_dimension
            ),
            "native_attributes_json": _json(native),
            "provenance_ref": (
                f"contract001:{tx.hash}"
            ),
            "provenance_hash": None,
        })

        sides = (
            (
                "sender",
                group["sender_partner_ids"],
                tx.is_sender_external,
                -tx.amount,
            ),
            (
                "receiver",
                group["receiver_partner_ids"],
                tx.is_receiver_external,
                tx.amount,
            ),
        )

        for (
            side,
            partner_ids,
            is_external,
            amount,
        ) in sides:
            account_id = _endpoint_id(
                tx.hash,
                side,
            )

            sorted_partner_ids = sorted(
                partner_ids
            )

            account_attributes = {
                "side": side,
                "partner_ids": sorted_partner_ids,
                "is_external": is_external,
            }

            native_owner_id = None

            if len(sorted_partner_ids) == 1:
                native_owner_id = _actor_id(
                    sorted_partner_ids[0]
                )

            accounts.append({
                "account_id": account_id,
                "native_account_id": None,
                "native_account_number": None,
                "native_account_type": None,
                "native_account_kind": (
                    "normalized_transaction_endpoint"
                ),
                "native_status": None,
                "display_label": None,
                "native_owner_id": native_owner_id,
                "native_attributes_json": _json(
                    account_attributes
                ),
                "provenance_ref": (
                    f"contract001:{tx.hash}:{side}"
                ),
                "provenance_hash": None,
            })

            effects.append({
                "effect_id": f"{tx.hash}:{side}",
                "event_id": tx.hash,
                "account_id": account_id,
                "amount_minor": amount,
                "unit_code": spec.unit_code,
                "unit_exponent": spec.unit_exponent,
                "monetary_dimension": (
                    spec.monetary_dimension
                ),
                "origin": "derived",
                "native_effect_id": None,
                "native_attributes_json": _json(
                    account_attributes
                ),
                "provenance_ref": (
                    f"contract001:{tx.hash}:{side}"
                ),
                "provenance_hash": None,
            })

            for partner_id in sorted_partner_ids:
                actor_id = _actor_id(
                    partner_id
                )

                actors_by_id.setdefault(
                    actor_id,
                    {
                        "actor_id": actor_id,
                        "source_system": (
                            "normalized_transactions_contract"
                        ),
                        "native_actor_id": str(
                            partner_id
                        ),
                        "native_actor_kind": None,
                        "display_label": None,
                        "native_attributes_json": _json({
                            "partner_id": partner_id,
                        }),
                        "provenance_ref": (
                            "contract001:partner:"
                            f"{partner_id}"
                        ),
                        "provenance_hash": None,
                    },
                )

                identity_links.append({
                    "identity_link_id": (
                        f"{tx.hash}:{side}:"
                        f"partner:{partner_id}"
                    ),
                    "subject_kind": "account",
                    "subject_id": account_id,
                    "target_kind": "actor",
                    "target_id": actor_id,
                    "link_kind": (
                        "contract_partner_id"
                    ),
                    "status": "resolved",
                    "confidence": None,
                    "source_system": (
                        "normalized_transactions_contract"
                    ),
                    "valid_from": None,
                    "valid_to": None,
                    "evidence_json": _json({
                        "partner_id": partner_id,
                    }),
                })

    canonical = _json({
        "transactions": [
            _native_attributes(group)
            for group in groups
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
            "coverage_from": (
                min(occurred)
                if occurred
                else None
            ),
            "coverage_to": (
                max(occurred)
                if occurred
                else None
            ),
            "source_cursor": None,
            "source_snapshot_ref": source_snapshot_ref,
            "adapter_name": (
                "contract001-transactions"
            ),
            "adapter_version": "1",
            "content_hash": (
                hashlib.sha256(
                    canonical
                ).hexdigest()
            ),
        },
        accounts=accounts,
        events=events,
        effects=effects,
        actors=list(
            actors_by_id.values()
        ),
        identity_links=identity_links,
        capabilities={},
    )
