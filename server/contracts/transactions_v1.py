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
    Une ligne de la relation SQL normalisée TRANSACTIONS001.

    Le hash identifie l'événement financier.

    sender_partner_id et receiver_partner_id décrivent les associations
    administratives exposées par le producteur pour cette ligne.

    Plusieurs lignes peuvent donc porter le même hash lorsqu'un endpoint
    financier est associé à plusieurs partenaires administratifs.

    Les faits financiers d'un même hash doivent rester identiques.
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


def transaction_event_signature(
    transaction: TransactionContractRow,
) -> tuple:
    """
    Faits invariants de l'événement financier identifié par hash.

    Les partner_id sont volontairement exclus : ils représentent
    des associations administratives potentiellement multiples.
    """
    return (
        transaction.amount,
        transaction.received_at,
        transaction.fn_abi,
        transaction.type,
        transaction.is_sender_external,
        transaction.is_receiver_external,
    )


def normalize_transaction_rows(
    rows: Iterable[Mapping[str, Any]],
) -> tuple[TransactionContractRow, ...]:
    """
    Valide les lignes SQL et les doublons.

    - doublons strictement identiques : éliminés ;
    - même hash avec partner_id différents : autorisé ;
    - même hash avec faits financiers divergents : rejeté.

    Le grain financier reste un événement par hash.
    """
    event_signatures: dict[str, tuple] = {}
    seen_rows: set[TransactionContractRow] = set()
    normalized: list[TransactionContractRow] = []

    for row in rows:
        transaction = transaction_from_mapping(row)

        signature = transaction_event_signature(
            transaction
        )

        previous_signature = event_signatures.get(
            transaction.hash
        )

        if previous_signature is None:
            event_signatures[transaction.hash] = signature
        elif previous_signature != signature:
            raise TransactionContractError(
                "Plusieurs lignes portant le même hash "
                "contiennent des faits financiers divergents : "
                f"{transaction.hash!r}."
            )

        if transaction in seen_rows:
            continue

        seen_rows.add(transaction)
        normalized.append(transaction)

    return tuple(
        sorted(
            normalized,
            key=lambda transaction: (
                transaction.received_at,
                transaction.hash,
                (
                    transaction.sender_partner_id
                    if transaction.sender_partner_id is not None
                    else -1
                ),
                (
                    transaction.receiver_partner_id
                    if transaction.receiver_partner_id is not None
                    else -1
                ),
            ),
        )
    )
