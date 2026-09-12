from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any


def _clean(value: Any) -> str | None:
    if value in (None, False):
        return None

    text = str(value).strip()
    return text or None


def _decimal(value: Any) -> Decimal | None:
    text = _clean(value)
    if text is None:
        return None

    try:
        return Decimal(text.replace(",", "."))
    except InvalidOperation:
        return None


@dataclass(frozen=True)
class CyclosActorFacts:
    actor_id: str | None
    actor_number: str | None
    native_account_type: str | None
    user_id: str | None
    user_display: str | None


@dataclass(frozen=True)
class CyclosTransactionFacts:
    transaction_id: str | None
    transaction_number: str | None
    occurred_at: str | None

    amount_raw: str | None
    amount_decimal: Decimal | None

    native_transaction_type: str | None
    native_transaction_label: str | None
    native_transaction_group: str | None

    source_actor: CyclosActorFacts | None
    destination_actor: CyclosActorFacts | None


def extract_cyclos_actor_facts(
    actor: dict[str, Any] | None,
) -> CyclosActorFacts | None:
    """
    Extrait uniquement les faits natifs utiles d'un acteur Cyclos.

    Aucune classification MLCFlux, aucun mapping et aucune pseudonymisation
    ne doivent être réalisés ici.
    """
    if not isinstance(actor, dict):
        return None

    actor_type = actor.get("type")
    if not isinstance(actor_type, dict):
        actor_type = {}

    user = actor.get("user")
    if not isinstance(user, dict):
        user = {}

    return CyclosActorFacts(
        actor_id=_clean(actor.get("id")),
        actor_number=_clean(actor.get("number")),
        native_account_type=_clean(actor_type.get("internalName")),
        user_id=_clean(user.get("id")),
        user_display=_clean(user.get("display")),
    )


def extract_cyclos_transaction_facts(
    transaction: dict[str, Any],
) -> CyclosTransactionFacts:
    """
    Extrait les faits natifs utilisés aujourd'hui par le pipeline Cyclos.

    Cette fonction est volontairement pure :
    - pas d'accès réseau ;
    - pas d'accès DB ;
    - pas de lecture du profil MLC ;
    - pas de résolution P/U/UD/T/X ;
    - pas de création de références ou pseudonymes.
    """
    tx_type = transaction.get("type")
    if not isinstance(tx_type, dict):
        tx_type = {}

    amount_raw = _clean(transaction.get("amount"))

    return CyclosTransactionFacts(
        transaction_id=_clean(transaction.get("id")),
        transaction_number=_clean(
            transaction.get("transactionNumber")
        ),
        occurred_at=_clean(transaction.get("date")),
        amount_raw=amount_raw,
        amount_decimal=_decimal(amount_raw),
        native_transaction_type=_clean(
            tx_type.get("internalName")
        ),
        native_transaction_label=(
            _clean(tx_type.get("name"))
            or _clean(tx_type.get("internalName"))
        ),
        native_transaction_group=(
            _clean(transaction.get("kind"))
            or _clean(transaction.get("creationType"))
        ),
        source_actor=extract_cyclos_actor_facts(
            transaction.get("from")
        ),
        destination_actor=extract_cyclos_actor_facts(
            transaction.get("to")
        ),
    )
