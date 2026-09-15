"""
Test live optionnel du contrat SQL normalisé.

Il ne lit QUE la relation transactions_* fournie à MLCFlux.
Il ne touche ni ext_pyc3l-*, ni res_partner_backend, ni res_alt_currency.
"""

import os

import pytest

from server.contracts.transactions_v1 import (
    CONTRACT_COLUMNS,
)
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


def test_normalized_transaction_contract_live():
    source = NormalizedTransactionsPostgresSource(
        dsn=DSN,
        relation=RELATION,
    )

    raw_rows = source.fetch_raw_rows()
    transactions = source.fetch_transactions()

    assert raw_rows
    assert transactions

    # Le lecteur SQL ne demande que les neuf colonnes contractuelles.
    assert set(raw_rows[0]) == set(CONTRACT_COLUMNS)

    # Après élimination des doublons strictement identiques,
    # le hash est la clé transactionnelle.
    hashes = [
        transaction.hash
        for transaction in transactions
    ]

    assert len(hashes) == len(set(hashes))

    # Les identités exposées sont administratives.
    # Aucune adresse wallet n'existe dans le contrat.
    assert "sender" not in CONTRACT_COLUMNS
    assert "receiver" not in CONTRACT_COLUMNS
    assert "caller" not in CONTRACT_COLUMNS
    assert "contract" not in CONTRACT_COLUMNS
