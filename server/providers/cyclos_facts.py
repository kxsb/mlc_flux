from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any


class CyclosFactsError(ValueError):
    """Payload Cyclos malformé ou incompatible avec les faits attendus."""


def _clean(value: Any) -> str | None:
    if value is None or value is False:
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

    native_currency_id: str | None
    amount_raw: str | None
    amount_decimal: Decimal | None

    native_transaction_type: str | None
    native_transaction_type_name: str | None
    native_transaction_kind: str | None
    native_creation_type: str | None

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
    if actor is None or actor is False:
        return None

    if not isinstance(actor, dict):
        raise CyclosFactsError(
            "Endpoint acteur Cyclos malformé : objet attendu."
        )

    actor_type = actor.get("type")
    if actor_type is None or actor_type is False:
        actor_type = {}
    elif not isinstance(actor_type, dict):
        raise CyclosFactsError(
            "Champ actor.type Cyclos malformé : objet attendu."
        )

    user = actor.get("user")
    if user is None or user is False:
        user = {}
    elif not isinstance(user, dict):
        raise CyclosFactsError(
            "Champ actor.user Cyclos malformé : objet attendu."
        )

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
    if not isinstance(transaction, dict):
        raise CyclosFactsError(
            "Transaction Cyclos malformée : objet attendu."
        )

    tx_type = transaction.get("type")
    if tx_type is None or tx_type is False:
        tx_type = {}
    elif not isinstance(tx_type, dict):
        raise CyclosFactsError(
            "Champ transaction.type Cyclos malformé : objet attendu."
        )

    amount_raw = _clean(transaction.get("amount"))
    native_type = _clean(tx_type.get("internalName"))
    native_type_name = _clean(tx_type.get("name"))
    native_kind = _clean(transaction.get("kind"))
    native_creation_type = _clean(
        transaction.get("creationType")
    )

    return CyclosTransactionFacts(
        transaction_id=_clean(transaction.get("id")),
        transaction_number=_clean(
            transaction.get("transactionNumber")
        ),
        occurred_at=_clean(transaction.get("date")),
        native_currency_id=_clean(transaction.get("currency")),
        amount_raw=amount_raw,
        amount_decimal=_decimal(amount_raw),
        native_transaction_type=native_type,
        native_transaction_type_name=native_type_name,
        native_transaction_kind=native_kind,
        native_creation_type=native_creation_type,
        native_transaction_label=(
            native_type_name
            or native_type
        ),
        native_transaction_group=(
            native_kind
            or native_creation_type
        ),
        source_actor=extract_cyclos_actor_facts(
            transaction.get("from")
        ),
        destination_actor=extract_cyclos_actor_facts(
            transaction.get("to")
        ),
    )
