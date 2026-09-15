from __future__ import annotations

import hashlib
import json

from server.financial_core.schema import CONTRACT_VERSION
from server.financial_core.writer import FinancialCorePayload
from server.providers.comchain_financial_core import (
    ComChainFinancialCoreBatch,
    ComChainFinancialCoreSpec,
)


class ComChainFinancialCoreBridgeError(ValueError):
    """Impossible de construire un payload Financial Core."""


def _non_empty(value: str, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ComChainFinancialCoreBridgeError(
            f"{label} doit être renseigné."
        )

    return value.strip()


def _content_hash(
    batch: ComChainFinancialCoreBatch,
) -> str:
    """
    Empreinte déterministe du contenu normalisé.

    Elle complète la provenance native mais ne la remplace pas.
    """
    canonical = {
        "accounts": list(batch.accounts),
        "events": list(batch.events),
        "effects": list(batch.account_effects),
    }

    raw = json.dumps(
        canonical,
        sort_keys=True,
        ensure_ascii=False,
        default=str,
        separators=(",", ":"),
    ).encode("utf-8")

    return hashlib.sha256(raw).hexdigest()


def _coverage(
    batch: ComChainFinancialCoreBatch,
):
    instants = [
        event.get("occurred_at")
        for event in batch.events
        if event.get("occurred_at") is not None
    ]

    if not instants:
        return None, None

    return min(instants), max(instants)


def build_comchain_financial_core_payload(
    batch: ComChainFinancialCoreBatch,
    *,
    spec: ComChainFinancialCoreSpec,
    dataset_id: str,
    publication_id: str,
    source_instance_id: str,
    adapter_version: str = "fincore003-b",
    source_cursor: str | None = None,
    source_snapshot_ref: str | None = None,
) -> FinancialCorePayload:
    """
    Transforme un batch ComChain normalisé en payload Financial Core.

    La séparation est volontaire :

    - dataset : identité stable de la source ;
    - publication : version/snapshot produit par une synchronisation ;
    - accounts/events/effects : faits financiers ;
    - Odoo n'intervient pas ici.
    """
    if not isinstance(spec, ComChainFinancialCoreSpec):
        raise ComChainFinancialCoreBridgeError(
            "spec doit être un ComChainFinancialCoreSpec."
        )

    dataset_id = _non_empty(
        dataset_id,
        "dataset_id",
    )
    publication_id = _non_empty(
        publication_id,
        "publication_id",
    )
    source_instance_id = _non_empty(
        source_instance_id,
        "source_instance_id",
    )
    adapter_version = _non_empty(
        adapter_version,
        "adapter_version",
    )

    coverage_from, coverage_to = _coverage(batch)

    dataset = {
        "dataset_id": dataset_id,
        "contract_version": CONTRACT_VERSION,
        "source_system": "comchain",
        "source_instance_id": source_instance_id,
    }

    publication = {
        "publication_id": publication_id,
        "coverage_from": coverage_from,
        "coverage_to": coverage_to,
        "source_cursor": source_cursor,
        "source_snapshot_ref": source_snapshot_ref,
        "adapter_name": "comchain-postgres",
        "adapter_version": adapter_version,
        "content_hash": _content_hash(batch),
    }

    return FinancialCorePayload(
        dataset=dataset,
        publication=publication,
        accounts=list(batch.accounts),
        events=list(batch.events),
        effects=list(batch.account_effects),

        # Les dimensions administratives et de stock seront ajoutées
        # dans des jalons distincts.
        actors=(),
        identity_links=(),
        balance_observations=(),
        monetary_observations=(),
        account_replacements=(),

        # FINCORE003 valide d'abord le transport des faits.
        capabilities={},
    )
