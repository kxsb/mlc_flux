from __future__ import annotations

import re
from typing import Any

import psycopg
from psycopg.rows import dict_row

from server.contracts.partners_v1 import (
    PartnerContractRow,
    normalize_partner_rows,
)


_SQL = """
SELECT
    p.id AS partner_id,
    p.name AS name,
    p.is_company AS is_company,
    mt.name AS member_type,
    i.name AS industry_name_json,
    i.full_name AS industry_full_name_json,
    p.siret AS siret,
    p.siren AS siren,
    p.legal_activity_code AS legal_activity_code,
    p.city AS city,
    p.zip AS zip,
    p.partner_latitude::double precision AS latitude,
    p.partner_longitude::double precision AS longitude,
    p.active AS active,
    p.is_published AS is_published
FROM public.res_partner AS p
LEFT JOIN public.member_type AS mt
    ON mt.id = p.member_type_id
LEFT JOIN public.res_partner_industry AS i
    ON i.id = p.industry_id
ORDER BY p.id
"""


def _localized(value: Any) -> str | None:
    if value is None:
        return None

    if isinstance(value, str):
        value = value.strip()
        return value or None

    if not isinstance(value, dict):
        return None

    for key in ("fr_FR", "en_US"):
        candidate = value.get(key)

        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()

    for candidate in value.values():
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()

    return None


def _industry_code(full_name: str | None) -> str | None:
    if not full_name:
        return None

    match = re.match(r"^\s*([A-U])(?:\s|-)", full_name)

    if match is None:
        return None

    return match.group(1)


class OdooPartnersPostgresSource:
    """
    Adaptateur source Odoo -> PARTNERS002.

    Les IDs de nomenclature Odoo ne traversent pas le contrat.
    """

    def __init__(self, *, dsn: str):
        self.dsn = dsn

    def fetch_raw_rows(self) -> list[dict[str, Any]]:
        with psycopg.connect(
            self.dsn,
            row_factory=dict_row,
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION READ ONLY")
                cursor.execute(_SQL)
                source_rows = cursor.fetchall()

        rows: list[dict[str, Any]] = []

        for source in source_rows:
            industry_name = _localized(
                source["industry_name_json"]
            )
            industry_full_name = _localized(
                source["industry_full_name_json"]
            )

            rows.append({
                "partner_id": source["partner_id"],
                "name": source["name"],
                "is_company": source["is_company"],
                "member_type": source["member_type"],
                "industry_code": _industry_code(
                    industry_full_name
                ),
                "industry_name": industry_name,
                "siret": source["siret"],
                "siren": source["siren"],
                "legal_activity_code": (
                    source["legal_activity_code"]
                ),
                "city": source["city"],
                "zip": source["zip"],
                "latitude": source["latitude"],
                "longitude": source["longitude"],
                "active": source["active"],
                "is_published": source["is_published"],
            })

        return rows

    def fetch_partners(
        self,
    ) -> tuple[PartnerContractRow, ...]:
        return normalize_partner_rows(
            self.fetch_raw_rows()
        )
