from __future__ import annotations

import re
from datetime import datetime, UTC
from typing import Any

import requests

from server.mlc_profiles import get_mlc_profile
from server.mlc_secrets import get_cyclos_config
from server.services.cyclos_client import create_session_token, get_transactions
from server.services.professional_ref_mapping import get_or_create_professional_ref


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _actor_type_internal(actor: dict[str, Any] | None) -> str | None:
    if not isinstance(actor, dict):
        return None

    actor_type = actor.get("type")
    if not isinstance(actor_type, dict):
        return None

    return actor_type.get("internalName")


def _custom_values_by_internal_name(user_profile: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result = {}

    for item in user_profile.get("customValues") or []:
        if not isinstance(item, dict):
            continue

        field = item.get("field")
        if not isinstance(field, dict):
            continue

        internal_name = field.get("internalName")
        if internal_name:
            result[str(internal_name)] = item

    return result


def _custom_string(custom_values: dict[str, dict[str, Any]], internal_name: str) -> str | None:
    item = custom_values.get(internal_name) or {}

    value = item.get("stringValue")
    if value in (None, False):
        return None

    value = str(value).strip()
    return value or None


def _enumerated_values(custom_values: dict[str, dict[str, Any]], internal_name: str) -> list[dict[str, Any]]:
    item = custom_values.get(internal_name) or {}
    values = item.get("enumeratedValues") or []

    if not isinstance(values, list):
        return []

    return [
        value
        for value in values
        if isinstance(value, dict)
    ]


def _first_enum_value(custom_values: dict[str, dict[str, Any]], internal_name: str) -> str | None:
    values = _enumerated_values(custom_values, internal_name)

    if not values:
        return None

    value = values[0].get("value")
    if value in (None, False):
        return None

    value = str(value).strip()
    return value or None


def _first_enum_internal_name(custom_values: dict[str, dict[str, Any]], internal_name: str) -> str | None:
    values = _enumerated_values(custom_values, internal_name)

    if not values:
        return None

    value = values[0].get("internalName")
    if value in (None, False):
        return None

    value = str(value).strip()
    return value or None


def _enum_value_list(custom_values: dict[str, dict[str, Any]], internal_name: str) -> list[str]:
    result = []

    for item in _enumerated_values(custom_values, internal_name):
        value = item.get("value")
        if value in (None, False):
            continue

        value = str(value).strip()
        if value:
            result.append(value)

    return result


def _enum_internal_name_list(custom_values: dict[str, dict[str, Any]], internal_name: str) -> list[str]:
    result = []

    for item in _enumerated_values(custom_values, internal_name):
        value = item.get("internalName")
        if value in (None, False):
            continue

        value = str(value).strip()
        if value:
            result.append(value)

    return result


def _digits_only(value: str | None) -> str | None:
    if not value:
        return None

    digits = re.sub(r"\D+", "", str(value))
    return digits or None


def _normalize_siret(value: str | None) -> str | None:
    digits = _digits_only(value)
    if digits and len(digits) == 14:
        return digits
    return None


def _normalize_siren_from_siret(value: str | None) -> str | None:
    siret = _normalize_siret(value)
    if siret:
        return siret[:9]
    return None


def _default_address_from_user(user_profile: dict[str, Any]) -> dict[str, Any] | None:
    addresses = user_profile.get("addresses") or []

    if not isinstance(addresses, list):
        return None

    for address in addresses:
        if isinstance(address, dict) and address.get("defaultAddress"):
            return address

    for address in addresses:
        if isinstance(address, dict):
            return address

    return None


def _address_value(primary_address: dict[str, Any] | None, user_profile: dict[str, Any], key: str):
    if isinstance(primary_address, dict):
        value = primary_address.get(key)
        if value not in (None, False, ""):
            return value

    fallback = _default_address_from_user(user_profile) or {}
    value = fallback.get(key)

    if value in (None, False, ""):
        return None

    return value


def _address_location_value(primary_address: dict[str, Any] | None, user_profile: dict[str, Any], key: str):
    if isinstance(primary_address, dict):
        location = primary_address.get("location") or {}
        if isinstance(location, dict):
            value = location.get(key)
            if value not in (None, False, ""):
                return value

    fallback = _default_address_from_user(user_profile) or {}
    location = fallback.get("location") or {}

    if not isinstance(location, dict):
        return None

    value = location.get(key)
    if value in (None, False, ""):
        return None

    return value


def _fetch_json(base_url: str, session_token: str, path: str) -> dict[str, Any] | list[Any] | None:
    response = requests.get(
        f"{base_url.rstrip('/')}/{path.lstrip('/')}",
        headers={
            "Session-Token": session_token,
            "Accept": "application/json",
        },
        timeout=30,
    )

    if response.status_code == 204:
        return None

    response.raise_for_status()
    return response.json()


def _fetch_user_profile(base_url: str, session_token: str, user_id: str) -> dict[str, Any]:
    data = _fetch_json(base_url, session_token, f"users/{user_id}")

    if not isinstance(data, dict):
        raise ValueError(f"Profil utilisateur Cyclos inattendu pour {user_id}")

    return data


def _fetch_primary_address(base_url: str, session_token: str, user_id: str) -> dict[str, Any] | None:
    data = _fetch_json(base_url, session_token, f"{user_id}/addresses/primary")

    if data is None:
        return None

    if not isinstance(data, dict):
        raise ValueError(f"Adresse primaire Cyclos inattendue pour {user_id}")

    return data


def collect_professional_actors_from_transactions(
    transactions: list[dict[str, Any]],
    *,
    mlc_id: str,
) -> list[dict[str, Any]]:
    profile = get_mlc_profile(mlc_id).public_dict()
    enrichment = profile.get("professional_enrichment") or {}
    target_types = set(enrichment.get("professional_actor_type_internal_names") or [])

    actors_by_key: dict[str, dict[str, Any]] = {}

    for transaction in transactions:
        for side in ("from", "to"):
            actor = transaction.get(side)
            if not isinstance(actor, dict):
                continue

            if target_types and _actor_type_internal(actor) not in target_types:
                continue

            user = actor.get("user")
            if not isinstance(user, dict):
                continue

            user_id = user.get("id")
            actor_id = actor.get("id")
            actor_number = actor.get("number")

            key = str(user_id or actor_id or actor_number or "").strip()
            if not key:
                continue

            professional_ref = get_or_create_professional_ref(
                mlc_id=mlc_id,
                actor=actor,
            )

            actors_by_key[key] = {
                "professional_ref": professional_ref,
                "cyclos_user_id": user_id,
                "cyclos_actor_id": actor_id,
                "external_professional_ref": actor_number,
                "actor_type_internal": _actor_type_internal(actor),
                "actor_kind": actor.get("kind"),
                "source_side": side,
            }

    return list(actors_by_key.values())


def normalize_cyclos_professional_profile(
    *,
    actor_ref: dict[str, Any],
    user_profile: dict[str, Any],
    primary_address: dict[str, Any] | None,
) -> dict[str, Any]:
    custom_values = _custom_values_by_internal_name(user_profile)

    siret_raw = _custom_string(custom_values, "sirene")
    group = user_profile.get("group") if isinstance(user_profile.get("group"), dict) else {}
    group_set = user_profile.get("groupSet") if isinstance(user_profile.get("groupSet"), dict) else {}

    display_name = (
        _custom_string(custom_values, "nomEnseigne")
        or user_profile.get("display")
        or None
    )

    return {
        "professional_ref": actor_ref.get("professional_ref"),
        "external_professional_ref": actor_ref.get("external_professional_ref"),
        "cyclos_user_id": actor_ref.get("cyclos_user_id"),
        "cyclos_actor_id": actor_ref.get("cyclos_actor_id"),
        "actor_type_internal": actor_ref.get("actor_type_internal"),
        "display_name": display_name,
        "legal_name": _custom_string(custom_values, "raisonSociale"),
        "industry_name": _first_enum_value(custom_values, "categoriePro"),
        "industry_internal_name": _first_enum_internal_name(custom_values, "categoriePro"),
        "secondary_industries": _enum_value_list(custom_values, "catPro"),
        "secondary_industry_internal_names": _enum_internal_name_list(custom_values, "catPro"),
        "payment_methods_accepted": _enum_value_list(custom_values, "typePaiementAccepte"),
        "detailed_activity": _custom_string(custom_values, "descriptionDetail"),
        "short_description": _custom_string(custom_values, "about"),
        "keywords": _custom_string(custom_values, "keywords"),
        "website": _custom_string(custom_values, "siteinternet"),
        "siret": _normalize_siret(siret_raw),
        "siren": _normalize_siren_from_siret(siret_raw),
        "street": _address_value(primary_address, user_profile, "addressLine1"),
        "zip": _address_value(primary_address, user_profile, "zip"),
        "city": _address_value(primary_address, user_profile, "city"),
        "latitude": _address_location_value(primary_address, user_profile, "latitude"),
        "longitude": _address_location_value(primary_address, user_profile, "longitude"),
        "cyclos_group": group.get("internalName"),
        "cyclos_group_name": group.get("name"),
        "cyclos_group_set": group_set.get("name"),
        "fetched_at": _utc_now(),
    }


def fetch_professional_profile_enrichment_sample(
    *,
    mlc_id: str = "graine",
    days: int = 30,
    limit: int | None = 20,
) -> list[dict[str, Any]]:
    config = get_cyclos_config(mlc_id)
    session_token = create_session_token()

    transactions = get_transactions(days=days)
    actor_refs = collect_professional_actors_from_transactions(
        transactions,
        mlc_id=mlc_id,
    )

    if limit is not None:
        actor_refs = actor_refs[:limit]

    enriched = []

    for actor_ref in actor_refs:
        user_id = actor_ref.get("cyclos_user_id")
        if not user_id:
            continue

        user_profile = _fetch_user_profile(config.base_url, session_token, str(user_id))
        primary_address = _fetch_primary_address(config.base_url, session_token, str(user_id))

        enriched.append(
            normalize_cyclos_professional_profile(
                actor_ref=actor_ref,
                user_profile=user_profile,
                primary_address=primary_address,
            )
        )

    return enriched



def _json_dumps(value: Any) -> str:
    import json

    return json.dumps(value if value is not None else None, ensure_ascii=False, sort_keys=True)


def _professional_ref_from_row(row: dict[str, Any]) -> str:
    for key in ("professional_ref", "external_professional_ref", "cyclos_user_id", "cyclos_actor_id"):
        value = row.get(key)
        if value not in (None, "", [], {}):
            return str(value)

    raise ValueError("Impossible de déterminer professional_ref pour l’enrichissement professionnel.")


def save_professional_enrichment_rows(
    rows: list[dict[str, Any]],
    *,
    source_provider: str = "cyclos_user_profile",
) -> int:
    from server.database import get_connection, init_professional_enrichment_db

    if not rows:
        return 0

    init_professional_enrichment_db()

    conn = get_connection()
    cur = conn.cursor()

    written = 0
    now = _utc_now()

    for row in rows:
        professional_ref = _professional_ref_from_row(row)

        cur.execute(
            """
            INSERT INTO professional_enrichment (
                professional_ref,
                source_provider,
                external_professional_ref,
                cyclos_user_id,
                cyclos_actor_id,
                actor_type_internal,
                display_name,
                legal_name,
                industry_name,
                industry_internal_name,
                secondary_industries_json,
                secondary_industry_internal_names_json,
                payment_methods_accepted_json,
                detailed_activity,
                short_description,
                keywords,
                website,
                siret,
                siren,
                street,
                zip,
                city,
                latitude,
                longitude,
                cyclos_group,
                cyclos_group_name,
                cyclos_group_set,
                raw_safe_json,
                fetched_at,
                updated_at
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            ON CONFLICT(professional_ref) DO UPDATE SET
                source_provider = excluded.source_provider,
                external_professional_ref = excluded.external_professional_ref,
                cyclos_user_id = excluded.cyclos_user_id,
                cyclos_actor_id = excluded.cyclos_actor_id,
                actor_type_internal = excluded.actor_type_internal,
                display_name = excluded.display_name,
                legal_name = excluded.legal_name,
                industry_name = excluded.industry_name,
                industry_internal_name = excluded.industry_internal_name,
                secondary_industries_json = excluded.secondary_industries_json,
                secondary_industry_internal_names_json = excluded.secondary_industry_internal_names_json,
                payment_methods_accepted_json = excluded.payment_methods_accepted_json,
                detailed_activity = excluded.detailed_activity,
                short_description = excluded.short_description,
                keywords = excluded.keywords,
                website = excluded.website,
                siret = excluded.siret,
                siren = excluded.siren,
                street = excluded.street,
                zip = excluded.zip,
                city = excluded.city,
                latitude = excluded.latitude,
                longitude = excluded.longitude,
                cyclos_group = excluded.cyclos_group,
                cyclos_group_name = excluded.cyclos_group_name,
                cyclos_group_set = excluded.cyclos_group_set,
                raw_safe_json = excluded.raw_safe_json,
                fetched_at = excluded.fetched_at,
                updated_at = excluded.updated_at
            """,
            (
                professional_ref,
                source_provider,
                row.get("external_professional_ref"),
                row.get("cyclos_user_id"),
                row.get("cyclos_actor_id"),
                row.get("actor_type_internal"),
                row.get("display_name"),
                row.get("legal_name"),
                row.get("industry_name"),
                row.get("industry_internal_name"),
                _json_dumps(row.get("secondary_industries")),
                _json_dumps(row.get("secondary_industry_internal_names")),
                _json_dumps(row.get("payment_methods_accepted")),
                row.get("detailed_activity"),
                row.get("short_description"),
                row.get("keywords"),
                row.get("website"),
                row.get("siret"),
                row.get("siren"),
                row.get("street"),
                row.get("zip"),
                row.get("city"),
                row.get("latitude"),
                row.get("longitude"),
                row.get("cyclos_group"),
                row.get("cyclos_group_name"),
                row.get("cyclos_group_set"),
                _json_dumps(row),
                row.get("fetched_at") or now,
                now,
            ),
        )
        written += 1

    conn.commit()
    conn.close()

    return written


def sync_professional_profile_enrichment_sample(
    *,
    mlc_id: str = "graine",
    days: int = 30,
    limit: int | None = 20,
) -> dict[str, Any]:
    rows = fetch_professional_profile_enrichment_sample(
        mlc_id=mlc_id,
        days=days,
        limit=limit,
    )
    written = save_professional_enrichment_rows(
        rows,
        source_provider="cyclos_user_profile",
    )

    return {
        "mlc_id": mlc_id,
        "fetched": len(rows),
        "written": written,
        "synced_at": _utc_now(),
    }
