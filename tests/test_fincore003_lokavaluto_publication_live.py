"""
Premier parcours complet Lokavaluto -> Financial Core.

SOURCE :
PostgreSQL dev Lokavaluto, transaction READ ONLY.

CIBLE :
SQLite :memory:.

Aucune donnée n'est écrite dans PostgreSQL ou dans la base MLCFlux
opérationnelle.
"""

import os

import pytest
from sqlalchemy import create_engine

from server.financial_core.publication import (
    validate_and_publish_financial_core,
)
from server.financial_core.reader import (
    read_current_financial_core,
)
from server.financial_core.schema import metadata
from server.providers.comchain_financial_core import (
    ComChainFinancialCoreSpec,
    build_comchain_financial_core_batch,
)
from server.providers.comchain_financial_core_bridge import (
    build_comchain_financial_core_payload,
)
from server.providers.comchain_postgres import (
    ComChainPostgresSource,
)


DSN = os.getenv("LOKAVALUTO_PG_DSN")
SCHEMA = os.getenv("LOKAVALUTO_COMCHAIN_SCHEMA")


pytestmark = pytest.mark.skipif(
    not DSN or not SCHEMA,
    reason="Lokavaluto PostgreSQL live test non configuré",
)


def test_lokavaluto_can_publish_to_temporary_financial_core():
    source = ComChainPostgresSource(
        dsn=DSN,
        schema=SCHEMA,
    )

    rows = source.fetch_transactions()

    spec = ComChainFinancialCoreSpec(
        # Valeurs volontairement non métier :
        # ce test valide la structure, pas encore la nomenclature
        # monétaire définitive de Lemanopolis.
        native_currency_id=SCHEMA,
        unit_code="LIVE-TEST",
        unit_exponent=0,
        monetary_dimension="unqualified",
    )

    batch = build_comchain_financial_core_batch(
        rows,
        spec=spec,
    )

    max_block = max(
        row["block"]
        for row in rows
        if row["block"] is not None
    )

    payload = build_comchain_financial_core_payload(
        batch,
        spec=spec,
        dataset_id="lokavaluto-lemanopolis-live-test",
        publication_id="live-publication-1",
        source_instance_id="dev2.lokavaluto.fr",
        source_cursor=str(max_block),
        source_snapshot_ref=(
            f'{SCHEMA}.transactions'
        ),
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

    assert publication_id == "live-publication-1"

    snapshot = read_current_financial_core(
        target,
        "lokavaluto-lemanopolis-live-test",
    )

    assert snapshot.publication_id == "live-publication-1"

    # Le Financial Core doit conserver exactement le grain natif,
    # quelle que soit l'évolution future du nombre de transactions.
    assert len(snapshot.events) == len(batch.events)
    assert len(snapshot.account_effects) == len(
        batch.account_effects
    )
    assert len(snapshot.accounts) == len(batch.accounts)

    assert {
        event["event_id"]
        for event in snapshot.events
    } == {
        row["hash"]
        for row in rows
    }

    assert len({
        event["event_id"]
        for event in snapshot.events
    }) == len(snapshot.events)

    # Un transfert FINCORE003 conserve actuellement deux effets.
    assert len(snapshot.account_effects) == (
        2 * len(snapshot.events)
    )

    assert {
        effect["account_id"]
        for effect in snapshot.account_effects
    } == {
        account["account_id"]
        for account in snapshot.accounts
    }

    assert {
        event["execution_state"]
        for event in snapshot.events
    } == {"unknown"}
