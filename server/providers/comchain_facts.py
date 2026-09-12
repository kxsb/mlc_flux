from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping


class ComChainFactsError(ValueError):
    """Payload ComChain malformé ou incompatible avec les faits attendus."""


def _text(value: Any, *, field: str) -> str | None:
    if value is None:
        return None

    if isinstance(value, (bool, dict, list, tuple, set)):
        raise ComChainFactsError(
            f"Champ ComChain {field!r} invalide."
        )

    # Identifiant opaque : aucune normalisation de casse,
    # préfixe ou whitespace dans la couche de faits.
    return str(value)


def _integer(value: Any, *, field: str) -> int | None:
    if value is None:
        return None

    if isinstance(value, bool):
        raise ComChainFactsError(
            f"Champ ComChain {field!r} invalide."
        )

    if isinstance(value, int):
        return value

    if isinstance(value, str):
        try:
            return int(value, 10)
        except ValueError as exc:
            raise ComChainFactsError(
                f"Champ ComChain {field!r} non entier."
            ) from exc

    raise ComChainFactsError(
        f"Champ ComChain {field!r} non entier."
    )


def _amount(value: Any) -> tuple[str | None, Decimal | None]:
    if value is None:
        return None, None

    # Un float binaire détruirait la garantie d'exactitude.
    if isinstance(value, (bool, float)):
        raise ComChainFactsError(
            "Montant ComChain fourni sous une forme non exacte."
        )

    if not isinstance(value, (str, int, Decimal)):
        raise ComChainFactsError(
            "Montant ComChain fourni sous une forme invalide."
        )

    raw = str(value)

    try:
        parsed = Decimal(raw)
    except InvalidOperation as exc:
        raise ComChainFactsError(
            "Montant ComChain invalide."
        ) from exc

    if not parsed.is_finite():
        raise ComChainFactsError(
            "Montant ComChain non fini."
        )

    return raw, parsed


@dataclass(frozen=True)
class ComChainTransactionFacts:
    transaction_hash: str | None
    block_number: int | None
    received_at_epoch: int | None

    native_currency_id: str | None

    caller: str | None
    contract: str | None
    contract_abi: str | None

    native_transaction_type: str | None

    sender: str | None
    receiver: str | None

    amount_raw: str | None
    amount_decimal: Decimal | None

    function_name: str | None
    function_abi: str | None
    native_status: str | None


def extract_comchain_transaction_facts(
    row: Mapping[str, Any],
    *,
    native_currency_id: str | None,
) -> ComChainTransactionFacts:
    """
    Extrait uniquement les faits natifs d'une transaction ComChain.

    `native_currency_id` est fourni explicitement par le contexte du
    store : la table `transactions` de pyc3l-cli ne porte pas la devise
    sur chaque ligne.

    Aucune classification MLCFlux, aucun rapprochement Odoo et aucune
    normalisation d'adresse ne sont réalisés ici.
    """
    if not isinstance(row, Mapping):
        raise ComChainFactsError(
            "Transaction ComChain malformée : mapping attendu."
        )

    amount_raw, amount_decimal = _amount(row.get("amount"))

    return ComChainTransactionFacts(
        transaction_hash=_text(
            row.get("hash"),
            field="hash",
        ),
        block_number=_integer(
            row.get("block"),
            field="block",
        ),
        received_at_epoch=_integer(
            row.get("received_at"),
            field="received_at",
        ),
        native_currency_id=_text(
            native_currency_id,
            field="native_currency_id",
        ),
        caller=_text(
            row.get("caller"),
            field="caller",
        ),
        contract=_text(
            row.get("contract"),
            field="contract",
        ),
        contract_abi=_text(
            row.get("contract_abi"),
            field="contract_abi",
        ),
        native_transaction_type=_text(
            row.get("type"),
            field="type",
        ),
        sender=_text(
            row.get("sender"),
            field="sender",
        ),
        receiver=_text(
            row.get("receiver"),
            field="receiver",
        ),
        amount_raw=amount_raw,
        amount_decimal=amount_decimal,
        function_name=_text(
            row.get("fn"),
            field="fn",
        ),
        function_abi=_text(
            row.get("fn_abi"),
            field="fn_abi",
        ),
        native_status=_text(
            row.get("status"),
            field="status",
        ),
    )
