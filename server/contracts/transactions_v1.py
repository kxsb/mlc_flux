from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping


CONTRACT_VERSION = "TRANSACTIONS001"

CONTRACT_COLUMNS = (
    "amount",
    "received_at",
    "hash",
    "fn_abi",
    "type",
    "sender_partner_id",
    "receiver_partner_id",
    "is_sender_external",
    "is_receiver_external",
)


class TransactionContractError(ValueError):
    """Une ligne ne respecte pas TRANSACTIONS001."""


@dataclass(frozen=True)
class TransactionContractRow:
    """
    Une transaction financière normalisée pour MLCFlux.

    Ce contrat ne connaît pas :
    - les wallets ComChain ;
    - les comptes Cyclos ;
    - res_partner_backend ;
    - les détails du backend financier.

    Les partner_id sont les identifiants administratifs fournis
    directement par le producteur du contrat.
    """

    amount: int
    received_at: int
    hash: str
    fn_abi: str | None
    type: str | None
    sender_partner_id: int | None
    receiver_partner_id: int | None
    is_sender_external: bool
    is_receiver_external: bool


def _required_int(value: Any, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TransactionContractError(
            f"{label} doit être un entier."
        )

    return value


def _optional_partner_id(
    value: Any,
    label: str,
) -> int | None:
    if value is None:
        return None

    result = _required_int(value, label)

    if result <= 0:
        raise TransactionContractError(
            f"{label} doit être positif lorsqu'il est renseigné."
        )

    return result


def _required_bool(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise TransactionContractError(
            f"{label} doit être booléen."
        )

    return value


def _optional_text(
    value: Any,
    label: str,
) -> str | None:
    if value is None:
        return None

    if not isinstance(value, str):
        raise TransactionContractError(
            f"{label} doit être textuel ou NULL."
        )

    return value


def transaction_from_mapping(
    row: Mapping[str, Any],
) -> TransactionContractRow:
    """
    Valide une ligne SQL déjà normalisée.

    Aucune interprétation métier supplémentaire n'est effectuée.
    """
    unknown = set(row) - set(CONTRACT_COLUMNS)

    if unknown:
        raise TransactionContractError(
            "Colonnes inconnues dans TRANSACTIONS001 : "
            + ", ".join(sorted(unknown))
        )

    missing = set(CONTRACT_COLUMNS) - set(row)

    if missing:
        raise TransactionContractError(
            "Colonnes absentes dans TRANSACTIONS001 : "
            + ", ".join(sorted(missing))
        )

    tx_hash = row["hash"]

    if not isinstance(tx_hash, str) or not tx_hash.strip():
        raise TransactionContractError(
            "hash doit être un texte non vide."
        )

    received_at = _required_int(
        row["received_at"],
        "received_at",
    )

    if received_at < 0:
        raise TransactionContractError(
            "received_at doit être positif ou nul."
        )

    return TransactionContractRow(
        amount=_required_int(
            row["amount"],
            "amount",
        ),
        received_at=received_at,
        hash=tx_hash.strip(),
        fn_abi=_optional_text(
            row["fn_abi"],
            "fn_abi",
        ),
        type=_optional_text(
            row["type"],
            "type",
        ),
        sender_partner_id=_optional_partner_id(
            row["sender_partner_id"],
            "sender_partner_id",
        ),
        receiver_partner_id=_optional_partner_id(
            row["receiver_partner_id"],
            "receiver_partner_id",
        ),
        is_sender_external=_required_bool(
            row["is_sender_external"],
            "is_sender_external",
        ),
        is_receiver_external=_required_bool(
            row["is_receiver_external"],
            "is_receiver_external",
        ),
    )


def normalize_transaction_rows(
    rows: Iterable[Mapping[str, Any]],
) -> tuple[TransactionContractRow, ...]:
    """
    Valide les lignes et impose le grain contractuel par hash.

    Tolérance temporaire pour les fixtures Lokavaluto :
    des doublons strictement identiques sont éliminés.

    Si un même hash porte deux contenus différents, le contrat est
    ambigu et l'ingestion échoue explicitement.
    """
    by_hash: dict[str, TransactionContractRow] = {}

    for row in rows:
        transaction = transaction_from_mapping(row)

        previous = by_hash.get(transaction.hash)

        if previous is None:
            by_hash[transaction.hash] = transaction
            continue

        if previous != transaction:
            raise TransactionContractError(
                "Plusieurs lignes divergentes portent le même hash : "
                f"{transaction.hash!r}."
            )

    return tuple(
        sorted(
            by_hash.values(),
            key=lambda transaction: (
                transaction.received_at,
                transaction.hash,
            ),
        )
    )
