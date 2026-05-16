from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import UTC, datetime
from urllib.parse import quote

import requests
from flask import current_app

from server.database import get_connection
from server.services.cyclos_actor_user_links import load_actor_user_links
from server.services.cyclos_client import create_session_token
from server.services.odoo_client import OdooJsonRpcClient


MEMBER_REF_RE = re.compile(r"^U\d+$")

ODOO_INDIVIDUAL_FIELDS = [
    "ref",
    "zip",
    "city",
    "partner_latitude",
    "partner_longitude",
    "membership_state",
    "is_former_member",
]

ODOO_CHUNK_SIZE = 400


def _utc_now_iso():
    return datetime.now(UTC).isoformat(timespec="seconds")


def _nullable_float(value):
    if value in (False, None, ""):
        return None
    return float(value)


def _safe_text(value):
    if value in (False, None, ""):
        return None
    return str(value).strip() or None


def _fetch_cyclos_user(user_id, session_token):
    base_url = current_app.config["CYCLOS_BASE_URL"].rstrip("/")
    url = f"{base_url}/users/{quote(str(user_id), safe='')}"

    response = requests.get(
        url,
        headers={
            "Session-Token": session_token,
            "Accept": "application/json",
        },
        timeout=60,
    )

    if response.status_code != 200:
        return {
            "status": "error",
            "http_status": response.status_code,
            "payload": None,
        }

    return {
        "status": "ok",
        "http_status": response.status_code,
        "payload": response.json(),
    }


def _extract_numadherent(user_payload):
    """
    Extrait customValues[].stringValue pour le champ
    field.internalName == 'numadherent'.
    """
    for custom_value in user_payload.get("customValues") or []:
        field = custom_value.get("field") or {}
        internal_name = field.get("internalName")

        if internal_name != "numadherent":
            continue

        value = _safe_text(custom_value.get("stringValue"))
        return value

    return None


def _chunked(items, size):
    for index in range(0, len(items), size):
        yield items[index:index + size]


def _fetch_odoo_individuals(member_refs, *, progress_callback=None):
    refs = sorted(set(member_refs))
    if not refs:
        return []

    client = OdooJsonRpcClient()
    partners = []

    chunks = list(_chunked(refs, ODOO_CHUNK_SIZE))

    for index, chunk in enumerate(chunks, start=1):
        if progress_callback:
            progress_callback({
                "stage": "odoo_chunk_start",
                "chunk_index": index,
                "chunk_count": len(chunks),
                "ref_count": len(chunk),
            })

        result = client.execute_kw(
            model="res.partner",
            method="search_read",
            args=[[
                ["ref", "in", chunk],
                ["is_company", "=", False],
            ]],
            kwargs={
                "fields": ODOO_INDIVIDUAL_FIELDS,
                "limit": 10000,
                "order": "ref asc",
            },
        )

        partners.extend(result)

        if progress_callback:
            progress_callback({
                "stage": "odoo_chunk_done",
                "chunk_index": index,
                "chunk_count": len(chunks),
                "partner_count": len(result),
            })

    return partners


def build_odoo_individual_enrichment_snapshot(*, progress_callback=None, limit=None):
    """
    Construit un snapshot territorial des particuliers raccordés :

    actor_user_links.json
        -> user.id Cyclos
        -> numadherent Uxxxx via /users/{id}
        -> res.partner.ref Uxxxx dans Odoo
        -> données territoriales analytiques.
    """
    fetched_at = _utc_now_iso()
    links_payload = load_actor_user_links()
    links = links_payload.get("links") or {}

    ordered_links = sorted(
        links.items(),
        key=lambda pair: str((pair[1] or {}).get("pseudonym") or ""),
    )

    if limit is not None:
        ordered_links = ordered_links[:limit]

    session_token = create_session_token()

    candidates = []
    member_ref_to_pseudonyms = defaultdict(set)
    stats = Counter()

    total_links = len(ordered_links)

    for index, (_actor_id, record) in enumerate(ordered_links, start=1):
        pseudonym = _safe_text(record.get("pseudonym"))
        user_id = _safe_text(record.get("user_id"))

        if progress_callback and (
            index == 1
            or index == total_links
            or index % 50 == 0
        ):
            progress_callback({
                "stage": "cyclos_user_progress",
                "done": index,
                "total": total_links,
            })

        candidate = {
            "pseudonym": pseudonym,
            "member_ref": None,
            "status": None,
            "partner": None,
        }

        if not pseudonym or not user_id:
            candidate["status"] = "invalid_actor_user_link"
            candidates.append(candidate)
            stats["invalid_actor_user_link"] += 1
            continue

        fetch_result = _fetch_cyclos_user(user_id, session_token)

        if fetch_result["status"] != "ok":
            candidate["status"] = "cyclos_user_error"
            candidates.append(candidate)
            stats["cyclos_user_error"] += 1
            continue

        stats["cyclos_user_profile_ok"] += 1

        member_ref = _extract_numadherent(fetch_result["payload"])

        if not member_ref:
            candidate["status"] = "no_member_ref"
            candidates.append(candidate)
            stats["no_member_ref"] += 1
            continue

        if not MEMBER_REF_RE.match(member_ref):
            candidate["status"] = "invalid_member_ref"
            candidates.append(candidate)
            stats["invalid_member_ref"] += 1
            continue

        candidate["member_ref"] = member_ref
        candidate["status"] = "awaiting_odoo"

        candidates.append(candidate)
        member_ref_to_pseudonyms[member_ref].add(pseudonym)
        stats["valid_member_ref"] += 1

    duplicated_refs = {
        member_ref: sorted(pseudonyms)
        for member_ref, pseudonyms in member_ref_to_pseudonyms.items()
        if len(pseudonyms) > 1
    }

    if duplicated_refs:
        raise RuntimeError(
            "Conflit de raccordement individuel : "
            "au moins une ref Uxxxx est associée à plusieurs pseudonymes."
        )

    partners = _fetch_odoo_individuals(
        list(member_ref_to_pseudonyms.keys()),
        progress_callback=progress_callback,
    )

    partners_by_ref = defaultdict(list)
    for partner in partners:
        ref = _safe_text(partner.get("ref"))
        if ref:
            partners_by_ref[ref].append(partner)

    rows = []

    for candidate in candidates:
        pseudonym = candidate["pseudonym"]
        member_ref = candidate.get("member_ref")
        status = candidate["status"]

        row = {
            "pseudonym": pseudonym,
            "odoo_match_status": status,
            "zip": None,
            "city": None,
            "latitude": None,
            "longitude": None,
            "membership_state": None,
            "is_former_member": 0,
            "has_zip": 0,
            "has_city": 0,
            "has_coordinates": 0,
            "fetched_at": fetched_at,
            "source": "odoo_jsonrpc_via_cyclos_numadherent",
        }

        if status != "awaiting_odoo":
            rows.append(row)
            continue

        matches = partners_by_ref.get(member_ref) or []

        if not matches:
            row["odoo_match_status"] = "no_odoo_partner"
            rows.append(row)
            stats["no_odoo_partner"] += 1
            continue

        if len(matches) > 1:
            row["odoo_match_status"] = "ambiguous_odoo_ref"
            rows.append(row)
            stats["ambiguous_odoo_ref"] += 1
            continue

        partner = matches[0]

        zip_code = _safe_text(partner.get("zip"))
        city = _safe_text(partner.get("city"))
        latitude = _nullable_float(partner.get("partner_latitude"))
        longitude = _nullable_float(partner.get("partner_longitude"))

        row.update({
            "odoo_match_status": "matched",
            "zip": zip_code,
            "city": city,
            "latitude": latitude,
            "longitude": longitude,
            "membership_state": _safe_text(partner.get("membership_state")),
            "is_former_member": 1 if partner.get("is_former_member") else 0,
            "has_zip": 1 if zip_code else 0,
            "has_city": 1 if city else 0,
            "has_coordinates": 1 if latitude is not None and longitude is not None else 0,
        })

        rows.append(row)
        stats["matched"] += 1

    return {
        "items": rows,
        "fetched_at": fetched_at,
        "source_link_count": total_links,
        "member_ref_count": len(member_ref_to_pseudonyms),
        "odoo_partner_rows_returned": len(partners),
        "stats": dict(stats),
    }


def replace_odoo_individual_enrichment(snapshot):
    """
    Remplace atomiquement le snapshot SQLite des enrichissements particuliers.
    """
    items = snapshot.get("items") or []
    fetched_at = snapshot.get("fetched_at")

    if not fetched_at:
        raise ValueError("Snapshot individuel invalide : fetched_at manquant.")

    source_link_count = int(snapshot.get("source_link_count") or 0)
    stats = snapshot.get("stats") or {}

    if source_link_count > 0 and int(stats.get("cyclos_user_profile_ok") or 0) == 0:
        raise RuntimeError(
            "Synchronisation individuelle interrompue : "
            "aucun profil Cyclos n'a pu être lu."
        )

    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("BEGIN")

        cur.execute("DELETE FROM odoo_individual_enrichment")

        for item in items:
            cur.execute("""
                INSERT INTO odoo_individual_enrichment (
                    pseudonym,
                    odoo_match_status,
                    zip,
                    city,
                    latitude,
                    longitude,
                    membership_state,
                    is_former_member,
                    has_zip,
                    has_city,
                    has_coordinates,
                    fetched_at,
                    source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                item.get("pseudonym"),
                item.get("odoo_match_status"),
                item.get("zip"),
                item.get("city"),
                item.get("latitude"),
                item.get("longitude"),
                item.get("membership_state"),
                1 if item.get("is_former_member") else 0,
                1 if item.get("has_zip") else 0,
                1 if item.get("has_city") else 0,
                1 if item.get("has_coordinates") else 0,
                item.get("fetched_at"),
                item.get("source"),
            ))

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    matched_count = sum(
        1 for item in items
        if item.get("odoo_match_status") == "matched"
    )

    return {
        "stored_rows": len(items),
        "matched_count": matched_count,
        "fetched_at": fetched_at,
    }
