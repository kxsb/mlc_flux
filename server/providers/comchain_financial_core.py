from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Iterable, Mapping

from server.providers.comchain_facts import (
    ComChainTransactionFacts,
    extract_comchain_transaction_facts,
)
_ETHEREUM_ADDRESS_RE = re.compile(
    r"^(?:0x)?([0-9a-fA-F]{40})$"
)


class ComChainIdentityError(ValueError):
    """Identité financière ComChain invalide."""


def _normalized_account_id(account_id: str) -> str:
    """
    Canonicalisation technique ComChain/Ethereum.

    Cette règle appartient au provider ComChain, pas à INPUT001
    ni au Financial Core générique.
    """
    if not isinstance(account_id, str):
        raise ComChainIdentityError(
            "Identifiant de compte ComChain non textuel."
        )

    if not account_id.strip():
        raise ComChainIdentityError(
            "Identifiant de compte ComChain vide."
        )

    match = _ETHEREUM_ADDRESS_RE.fullmatch(account_id)

    if match is not None:
        return match.group(1).lower()

    return account_id


class ComChainFinancialCoreError(ValueError):
    """Faits ComChain incompatibles avec Financial Core."""


@dataclass(frozen=True)
class ComChainFinancialCoreSpec:
    """
    Paramètres appartenant à l'installation, pas au provider générique.

    `monetary_dimension` reste explicite : le provider ne déduit pas
    EL/CM/nantissement à partir d'un simple nom de fonction.
    """

    native_currency_id: str
    unit_code: str
    unit_exponent: int
    monetary_dimension: str


@dataclass(frozen=True)
class ComChainFinancialCoreBatch:
    accounts: tuple[dict[str, Any], ...]
    events: tuple[dict[str, Any], ...]
    account_effects: tuple[dict[str, Any], ...]


def _required_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ComChainFinancialCoreError(
            f"{label} doit être renseigné."
        )
    return value.strip()


def _validate_spec(
    spec: ComChainFinancialCoreSpec,
) -> None:
    _required_text(
        spec.native_currency_id,
        "native_currency_id",
    )
    _required_text(spec.unit_code, "unit_code")
    _required_text(
        spec.monetary_dimension,
        "monetary_dimension",
    )

    if (
        not isinstance(spec.unit_exponent, int)
        or isinstance(spec.unit_exponent, bool)
        or spec.unit_exponent < 0
    ):
        raise ComChainFinancialCoreError(
            "unit_exponent doit être un entier positif ou nul."
        )


def _event_time(
    transaction: ComChainTransactionFacts,
) -> datetime:
    if transaction.received_at_epoch is None:
        raise ComChainFinancialCoreError(
            "Transaction ComChain sans received_at."
        )

    try:
        return datetime.fromtimestamp(
            transaction.received_at_epoch,
            tz=UTC,
        )
    except (OverflowError, OSError, ValueError) as exc:
        raise ComChainFinancialCoreError(
            "received_at ComChain invalide."
        ) from exc


def _exact_minor_amount(
    transaction: ComChainTransactionFacts,
) -> int:
    amount = transaction.amount_decimal

    if amount is None or not amount.is_finite():
        raise ComChainFinancialCoreError(
            "Montant ComChain absent ou invalide."
        )

    integral = amount.to_integral_value()

    if integral != amount:
        raise ComChainFinancialCoreError(
            "Le montant ComChain natif n'est pas entier."
        )

    value = int(integral)

    if value < 0:
        raise ComChainFinancialCoreError(
            "Le transfert ComChain porte un montant négatif."
        )

    if value > 2**63 - 1:
        raise ComChainFinancialCoreError(
            "Montant ComChain hors plage BIGINT."
        )

    return value


def _account_id(value: str | None, label: str) -> str:
    if value is None:
        raise ComChainFinancialCoreError(
            f"Transaction ComChain sans {label}."
        )

    try:
        return _normalized_account_id(value)
    except ComChainIdentityError as exc:
        raise ComChainFinancialCoreError(
            f"Identité ComChain invalide pour {label}."
        ) from exc


def _native_attributes(
    transaction: ComChainTransactionFacts,
) -> str:
    """
    Conserve les faits nécessaires à une réinterprétation future.

    On ne réduit pas la provenance au seul hash.
    """
    payload = {
        "hash": transaction.transaction_hash,
        "block": transaction.block_number,
        "received_at": transaction.received_at_epoch,
        "caller": transaction.caller,
        "contract": transaction.contract,
        "contract_abi": transaction.contract_abi,
        "type": transaction.native_transaction_type,
        "sender": transaction.sender,
        "receiver": transaction.receiver,
        "amount": transaction.amount_raw,
        "fn": transaction.function_name,
        "fn_abi": transaction.function_abi,
        "status": transaction.native_status,
        "native_currency_id": transaction.native_currency_id,
    }

    return json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _transaction_to_rows(
    transaction: ComChainTransactionFacts,
    *,
    spec: ComChainFinancialCoreSpec,
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
]:
    """
    Produit un événement et deux effets natifs.

    Cette projection n'affirme pas que l'événement est un "paiement".
    Elle représente seulement le mouvement sender -> receiver exposé
    par la source ComChain `type=transfer`.
    """
    tx_hash = _required_text(
        transaction.transaction_hash,
        "transaction_hash",
    )

    if transaction.native_transaction_type != "transfer":
        raise ComChainFinancialCoreError(
            "FINCORE003 ne projette pour l'instant que les "
            "lignes ComChain natives de type 'transfer'."
        )

    if transaction.block_number is None:
        raise ComChainFinancialCoreError(
            "Transaction ComChain sans block."
        )

    sender = _account_id(
        transaction.sender,
        "sender",
    )
    receiver = _account_id(
        transaction.receiver,
        "receiver",
    )

    amount = _exact_minor_amount(transaction)
    occurred_at = _event_time(transaction)

    event = {
        "event_id": tx_hash,
        "native_event_id": tx_hash,
        "native_event_number": str(
            transaction.block_number
        ),
        "event_kind": "native_transfer",
        "native_event_type": (
            transaction.native_transaction_type
        ),
        "native_event_subtype": (
            transaction.function_abi
            or transaction.function_name
        ),
        "native_method": transaction.function_name,
        "native_status": transaction.native_status,
        # status='' n'est pas interprété comme confirmation.
        "execution_state": "unknown",
        "time_precision": "instant",
        "occurred_at": occurred_at,
        "occurred_date": None,
        "business_timezone": None,
        "native_amount_minor": amount,
        "native_unit_code": spec.unit_code,
        "native_unit_exponent": spec.unit_exponent,
        "native_monetary_dimension": (
            spec.monetary_dimension
        ),
        "native_attributes_json": (
            _native_attributes(transaction)
        ),
        "provenance_ref": f"comchain:tx:{tx_hash}",
        "provenance_hash": None,
    }

    common_effect = {
        "event_id": tx_hash,
        "unit_code": spec.unit_code,
        "unit_exponent": spec.unit_exponent,
        "monetary_dimension": spec.monetary_dimension,
        "origin": "native",
        "native_effect_id": None,
        "native_attributes_json": (
            _native_attributes(transaction)
        ),
        "provenance_ref": f"comchain:tx:{tx_hash}",
        "provenance_hash": None,
    }

    debit = {
        **common_effect,
        "effect_id": f"{tx_hash}:sender",
        "account_id": sender,
        "amount_minor": -amount,
    }

    credit = {
        **common_effect,
        "effect_id": f"{tx_hash}:receiver",
        "account_id": receiver,
        "amount_minor": amount,
    }

    return event, debit, credit


def build_comchain_financial_core_batch(
    rows: Iterable[Mapping[str, Any]],
    *,
    spec: ComChainFinancialCoreSpec,
) -> ComChainFinancialCoreBatch:
    """
    Normalise des lignes natives pyc3l/ComChain en faits Financial Core.

    Odoo n'intervient jamais dans cette fonction.
    """
    _validate_spec(spec)

    accounts_by_id: dict[str, dict[str, Any]] = {}
    events: list[dict[str, Any]] = []
    effects: list[dict[str, Any]] = []
    event_ids: set[str] = set()

    for row in rows:
        facts = extract_comchain_transaction_facts(
            row,
            native_currency_id=spec.native_currency_id,
        )

        event, debit, credit = _transaction_to_rows(
            facts,
            spec=spec,
        )

        event_id = event["event_id"]

        if event_id in event_ids:
            raise ComChainFinancialCoreError(
                "Hash ComChain dupliqué dans la source : "
                f"{event_id!r}"
            )

        event_ids.add(event_id)
        events.append(event)
        effects.extend((debit, credit))

        for effect in (debit, credit):
            account_id = effect["account_id"]

            accounts_by_id.setdefault(
                account_id,
                {
                    "account_id": account_id,
                    "native_account_id": account_id,
                    "native_account_number": None,
                    "native_account_type": None,
                    "native_account_kind": None,
                    "native_status": None,
                    "display_label": None,
                    "native_owner_id": None,
                    "native_attributes_json": None,
                    "provenance_ref": (
                        f"comchain:account:{account_id}"
                    ),
                    "provenance_hash": None,
                },
            )

    return ComChainFinancialCoreBatch(
        accounts=tuple(
            accounts_by_id[key]
            for key in sorted(accounts_by_id)
        ),
        events=tuple(events),
        account_effects=tuple(effects),
    )
