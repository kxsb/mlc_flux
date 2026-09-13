from __future__ import annotations

from typing import Any

from server.providers.cyclos_facts import CyclosActorFacts


class CyclosIdentityError(ValueError):
    """Un acteur Cyclos présent ne fournit pas d'identité de compte stable."""


def cyclos_account_row(
    actor: CyclosActorFacts | None,
) -> dict[str, Any] | None:
    """
    Convertit un acteur Cyclos natif vers une ligne `accounts`
    du contrat financier normalisé.

    Décision étayée sur Gonette + Graine :
    - account_id = actor.id
    - native_account_number = actor.number
    - native_owner_id = actor.user.id
    - native_account_type = actor.type.internalName

    Aucun fallback de account_id vers actor.number ou actor.user.id.
    """
    if actor is None:
        return None

    if not actor.actor_id:
        raise CyclosIdentityError(
            "Acteur Cyclos présent sans actor.id : "
            "impossible de produire un account_id stable."
        )

    return {
        "account_id": actor.actor_id,
        "native_account_number": actor.actor_number,
        "native_account_type": actor.native_account_type,
        "native_account_kind": actor.native_account_kind,
        "native_account_type_label": actor.native_account_type_label,
        "native_status": None,
        "display_label": actor.user_display,
        "native_owner_id": actor.user_id,
        "source_system": "cyclos",
    }


from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Mapping

from server.providers.cyclos_facts import CyclosTransactionFacts


class CyclosTransactionError(ValueError):
    """Une transaction Cyclos ne peut pas être normalisée sans perte."""


@dataclass(frozen=True)
class CyclosCurrencySpec:
    native_currency_id: str
    currency_code: str
    currency_exponent: int


def _parse_occurred_at(value: str | None) -> datetime:
    if not value:
        raise CyclosTransactionError("Transaction Cyclos sans date.")

    try:
        parsed = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )
    except ValueError as exc:
        raise CyclosTransactionError(
            f"Date Cyclos invalide : {value!r}"
        ) from exc

    if parsed.tzinfo is None:
        raise CyclosTransactionError(
            "Date Cyclos sans fuseau horaire."
        )

    return parsed.astimezone(UTC)


BIGINT_MIN = -(2**63)
BIGINT_MAX = 2**63 - 1


def _amount_minor(
    amount: Decimal | None,
    exponent: int,
) -> int:
    if amount is None:
        raise CyclosTransactionError(
            "Montant Cyclos absent ou invalide."
        )

    if not isinstance(exponent, int) or isinstance(exponent, bool):
        raise CyclosTransactionError(
            "currency_exponent invalide."
        )

    if exponent < 0:
        raise CyclosTransactionError(
            "currency_exponent négatif."
        )

    if not amount.is_finite():
        raise CyclosTransactionError(
            "Montant Cyclos non fini."
        )

    sign, digits, decimal_exponent = amount.as_tuple()

    coefficient = 0
    for digit in digits:
        coefficient = coefficient * 10 + digit

    scaled_exponent = decimal_exponent + exponent

    if scaled_exponent >= 0:
        result = coefficient * (10 ** scaled_exponent)
    else:
        divisor = 10 ** (-scaled_exponent)

        if coefficient % divisor:
            raise CyclosTransactionError(
                "Le montant Cyclos possède une précision supérieure "
                "à celle déclarée pour la devise."
            )

        result = coefficient // divisor

    if sign:
        result = -result

    if result < BIGINT_MIN or result > BIGINT_MAX:
        raise CyclosTransactionError(
            "Montant Cyclos hors plage BIGINT signée."
        )

    return result


def cyclos_transaction_row(
    transaction: CyclosTransactionFacts,
    *,
    currency_specs: Mapping[str, CyclosCurrencySpec],
) -> dict[str, Any]:
    """
    Convertit des faits transactionnels Cyclos vers le contrat normalisé.

    La devise native n'est jamais assimilée implicitement à un code
    de devise MLCFlux.
    """
    if not transaction.transaction_id:
        raise CyclosTransactionError(
            "Transaction Cyclos sans transaction.id."
        )

    native_currency_id = transaction.native_currency_id

    if not native_currency_id:
        raise CyclosTransactionError(
            "Transaction Cyclos sans currency."
        )

    spec = currency_specs.get(native_currency_id)
    if spec is None:
        raise CyclosTransactionError(
            "Devise Cyclos inconnue : "
            f"{native_currency_id!r}"
        )

    if spec.native_currency_id != native_currency_id:
        raise CyclosTransactionError(
            "Spécification de devise incohérente."
        )

    source = cyclos_account_row(transaction.source_actor)
    destination = cyclos_account_row(
        transaction.destination_actor
    )

    return {
        "transaction_id": transaction.transaction_id,
        "native_transaction_number": (
            transaction.transaction_number
        ),
        "occurred_at": _parse_occurred_at(
            transaction.occurred_at
        ),
        "source_account_id": (
            source["account_id"] if source else None
        ),
        "destination_account_id": (
            destination["account_id"]
            if destination else None
        ),
        "amount_minor": _amount_minor(
            transaction.amount_decimal,
            spec.currency_exponent,
        ),
        "native_currency_id": native_currency_id,
        "currency_code": spec.currency_code,
        "currency_exponent": spec.currency_exponent,
        "native_transaction_type": (
            transaction.native_transaction_type
        ),
        "native_transaction_label": (
            transaction.native_transaction_label
        ),
        "native_transaction_group": (
            transaction.native_transaction_group
        ),
        "native_transaction_description": (
            transaction.native_transaction_description
        ),
    }
