from __future__ import annotations

from typing import Any

from server.providers.comchain_facts import ComChainTransactionFacts


class ComChainIdentityError(ValueError):
    """Une identité financière ComChain ne peut pas être normalisée."""


def comchain_account_row(
    account_id: str | None,
) -> dict[str, Any] | None:
    """
    Convertit un endpoint financier ComChain vers une ligne `accounts`.

    Décision actuelle :
    - account_id = adresse / identifiant sender ou receiver tel que fourni ;
    - aucune normalisation de casse ;
    - aucun retrait du préfixe 0x ;
    - aucun rapprochement Odoo ;
    - aucun propriétaire inventé ;
    - aucune classification P/U/T/X.

    L'espace d'identités est qualifié par dataset_id au niveau INPUT001.
    """
    if account_id is None:
        return None

    if not isinstance(account_id, str):
        raise ComChainIdentityError(
            "Identifiant de compte ComChain non textuel."
        )

    if not account_id.strip():
        raise ComChainIdentityError(
            "Identifiant de compte ComChain vide."
        )

    return {
        "account_id": account_id,
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
