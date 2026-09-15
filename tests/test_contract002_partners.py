import pytest

from server.contracts.partners_v1 import (
    PartnerContractError,
    normalize_partner_rows,
)
from server.providers.odoo_partners_postgres import (
    _industry_code,
    _localized,
)


def _row(**changes):
    row = {
        "partner_id": 42,
        "name": "Example",
        "is_company": True,
        "member_type": "Company",
        "industry_code": "Q",
        "industry_name": "Santé/Social",
        "siret": "12345678900011",
        "siren": "123456789",
        "legal_activity_code": "86.90F",
        "city": "Lyon",
        "zip": "69007",
        "latitude": 45.74,
        "longitude": 4.84,
        "active": True,
        "is_published": True,
    }
    row.update(changes)
    return row


def test_partner_contract_normalizes():
    partners = normalize_partner_rows([_row()])

    assert len(partners) == 1
    assert partners[0].partner_id == 42
    assert partners[0].industry_code == "Q"


def test_empty_strings_become_null():
    partner = normalize_partner_rows([
        _row(
            siret="",
            siren="  ",
            city="",
        )
    ])[0]

    assert partner.siret is None
    assert partner.siren is None
    assert partner.city is None


def test_exact_duplicate_is_collapsed():
    partners = normalize_partner_rows([
        _row(),
        _row(),
    ])

    assert len(partners) == 1


def test_divergent_duplicate_is_rejected():
    with pytest.raises(
        PartnerContractError,
        match="Contenu divergent",
    ):
        normalize_partner_rows([
            _row(),
            _row(name="Different"),
        ])


def test_unknown_column_is_rejected():
    with pytest.raises(
        PartnerContractError,
        match="Colonnes inconnues",
    ):
        normalize_partner_rows([
            {
                **_row(),
                "odoo_internal_id": 123,
            }
        ])


def test_partner_id_is_local_identity_not_business_type():
    partner = normalize_partner_rows([
        _row(
            is_company=False,
            member_type=None,
        )
    ])[0]

    assert partner.partner_id == 42
    assert partner.is_company is False
    assert partner.member_type is None


def test_industry_code_is_standard_code_not_odoo_id():
    assert _industry_code(
        "Q ACTIVITÉS RELATIVES À LA SANTÉ"
    ) == "Q"

    assert _industry_code(
        "Q - HUMAN HEALTH AND SOCIAL WORK ACTIVITIES"
    ) == "Q"

    assert _industry_code("Santé") is None


def test_localized_labels_prefer_french():
    assert _localized({
        "en_US": "Health/Social",
        "fr_FR": "Santé/Social",
    }) == "Santé/Social"


def test_coordinates_keep_zero_distinct_from_null():
    zero = normalize_partner_rows([
        _row(latitude=0.0, longitude=0.0)
    ])[0]

    missing = normalize_partner_rows([
        _row(
            partner_id=43,
            latitude=None,
            longitude=None,
        )
    ])[0]

    assert zero.latitude == 0.0
    assert missing.latitude is None
