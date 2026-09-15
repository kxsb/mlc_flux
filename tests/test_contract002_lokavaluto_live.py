import os

import pytest

from server.providers.odoo_partners_postgres import (
    OdooPartnersPostgresSource,
)


DSN = os.getenv("LOKAVALUTO_PG_DSN")


pytestmark = pytest.mark.skipif(
    not DSN,
    reason="Lokavaluto PostgreSQL live non configuré",
)


def test_contract002_live():
    source = OdooPartnersPostgresSource(
        dsn=DSN,
    )

    partners = source.fetch_partners()

    assert partners

    ids = [
        partner.partner_id
        for partner in partners
    ]

    assert len(ids) == len(set(ids))
    assert all(partner_id > 0 for partner_id in ids)

    # PARTNERS002 transporte le sens des nomenclatures,
    # jamais leur ID Odoo.
    assert all(
        partner.industry_code is None
        or "A" <= partner.industry_code <= "U"
        for partner in partners
    )
