import re
from collections import defaultdict
from datetime import datetime, UTC
from math import atan2, cos, radians, sin, sqrt

from server.database import get_connection
from server.services.cyclos_client import (
    CyclosAddressError,
    create_session_token,
    get_primary_address,
)
from server.services.odoo_client import OdooJsonRpcClient


PROFESSIONAL_REF_RE = re.compile(r"^(P\d+)\b")


PARTNER_FIELDS = [
    "id",
    "name",
    "ref",
    "industry_id",
    "secondary_industry_ids",
    "detailed_activity",
    "website_description",
    "keywords",
    "naf",
    "street",
    "zip",
    "city",
    "partner_latitude",
    "partner_longitude",
    "date_localization",
    "membership_state",
    "is_former_member",
]


def extract_mlcflux_professional_refs():
    """
    Extrait les références professionnelles Pxxxx déjà observées
    dans les libellés from_label / to_label des transactions MLCFlux.
    """
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT from_label AS label FROM transactions
        UNION
        SELECT to_label AS label FROM transactions
    """)

    refs = set()

    for row in cur.fetchall():
        label = row["label"]
        if not label:
            continue

        match = PROFESSIONAL_REF_RE.match(label.strip())
        if match:
            refs.add(match.group(1))

    conn.close()
    return sorted(refs)


def fetch_odoo_professional_enrichment(professional_refs):
    """
    Récupère depuis Odoo les profils entreprises principaux
    dont le champ ref correspond à une référence Pxxxx MLCFlux.
    """
    refs = sorted(set(professional_refs))
    if not refs:
        return {
            "requested_refs": [],
            "matched": [],
            "unmatched_refs": [],
            "fetched_at": datetime.now(UTC).isoformat(timespec="seconds"),
        }

    client = OdooJsonRpcClient()

    partners = client.execute_kw(
        model="res.partner",
        method="search_read",
        args=[[
            ["is_company", "=", True],
            ["is_main_profile", "=", True],
            ["ref", "in", refs],
        ]],
        kwargs={
            "fields": PARTNER_FIELDS,
            "limit": 10000,
            "order": "ref asc",
        },
    )

    industry_ids = set()

    for partner in partners:
        industry = partner.get("industry_id")
        if industry:
            industry_ids.add(industry[0])

        for secondary_id in partner.get("secondary_industry_ids") or []:
            industry_ids.add(secondary_id)

    industry_names = _fetch_industry_names(client, sorted(industry_ids))

    session_token = create_session_token()

    matched = []
    for partner in partners:
        normalized = _normalize_partner(partner, industry_names)
        geo_qualified = _enrich_with_cyclos_geolocation(
            normalized,
            session_token=session_token,
        )
        matched.append(geo_qualified)

    matched_refs = {item["professional_ref"] for item in matched}
    unmatched_refs = sorted(set(refs) - matched_refs)

    return {
        "requested_refs": refs,
        "matched": matched,
        "unmatched_refs": unmatched_refs,
        "fetched_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }


def _fetch_industry_names(client, industry_ids):
    """
    Résout les noms des secteurs res.partner.industry.
    """
    if not industry_ids:
        return {}

    industries = client.execute_kw(
        model="res.partner.industry",
        method="read",
        args=[industry_ids],
        kwargs={"fields": ["id", "name"]},
    )

    return {
        industry["id"]: industry["name"]
        for industry in industries
    }


def _normalize_partner(partner, industry_names):
    """
    Produit un objet d'enrichissement normalisé, prêt à être stocké plus tard.
    """
    primary_industry = partner.get("industry_id") or False

    if primary_industry:
        industry_id = primary_industry[0]
        industry_name = primary_industry[1]
    else:
        industry_id = None
        industry_name = None

    secondary_industries = []

    for secondary_id in partner.get("secondary_industry_ids") or []:
        secondary_industries.append({
            "industry_id": secondary_id,
            "industry_name": industry_names.get(secondary_id, ""),
        })

    return {
        "professional_ref": partner.get("ref"),
        "odoo_partner_id": partner.get("id"),
        "odoo_name": partner.get("name"),
        "industry_id": industry_id,
        "industry_name": industry_name,
        "secondary_industries": secondary_industries,
        "detailed_activity": partner.get("detailed_activity") or None,
        "website_description_html": partner.get("website_description") or None,
        "keywords": partner.get("keywords") or None,
        "naf": partner.get("naf") or None,
        "street": partner.get("street") or None,
        "zip": partner.get("zip") or None,
        "city": partner.get("city") or None,
        "latitude": _nullable_float(partner.get("partner_latitude")),
        "longitude": _nullable_float(partner.get("partner_longitude")),
        "date_localization": partner.get("date_localization") or None,
        "membership_state": partner.get("membership_state") or None,
        "is_former_member": bool(partner.get("is_former_member")),
    }


def _nullable_float(value):
    if value in (False, None, ""):
        return None
    return float(value)


GEO_MATCH_THRESHOLD_METERS = 1000.0


def _geo_distance_meters(lat_a, lon_a, lat_b, lon_b):
    """
    Distance haversine entre deux coordonnées, en mètres.
    """
    earth_radius_meters = 6_371_000.0

    lat1 = radians(lat_a)
    lon1 = radians(lon_a)
    lat2 = radians(lat_b)
    lon2 = radians(lon_b)

    delta_lat = lat2 - lat1
    delta_lon = lon2 - lon1

    haversine = (
        sin(delta_lat / 2) ** 2
        + cos(lat1) * cos(lat2) * sin(delta_lon / 2) ** 2
    )

    angular_distance = 2 * atan2(sqrt(haversine), sqrt(1 - haversine))
    return earth_radius_meters * angular_distance


def _has_coordinates(latitude, longitude):
    return latitude is not None and longitude is not None


def _enrich_with_cyclos_geolocation(item, session_token):
    """
    Ajoute au professionnel normalisé :
    - l'adresse primaire Cyclos, si disponible ;
    - la distance entre les coordonnées Odoo et Cyclos ;
    - un statut de concordance géographique.
    """
    enriched = dict(item)

    enriched.update({
        "cyclos_address_id": None,
        "cyclos_address_line1": None,
        "cyclos_zip": None,
        "cyclos_city": None,
        "cyclos_latitude": None,
        "cyclos_longitude": None,
        "geo_distance_meters": None,
        "geo_match_status": None,
    })

    try:
        cyclos_address = get_primary_address(
            item["professional_ref"],
            session_token=session_token,
        )
    except CyclosAddressError:
        enriched["geo_match_status"] = "cyclos_error"
        return enriched

    if cyclos_address is None:
        enriched["geo_match_status"] = "no_cyclos_address"
        return enriched

    enriched.update(cyclos_address)

    odoo_latitude = _nullable_float(item.get("latitude"))
    odoo_longitude = _nullable_float(item.get("longitude"))
    cyclos_latitude = _nullable_float(cyclos_address.get("cyclos_latitude"))
    cyclos_longitude = _nullable_float(cyclos_address.get("cyclos_longitude"))

    enriched["cyclos_latitude"] = cyclos_latitude
    enriched["cyclos_longitude"] = cyclos_longitude

    if not _has_coordinates(cyclos_latitude, cyclos_longitude):
        enriched["geo_match_status"] = "no_cyclos_coordinates"
        return enriched

    if not _has_coordinates(odoo_latitude, odoo_longitude):
        enriched["geo_match_status"] = "no_odoo_coordinates"
        return enriched

    distance_meters = _geo_distance_meters(
        odoo_latitude,
        odoo_longitude,
        cyclos_latitude,
        cyclos_longitude,
    )

    enriched["geo_distance_meters"] = distance_meters
    enriched["geo_match_status"] = (
        "confirmed"
        if distance_meters <= GEO_MATCH_THRESHOLD_METERS
        else "mismatch"
    )

    return enriched


def replace_odoo_professional_enrichment(snapshot):
    """
    Remplace atomiquement le snapshot SQLite des enrichissements pros Odoo.

    Le snapshot doit être celui produit par fetch_odoo_professional_enrichment().
    Seuls les professionnels effectivement matchés sont stockés.
    """
    matched = snapshot.get("matched") or []
    fetched_at = snapshot.get("fetched_at")

    if not fetched_at:
        raise ValueError("Snapshot d'enrichissement invalide : fetched_at manquant.")

    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("BEGIN")

        cur.execute("DELETE FROM odoo_professional_secondary_industries")
        cur.execute("DELETE FROM odoo_professional_enrichment")

        professional_count = 0
        secondary_industry_count = 0

        for item in matched:
            cur.execute("""
                INSERT INTO odoo_professional_enrichment (
                    professional_ref,
                    odoo_partner_id,
                    odoo_name,
                    industry_id,
                    industry_name,
                    detailed_activity,
                    website_description_html,
                    keywords,
                    naf,
                    street,
                    zip,
                    city,
                    latitude,
                    longitude,
                    date_localization,
                    membership_state,
                    is_former_member,
                    cyclos_address_id,
                    cyclos_address_line1,
                    cyclos_zip,
                    cyclos_city,
                    cyclos_latitude,
                    cyclos_longitude,
                    geo_distance_meters,
                    geo_match_status,
                    fetched_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                item["professional_ref"],
                item["odoo_partner_id"],
                item["odoo_name"],
                item.get("industry_id"),
                item.get("industry_name"),
                item.get("detailed_activity"),
                item.get("website_description_html"),
                item.get("keywords"),
                item.get("naf"),
                item.get("street"),
                item.get("zip"),
                item.get("city"),
                item.get("latitude"),
                item.get("longitude"),
                item.get("date_localization"),
                item.get("membership_state"),
                1 if item.get("is_former_member") else 0,
                item.get("cyclos_address_id"),
                item.get("cyclos_address_line1"),
                item.get("cyclos_zip"),
                item.get("cyclos_city"),
                item.get("cyclos_latitude"),
                item.get("cyclos_longitude"),
                item.get("geo_distance_meters"),
                item.get("geo_match_status"),
                fetched_at,
            ))
            professional_count += 1

            for secondary in item.get("secondary_industries") or []:
                cur.execute("""
                    INSERT INTO odoo_professional_secondary_industries (
                        professional_ref,
                        industry_id,
                        industry_name
                    ) VALUES (?, ?, ?)
                """, (
                    item["professional_ref"],
                    secondary["industry_id"],
                    secondary["industry_name"],
                ))
                secondary_industry_count += 1

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    return {
        "professional_count": professional_count,
        "secondary_industry_count": secondary_industry_count,
        "fetched_at": fetched_at,
    }
