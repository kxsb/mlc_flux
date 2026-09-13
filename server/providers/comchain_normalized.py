from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Mapping

from server.providers.comchain_facts import ComChainTransactionFacts


class ComChainIdentityError(ValueError):
    """Une identité financière ComChain ne peut pas être normalisée."""


_ETHEREUM_ADDRESS_RE = re.compile(
    r"^(?:0x)?([0-9a-fA-F]{40})$"
)


def _normalized_account_id(account_id: str) -> str:
    """
    Canonicalisation propre au provider ComChain.

    Une adresse Ethereum reconnue est représentée par ses 40 chiffres
    hexadécimaux en minuscules, sans préfixe 0x.

    Les identifiants non-Ethereum (par exemple une éventuelle sentinelle
    native comme `admin`) restent opaques et sont conservés tels quels.
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


def comchain_account_row(
    account_id: str | None,
) -> dict[str, Any] | None:
    """
    Convertit un endpoint financier ComChain vers une ligne `accounts`.

    Décision actuelle :
    - une adresse Ethereum reconnue est canonicalisée en 40 hex
      minuscules sans préfixe 0x ;
    - un identifiant non-Ethereum reste opaque et inchangé ;
    - aucun rapprochement Odoo ;
    - aucun propriétaire inventé ;
    - aucune classification P/U/T/X.

    L'espace d'identités est qualifié par dataset_id au niveau INPUT001.
    """
    if account_id is None:
        return None

    normalized_account_id = _normalized_account_id(
        account_id
    )

    return {
        "account_id": normalized_account_id,
        "native_account_number": None,
        "native_account_type": None,
        "native_status": None,
        "display_label": None,
        "native_owner_id": None,
        "source_system": "comchain",
    }


def comchain_transaction_account_rows(
    transaction: ComChainTransactionFacts,
) -> tuple[
    dict[str, Any] | None,
    dict[str, Any] | None,
]:
    """
    Retourne les comptes source / destination observés par la transaction.

    `caller` n'est pas utilisé ici : le signataire / appelant d'une
    opération n'est pas nécessairement le compte financier débité.
    """
    source = comchain_account_row(transaction.sender)
    destination = comchain_account_row(transaction.receiver)

    return source, destination


class ComChainTransactionError(ValueError):
    """Une transaction ComChain ne peut pas être normalisée sans perte."""


@dataclass(frozen=True)
class ComChainCurrencySpec:
    native_currency_id: str
    currency_code: str
    currency_exponent: int

    # Convention de la source considérée.
    # pyc3l-cli / Lokavaluto expose actuellement `amount`
    # directement dans l'unité minimale.
    amount_representation: str


BIGINT_MIN = -(2**63)
BIGINT_MAX = 2**63 - 1


def _minor_amount(
    amount: Decimal | None,
    *,
    representation: str,
) -> int:
    if amount is None:
        raise ComChainTransactionError(
            "Montant ComChain absent ou invalide."
        )

    if representation != "minor":
        raise ComChainTransactionError(
            "Représentation monétaire ComChain non supportée : "
            f"{representation!r}"
        )

    if not amount.is_finite():
        raise ComChainTransactionError(
            "Montant ComChain non fini."
        )

    sign, digits, decimal_exponent = amount.as_tuple()

    coefficient = 0
    for digit in digits:
        coefficient = coefficient * 10 + digit

    if decimal_exponent >= 0:
        result = coefficient * (10 ** decimal_exponent)
    else:
        divisor = 10 ** (-decimal_exponent)

        if coefficient % divisor:
            raise ComChainTransactionError(
                "Le montant ComChain déclaré en unité minimale "
                "n'est pas entier."
            )

        result = coefficient // divisor

    if sign:
        result = -result

    if result < BIGINT_MIN or result > BIGINT_MAX:
        raise ComChainTransactionError(
            "Montant ComChain hors plage BIGINT signée."
        )

    return result


def _received_at(
    epoch: int | None,
) -> datetime:
    if epoch is None:
        raise ComChainTransactionError(
            "Transaction ComChain sans received_at."
        )

    try:
        return datetime.fromtimestamp(epoch, tz=UTC)
    except (OverflowError, OSError, ValueError) as exc:
        raise ComChainTransactionError(
            f"received_at ComChain invalide : {epoch!r}"
        ) from exc


def comchain_transaction_row(
    transaction: ComChainTransactionFacts,
    *,
    currency_specs: Mapping[str, ComChainCurrencySpec],
) -> dict[str, Any]:
    """
    Convertit une transaction ComChain native vers INPUT001.

    Décisions pour le stockage pyc3l-cli actuellement observé :

    - transaction_id = hash natif ;
    - sender / receiver = endpoints financiers ;
    - received_at = epoch UTC ;
    - amount doit être explicitement déclaré comme déjà exprimé
      en unité minimale ;
    - caller, contract, block, fn et ABI restent des faits natifs
      récupérables par le hash et ne sont pas réinterprétés dans
      des champs génériques dont la sémantique serait différente.
    """
    if not transaction.transaction_hash:
        raise ComChainTransactionError(
            "Transaction ComChain sans hash."
        )

    if transaction.block_number is None:
        raise ComChainTransactionError(
            "Transaction ComChain sans numéro de bloc."
        )

    native_currency_id = transaction.native_currency_id

    if not native_currency_id:
        raise ComChainTransactionError(
            "Transaction ComChain sans devise native."
        )

    spec = currency_specs.get(native_currency_id)

    if spec is None:
        raise ComChainTransactionError(
            "Devise ComChain inconnue : "
            f"{native_currency_id!r}"
        )

    if spec.native_currency_id != native_currency_id:
        raise ComChainTransactionError(
            "Spécification de devise ComChain incohérente."
        )

    if (
        not isinstance(spec.currency_exponent, int)
        or isinstance(spec.currency_exponent, bool)
        or spec.currency_exponent < 0
    ):
        raise ComChainTransactionError(
            "currency_exponent ComChain invalide."
        )

    source, destination = comchain_transaction_account_rows(
        transaction
    )

    return {
        "transaction_id": transaction.transaction_hash,
        "native_transaction_number": None,
        "occurred_at": _received_at(
            transaction.received_at_epoch
        ),
        "source_account_id": (
            source["account_id"]
            if source is not None
            else None
        ),
        "destination_account_id": (
            destination["account_id"]
            if destination is not None
            else None
        ),
        "amount_minor": _minor_amount(
            transaction.amount_decimal,
            representation=spec.amount_representation,
        ),
        "native_currency_id": native_currency_id,
        "currency_code": spec.currency_code,
        "currency_exponent": spec.currency_exponent,
        "native_transaction_type": (
            transaction.native_transaction_type
        ),
        "native_transaction_label": None,
        "native_transaction_group": None,
    }
