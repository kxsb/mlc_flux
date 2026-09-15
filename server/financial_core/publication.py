from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Mapping

from sqlalchemy import Engine

from server.financial_core.writer import (
    FinancialCorePayload,
    publish_financial_core,
    validate_financial_core_payload,
)


class FinancialCorePublicationError(RuntimeError):
    """Erreur du lifecycle de publication Financial Core."""


@dataclass(frozen=True)
class FinancialCoreCandidate:
    """
    Payload validé mais pas encore publié.

    FINCORE002 garde volontairement ce candidat en mémoire. La source de
    vérité persistée reste uniquement une publication validée. Un staging
    durable pourra être ajouté avec les adapters si un besoin opérationnel
    réel apparaît.
    """

    payload: FinancialCorePayload
    validated_at: datetime
    validation: Mapping[str, Any]


def prepare_financial_core_candidate(
    payload: FinancialCorePayload,
) -> FinancialCoreCandidate:
    """
    Valide un payload et le transforme en candidat explicite.

    Aucune écriture SQL n'est effectuée.
    """
    validation = validate_financial_core_payload(payload)

    return FinancialCoreCandidate(
        payload=payload,
        validated_at=datetime.now(UTC).replace(microsecond=0),
        validation=validation,
    )


def publish_financial_core_candidate(
    engine: Engine,
    candidate: FinancialCoreCandidate,
) -> str:
    """
    Revalide puis publie atomiquement un candidat.

    La revalidation au dernier moment évite qu'une structure mutable
    contenue dans le payload soit modifiée entre prepare et publish.
    """
    if not isinstance(candidate, FinancialCoreCandidate):
        raise FinancialCorePublicationError(
            "candidate doit être un FinancialCoreCandidate."
        )

    validate_financial_core_payload(candidate.payload)

    publication_id = publish_financial_core(
        engine,
        candidate.payload,
    )

    if not isinstance(publication_id, str) or not publication_id:
        raise FinancialCorePublicationError(
            "Le writer n'a pas retourné de publication_id valide."
        )

    return publication_id


def validate_and_publish_financial_core(
    engine: Engine,
    payload: FinancialCorePayload,
) -> str:
    """
    Raccourci explicite pour le chemin synchrone standard.
    """
    candidate = prepare_financial_core_candidate(payload)
    return publish_financial_core_candidate(engine, candidate)
