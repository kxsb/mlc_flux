"""
CONTRACT001 live end-to-end.

Source :
relation SQL normalisée Lokavaluto, READ ONLY.

Cible :
Financial Core dans SQLite :memory:.

Aucune lecture des tables internes ComChain / Odoo.
"""

import os

import pytest
from sqlalchemy import create_engine

from server.contracts.transactions_financial_core import (
    TransactionFinancialCoreSpec,
    build_transaction_contract_payload,
)
from server.financial_core.publication import (
    validate_and_publish_financial_core,
)
from server.financial_core.reader import (
    read_current_financial_core,
)
from server.financial_core.schema import metadata
from server.providers.normalized_transactions_postgres import (
    NormalizedTransactionsPostgresSource,
)


DSN = os.getenv("LOKAVALUTO_PG_DSN")
RELATION = os.getenv(
    "LOKAVALUTO_NORMALIZED_TRANSACTIONS_RELATION"
)


pytestmark = pytest.mark.skipif(
    not DSN or not RELATION,
    reason="CONTRACT001 live non configuré",
)


def test_contract001_live_publishes_to_financial_core():
    source = NormalizedTransactionsPostgresSource(
        dsn=DSN,
        relation=RELATION,
    )

    transactions = source.fetch_transactions()

    assert transactions

    payload = build_transaction_contract_payload(
        transactions,
        spec=TransactionFinancialCoreSpec(
            # Le modèle Lokavaluto observé travaille en centièmes.
            # On garde ici une unité générique de test.
            unit_code="LIVE-TEST",
            unit_exponent=2,
            monetary_dimension="local_currency",
        ),
        dataset_id="lokavaluto-contract001-live",
        publication_id="contract001-live-p1",
        source_instance_id="dev2.lokavaluto.fr",
        source_snapshot_ref=RELATION,
    )

    target = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
    )

    metadata.create_all(target)

    publication_id = validate_and_publish_financial_core(
        target,
        payload,
    )

    assert publication_id == "contract001-live-p1"

    snapshot = read_current_financial_core(
        target,
        "lokavaluto-contract001-live",
    )

    # Un hash contractuel = un événement.
    assert len(snapshot.events) == len(transactions)

    assert {
        event["event_id"]
        for event in snapshot.events
    } == {
        tx.hash
        for tx in transactions
    }

    # Deux effets analytiques par transaction.
    assert len(snapshot.account_effects) == (
        2 * len(transactions)
    )

    # Les partner_id disponibles deviennent des acteurs,
    # sans fabriquer d'identité pour les NULL.
    expected_partner_ids = {
        str(partner_id)
        for tx in transactions
        for partner_id in (
            tx.sender_partner_id,
            tx.receiver_partner_id,
        )
        if partner_id is not None
    }

    assert {
        actor["native_actor_id"]
        for actor in snapshot.actors
    } == expected_partner_ids

    # type / fn_abi sont conservés tels quels.
    by_hash = {
        tx.hash: tx
        for tx in transactions
    }

    for event in snapshot.events:
        tx = by_hash[event["event_id"]]

        assert event["native_event_type"] == tx.type
        assert event["native_event_subtype"] == tx.fn_abi

    # L'ingestion ne doit recréer aucun doublon de hash.
    assert len({
        event["event_id"]
        for event in snapshot.events
    }) == len(snapshot.events)
