from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Mapping, Sequence

from server.input_contract.writer import FinancialDatasetPayload
from server.providers.cyclos_facts import (
    CyclosTransactionFacts,
    extract_cyclos_transaction_facts,
)
from server.providers.cyclos_normalized import (
    CyclosCurrencySpec,
    cyclos_account_row,
    cyclos_transaction_row,
)


class CyclosDatasetError(ValueError):
    """Un ensemble de faits Cyclos ne peut pas former un dataset cohérent."""


_ACCOUNT_FACT_FIELDS = (
    "native_account_number",
    "native_account_type",
    "native_status",
    "display_label",
    "native_owner_id",
)


def _optional_utc_instant(
    value: datetime | None,
    *,
    field: str,
) -> datetime | None:
    if value is None:
        return None

    if value.tzinfo is None or value.utcoffset() is None:
        raise CyclosDatasetError(
            f"{field} doit être timezone-aware."
        )

    return value.astimezone(UTC)


def _merge_account_row(
    registry: dict[str, dict[str, Any]],
    incoming: dict[str, Any] | None,
) -> None:
    if incoming is None:
        return

    account_id = incoming["account_id"]
    current = registry.get(account_id)

    if current is None:
        registry[account_id] = dict(incoming)
        return

    if current.get("source_system") != incoming.get("source_system"):
        raise CyclosDatasetError(
            f"Compte Cyclos {account_id!r} avec source_system contradictoire."
        )

    for field in _ACCOUNT_FACT_FIELDS:
        old = current.get(field)
        new = incoming.get(field)

        if old is None and new is not None:
            current[field] = new
            continue

        if new is None or old == new:
            continue

        raise CyclosDatasetError(
            f"Compte Cyclos {account_id!r} avec fait natif "
            f"contradictoire pour {field!r}: {old!r} / {new!r}"
        )


def _register_transaction_accounts(
    registry: dict[str, dict[str, Any]],
    transaction: CyclosTransactionFacts,
) -> None:
    _merge_account_row(
        registry,
        cyclos_account_row(transaction.source_actor),
    )
    _merge_account_row(
        registry,
        cyclos_account_row(transaction.destination_actor),
    )


def build_cyclos_financial_dataset(
    raw_transactions: Sequence[Mapping[str, Any]],
    *,
    dataset_id: str,
    currency_specs: Mapping[str, CyclosCurrencySpec],
    snapshot_ref: str | None = None,
    coverage_from: datetime | None = None,
    coverage_to: datetime | None = None,
) -> FinancialDatasetPayload:
    """
    Construit un payload INPUT001 à partir de transactions Cyclos brutes.

    Ce bridge :
    - ne fait aucune anonymisation ;
    - ne classe aucun acteur P/U/UD/T/X ;
    - ne dépend d'aucun profil MLC ;
    - ne déduit aucune capacité optionnelle inexistante dans la source.

    Les bornes coverage_* ne sont jamais inférées automatiquement :
    elles doivent être fournies explicitement par l'appelant lorsque
    celui-ci sait que la requête source couvre réellement cette période.
    """
    if not isinstance(dataset_id, str) or not dataset_id.strip():
        raise CyclosDatasetError(
            "dataset_id Cyclos doit être renseigné."
        )

    accounts_by_id: dict[str, dict[str, Any]] = {}
    normalized_transactions: list[dict[str, Any]] = []
    transaction_ids: set[str] = set()

    for index, raw in enumerate(raw_transactions):
        if not isinstance(raw, Mapping):
            raise CyclosDatasetError(
                f"Transaction Cyclos brute #{index} invalide."
            )

        # L'extracteur Cyclos attend actuellement un dict concret.
        facts = extract_cyclos_transaction_facts(dict(raw))

        transaction_row = cyclos_transaction_row(
            facts,
            currency_specs=currency_specs,
        )

        transaction_id = transaction_row["transaction_id"]

        if transaction_id in transaction_ids:
            raise CyclosDatasetError(
                "Transaction Cyclos dupliquée dans le dataset : "
                f"{transaction_id!r}"
            )

        transaction_ids.add(transaction_id)

        _register_transaction_accounts(
            accounts_by_id,
            facts,
        )

        normalized_transactions.append(transaction_row)

    metadata: dict[str, Any] = {
        "dataset_id": dataset_id,
        "contract_version": "input001-v0.1",
        "source_system": "cyclos",
        "coverage_from": _optional_utc_instant(
            coverage_from,
            field="coverage_from",
        ),
        "coverage_to": _optional_utc_instant(
            coverage_to,
            field="coverage_to",
        ),
        "snapshot_ref": snapshot_ref,
        "account_state_history": False,
        "balances": False,
        "account_replacements": False,
    }

    return FinancialDatasetPayload(
        dataset_metadata=metadata,
        accounts=[
            accounts_by_id[account_id]
            for account_id in sorted(accounts_by_id)
        ],
        transactions=normalized_transactions,
    )
