from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping


CONTRACT_VERSION = "PARTNERS002"

CONTRACT_COLUMNS = (
    "partner_id",
    "name",
    "is_company",
    "member_type",
    "industry_code",
    "industry_name",
    "siret",
    "siren",
    "legal_activity_code",
    "city",
    "zip",
    "latitude",
    "longitude",
    "active",
    "is_published",
)


class PartnerContractError(ValueError):
    pass


@dataclass(frozen=True)
class PartnerContractRow:
    partner_id: int
    name: str | None
    is_company: bool | None
    member_type: str | None
    industry_code: str | None
    industry_name: str | None
    siret: str | None
    siren: str | None
    legal_activity_code: str | None
    city: str | None
    zip: str | None
    latitude: float | None
    longitude: float | None
    active: bool | None
    is_published: bool | None


def _text(value: Any, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise PartnerContractError(f"{field}: chaîne attendue")
    value = value.strip()
    return value or None


def _bool(value: Any, field: str) -> bool | None:
    if value is None:
        return None
    if type(value) is not bool:
        raise PartnerContractError(f"{field}: booléen attendu")
    return value


def _coordinate(
    value: Any,
    field: str,
    minimum: float,
    maximum: float,
) -> float | None:
    if value is None:
        return None

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PartnerContractError(f"{field}: nombre attendu")

    value = float(value)

    if not math.isfinite(value):
        raise PartnerContractError(f"{field}: valeur non finie")

    if not minimum <= value <= maximum:
        raise PartnerContractError(
            f"{field}: hors intervalle [{minimum}, {maximum}]"
        )

    return value


def normalize_partner_row(
    raw: Mapping[str, Any],
) -> PartnerContractRow:
    keys = set(raw)
    expected = set(CONTRACT_COLUMNS)

    missing = expected - keys
    unknown = keys - expected

    if missing:
        raise PartnerContractError(
            f"Colonnes manquantes: {sorted(missing)}"
        )

    if unknown:
        raise PartnerContractError(
            f"Colonnes inconnues: {sorted(unknown)}"
        )

    partner_id = raw["partner_id"]

    if (
        isinstance(partner_id, bool)
        or not isinstance(partner_id, int)
        or partner_id <= 0
    ):
        raise PartnerContractError(
            "partner_id: entier strictement positif attendu"
        )

    industry_code = _text(
        raw["industry_code"],
        "industry_code",
    )

    if (
        industry_code is not None
        and not re.fullmatch(r"[A-U]", industry_code)
    ):
        raise PartnerContractError(
            "industry_code: section A-U attendue"
        )

    return PartnerContractRow(
        partner_id=partner_id,
        name=_text(raw["name"], "name"),
        is_company=_bool(raw["is_company"], "is_company"),
        member_type=_text(raw["member_type"], "member_type"),
        industry_code=industry_code,
        industry_name=_text(
            raw["industry_name"],
            "industry_name",
        ),
        siret=_text(raw["siret"], "siret"),
        siren=_text(raw["siren"], "siren"),
        legal_activity_code=_text(
            raw["legal_activity_code"],
            "legal_activity_code",
        ),
        city=_text(raw["city"], "city"),
        zip=_text(raw["zip"], "zip"),
        latitude=_coordinate(
            raw["latitude"],
            "latitude",
            -90.0,
            90.0,
        ),
        longitude=_coordinate(
            raw["longitude"],
            "longitude",
            -180.0,
            180.0,
        ),
        active=_bool(raw["active"], "active"),
        is_published=_bool(
            raw["is_published"],
            "is_published",
        ),
    )


def normalize_partner_rows(
    rows: Iterable[Mapping[str, Any]],
) -> tuple[PartnerContractRow, ...]:
    by_id: dict[int, PartnerContractRow] = {}

    for raw in rows:
        row = normalize_partner_row(raw)

        previous = by_id.get(row.partner_id)

        if previous is None:
            by_id[row.partner_id] = row
            continue

        if previous != row:
            raise PartnerContractError(
                "Contenu divergent pour partner_id="
                f"{row.partner_id}"
            )

    return tuple(
        by_id[partner_id]
        for partner_id in sorted(by_id)
    )
