"""
Test d'intégration optionnel contre Lokavaluto.

Il est ignoré par défaut. Pour l'activer :
- LOKAVALUTO_PG_DSN
- LOKAVALUTO_COMCHAIN_SCHEMA

Aucune écriture n'est effectuée sur PostgreSQL.
"""

import os

import pytest

from server.providers.comchain_financial_core import (
    ComChainFinancialCoreSpec,
    build_comchain_financial_core_batch,
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


def test_lokavaluto_native_comchain_characterization():
    source = ComChainPostgresSource(
        dsn=DSN,
        schema=SCHEMA,
    )

    rows = source.fetch_transactions()

    assert rows

    hashes = [
        row["hash"]
        for row in rows
    ]

    # La source native doit rester à grain transaction :
    # une ligne = un hash ComChain.
    assert None not in hashes
    assert len(set(hashes)) == len(rows)

    batch = build_comchain_financial_core_batch(
        rows,
        spec=ComChainFinancialCoreSpec(
            native_currency_id=SCHEMA,
            unit_code="LIVE-TEST",
            unit_exponent=0,
            monetary_dimension="unqualified",
        ),
    )

    assert len(batch.events) == len(rows)

    # FINCORE003 supporte actuellement les transferts natifs :
    # un débit + un crédit par événement.
    assert len(batch.account_effects) == 2 * len(batch.events)

    assert {
        event["event_id"]
        for event in batch.events
    } == set(hashes)

    # Tous les comptes présents dans les effets doivent avoir été
    # matérialisés exactement une fois dans le registre des comptes.
    effect_accounts = {
        effect["account_id"]
        for effect in batch.account_effects
    }

    assert {
        account["account_id"]
        for account in batch.accounts
    } == effect_accounts

    source_by_hash = {
        row["hash"]: row
        for row in rows
    }

    # Vérifie que les faits natifs ne sont pas réinterprétés.
    for event in batch.events:
        native = source_by_hash[event["event_id"]]

        assert event["native_event_type"] == native["type"]
        assert event["native_method"] == native["fn"]
        assert event["native_event_subtype"] == (
            native["fn_abi"] or native["fn"]
        )
        assert event["native_status"] == native["status"]

        # Aucune règle de finalité ComChain n'est encore définie.
        assert event["execution_state"] == "unknown"
