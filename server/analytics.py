from datetime import datetime
from math import log1p

from server.database import get_connection


def _is_date_only(value):
    """
    Retourne True pour les dates calendaires au format YYYY-MM-DD.

    Les dates stockées en base sont des timestamps ISO complets.
    Pour un filtre utilisateur du type end=2026-05-14,
    il faut comparer sur la partie jour afin d'inclure toute la journée.
    """
    if not isinstance(value, str):
        return False

    value = value.strip()
    if len(value) != 10:
        return False

    try:
        datetime.strptime(value, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def fetch_transactions(start=None, end=None, year=None):
    conn = get_connection()
    cur = conn.cursor()

    query = """
        SELECT
            date,
            group_label,
            from_label,
            to_label,
            amount,
            type_label,
            transaction_number
        FROM transactions
        WHERE 1=1
    """
    params = []

    if start:
        if _is_date_only(start):
            query += " AND substr(date, 1, 10) >= ?"
        else:
            query += " AND date >= ?"
        params.append(start)

    if end:
        if _is_date_only(end):
            query += " AND substr(date, 1, 10) <= ?"
        else:
            query += " AND date <= ?"
        params.append(end)

    if year is not None:
        query += " AND substr(date, 1, 4) = ?"
        params.append(str(year))

    query += " ORDER BY date ASC"

    cur.execute(query, params)
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows


def get_available_years():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT DISTINCT substr(date, 1, 4) AS year
        FROM transactions
        WHERE date IS NOT NULL AND date != ''
        ORDER BY year ASC
    """)

    years = [int(row["year"]) for row in cur.fetchall() if row["year"]]
    conn.close()
    return years


def get_available_period_bounds():
    """
    Retourne la première et la dernière date disponibles dans la base,
    au format YYYY-MM-DD.

    Ces bornes servent à initialiser le filtre global de période côté interface.
    """
    conn = get_connection()
    cur = conn.cursor()

    row = cur.execute("""
        SELECT
            MIN(substr(date, 1, 10)) AS min_date,
            MAX(substr(date, 1, 10)) AS max_date
        FROM transactions
        WHERE date IS NOT NULL AND date != ''
    """).fetchone()

    conn.close()

    if not row:
        return {
            "min_date": None,
            "max_date": None,
        }

    return {
        "min_date": row["min_date"],
        "max_date": row["max_date"],
    }


def compute_global_stats(start=None, end=None, year=None):
    rows = fetch_transactions(start=start, end=end, year=year)

    if not rows:
        return {
            "periode": "-",
            "nb_utilisateurs": 0,
            "moyenne_transactions_PP": 0.0,
            "moyenne_paiement_UP": 0.0,
            "moyenne_transactions_UU": 0.0,
            "transactions": []
        }

    dates = [row["date"] for row in rows if row.get("date")]
    if dates:
        start_date = datetime.fromisoformat(min(dates).replace("Z", "+00:00")).strftime("%d/%m/%Y")
        end_date = datetime.fromisoformat(max(dates).replace("Z", "+00:00")).strftime("%d/%m/%Y")
        periode = f"{start_date} - {end_date}"
    else:
        periode = "-"

    acteurs = set()
    for row in rows:
        from_label = str(row.get("from_label", "")).strip()
        to_label = str(row.get("to_label", "")).strip()
        if from_label:
            acteurs.add(from_label)
        if to_label:
            acteurs.add(to_label)

    pp = [
        row for row in rows
        if str(row.get("from_label", "")).startswith("P")
        and str(row.get("to_label", "")).startswith("P")
    ]

    up = [
        row for row in rows
        if str(row.get("from_label", "")).startswith("U")
        and str(row.get("to_label", "")).startswith("P")
    ]

    uu = [
        row for row in rows
        if str(row.get("from_label", "")).startswith("U")
        and str(row.get("to_label", "")).startswith("U")
    ]

    def avg_amount(items):
        if not items:
            return 0.0
        return float(sum(float(row.get("amount", 0) or 0) for row in items) / len(items))

    transactions = [
        {
            "Date": row["date"][:10],
            "Réalisé par": row.get("from_label", ""),
            "Vers": row.get("to_label", ""),
            "Montant": float(row.get("amount", 0) or 0),
        }
        for row in rows
    ]

    return {
        "periode": periode,
        "nb_utilisateurs": len(acteurs),
        "moyenne_transactions_PP": avg_amount(pp),
        "moyenne_paiement_UP": avg_amount(up),
        "moyenne_transactions_UU": avg_amount(uu),
        "transactions": transactions,
    }

def compute_network_data(start=None, end=None, year=None):
    rows = fetch_transactions(start=start, end=end, year=year)

    # même logique que la prod : seulement P -> P
    pp_rows = [
        row for row in rows
        if str(row.get("from_label", "")).startswith("P")
        and str(row.get("to_label", "")).startswith("P")
    ]

    if not pp_rows:
        return {"nodes": [], "edges": []}

    edge_weights = {}
    nodes_set = set()

    for row in pp_rows:
        source = str(row.get("from_label", "")).strip()
        target = str(row.get("to_label", "")).strip()
        amount = float(row.get("amount", 0) or 0)

        if not source or not target:
            continue

        nodes_set.add(source)
        nodes_set.add(target)

        key = (source, target)
        edge_weights[key] = edge_weights.get(key, 0.0) + amount

    nodes = [{"data": {"id": node, "label": node}} for node in sorted(nodes_set)]
    edges = [
        {
            "data": {
                "source": source,
                "target": target,
                "weight": float(weight),
            }
        }
        for (source, target), weight in edge_weights.items()
    ]

    return {"nodes": nodes, "edges": edges}


def compute_professionals_ranking(start=None, end=None, year=None):
    rows = fetch_transactions(start=start, end=end, year=year)

    if not rows:
        return []

    b2b_recu = {}
    b2b_emis = {}
    b2c = {}
    remuneration = {}
    pros = set()

    for row in rows:
        from_label = str(row.get("from_label", "")).strip()
        to_label = str(row.get("to_label", "")).strip()
        amount = float(row.get("amount", 0) or 0)

        from_is_pro = from_label.startswith("P")
        to_is_pro = to_label.startswith("P")
        from_is_user = from_label.startswith("U")
        to_is_user = to_label.startswith("U")

        if from_is_pro:
            pros.add(from_label)
        if to_is_pro:
            pros.add(to_label)

        if from_is_pro and to_is_pro:
            b2b_recu[to_label] = b2b_recu.get(to_label, 0.0) + amount
            b2b_emis[from_label] = b2b_emis.get(from_label, 0.0) + amount

        if from_is_user and to_is_pro:
            b2c[to_label] = b2c.get(to_label, 0.0) + amount

        if from_is_pro and to_is_user:
            remuneration[from_label] = remuneration.get(from_label, 0.0) + amount

    ranking = []
    for pro in pros:
        total_recu = b2b_recu.get(pro, 0.0) + b2c.get(pro, 0.0)

        ranking.append({
            "Professionnel": pro,
            "B2B Reçu": round(b2b_recu.get(pro, 0.0), 2),
            "B2B Emis": round(b2b_emis.get(pro, 0.0), 2),
            "B2C": round(b2c.get(pro, 0.0), 2),
            "Paiements Reçu B+C": round(total_recu, 2),
            "Rémunération": round(remuneration.get(pro, 0.0), 2),
            "Total Reçu": round(total_recu, 2),
        })

    ranking.sort(key=lambda x: x["Total Reçu"], reverse=True)
    return ranking


def _get_odoo_professional_enrichment(professional_ref):
    """
    Retourne les métadonnées Odoo stockées en SQLite pour un professionnel Pxxxx.

    Si aucune correspondance automatique n'existe dans le snapshot Odoo,
    retourne None.
    """
    conn = get_connection()
    cur = conn.cursor()

    row = cur.execute("""
        SELECT
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
            fetched_at
        FROM odoo_professional_enrichment
        WHERE professional_ref = ?
    """, (professional_ref,)).fetchone()

    if row is None:
        conn.close()
        return None

    secondary_rows = cur.execute("""
        SELECT
            industry_id,
            industry_name
        FROM odoo_professional_secondary_industries
        WHERE professional_ref = ?
        ORDER BY industry_name ASC, industry_id ASC
    """, (professional_ref,)).fetchall()

    conn.close()

    enrichment = dict(row)
    enrichment["is_former_member"] = bool(enrichment.get("is_former_member"))
    enrichment["secondary_industries"] = [
        {
            "industry_id": secondary["industry_id"],
            "industry_name": secondary["industry_name"],
        }
        for secondary in secondary_rows
    ]

    return enrichment


def get_professional_detail(num_professionnel, start=None, end=None, year=None):
    rows = fetch_transactions(start=start, end=end, year=year)

    related = []
    for row in rows:
        from_label = str(row.get("from_label", "")).strip()
        to_label = str(row.get("to_label", "")).strip()

        if num_professionnel in from_label or num_professionnel in to_label:
            related.append(row)

    if not related:
        return None

    received = [
        row for row in related
        if num_professionnel in str(row.get("to_label", ""))
        and "conversion" not in str(row.get("from_label", "")).lower()
    ]

    particuliers = {
        str(row.get("from_label", "")).strip()
        for row in related
        if num_professionnel in str(row.get("to_label", ""))
        and str(row.get("from_label", "")).startswith("U")
    }

    professionnels = {
        str(row.get("from_label", "")).strip()
        for row in related
        if num_professionnel in str(row.get("to_label", ""))
        and str(row.get("from_label", "")).startswith("P")
    }

    emis_vers_pro = sum(
        float(row.get("amount", 0) or 0)
        for row in related
        if num_professionnel in str(row.get("from_label", ""))
        and str(row.get("to_label", "")).startswith("P")
    )

    emis_vers_particuliers = sum(
        float(row.get("amount", 0) or 0)
        for row in related
        if num_professionnel in str(row.get("from_label", ""))
        and str(row.get("to_label", "")).startswith("U")
    )

    montant_reconverti = sum(
        float(row.get("amount", 0) or 0)
        for row in related
        if num_professionnel in str(row.get("from_label", ""))
        and "conversion" in str(row.get("to_label", "")).lower()
    )

    montant_converti = sum(
        float(row.get("amount", 0) or 0)
        for row in related
        if num_professionnel in str(row.get("to_label", ""))
        and "conversion" in str(row.get("from_label", "")).lower()
    )

    dates = [row["date"] for row in related if row.get("date")]
    stats = {
        "nb_particuliers": len(particuliers),
        "nb_professionnels": len(professionnels),
        "premiere_date": min(dates)[:10] if dates else "-",
        "derniere_date": max(dates)[:10] if dates else "-",
        "nb_transactions_recues": len(received),
        "somme_transactions_recues": float(sum(float(r.get("amount", 0) or 0) for r in received)),
        "montant_emis_vers_pro": float(emis_vers_pro),
        "montant_emis_vers_particuliers": float(emis_vers_particuliers),
        "montant_reconverti": float(montant_reconverti),
        "montant_converti": float(montant_converti),
        "total_montant_emis_sans_reconversion": float(emis_vers_pro + emis_vers_particuliers),
    }

    transactions = [
        {
            "Date": row["date"][:10],
            "Réalisé par": row.get("from_label", ""),
            "Vers": row.get("to_label", ""),
            "Montant": float(row.get("amount", 0) or 0),
        }
        for row in related
    ]

    fullname = next(
        (
            label for label in (
                str(related[0].get("from_label", "")),
                str(related[0].get("to_label", "")),
            )
            if num_professionnel in label
        ),
        num_professionnel
    )

    return {
        "professionnel": num_professionnel,
        "fullname": fullname,
        "stats": stats,
        "transactions": transactions,
        "odoo_enrichment": _get_odoo_professional_enrichment(num_professionnel),
    }




def _extract_professional_ref(label):
    """
    Extrait une référence Pxxxx depuis un libellé de transaction.
    Exemple : 'P0080 - 3 Ptits Pois' -> 'P0080'
    """
    value = str(label or "").strip()
    if not value.startswith("P"):
        return None

    prefix = value.split(" - ", 1)[0].strip()
    if prefix.startswith("P") and prefix[1:].isdigit():
        return prefix

    return None


def _normalize_activity_component(values):
    """
    Normalise une série positive en [0, 1] après compression logarithmique.
    """
    transformed = [log1p(max(float(value or 0), 0.0)) for value in values]
    maximum = max(transformed, default=0.0)

    if maximum <= 0:
        return [0.0 for _ in transformed]

    return [value / maximum for value in transformed]


def _compute_map_activity_scores(professionals, rows):
    """
    Calcule les métriques et l'indice d'activité des professionnels cartographiables.

    Définitions cohérentes avec les fiches pros existantes :
    - reçu : hors conversions reçues ;
    - émis : vers P ou U uniquement, donc hors reconversions.
    """
    by_ref = {
        professional["professional_ref"]: professional
        for professional in professionals
    }

    for professional in professionals:
        professional["received_volume"] = 0.0
        professional["emitted_volume"] = 0.0
        professional["received_count"] = 0
        professional["emitted_count"] = 0
        professional["activity_score"] = 0.0

    for row in rows:
        from_label = str(row.get("from_label", "")).strip()
        to_label = str(row.get("to_label", "")).strip()
        amount = float(row.get("amount", 0) or 0)

        from_ref = _extract_professional_ref(from_label)
        to_ref = _extract_professional_ref(to_label)

        # Reçu par un professionnel cartographiable, hors conversions reçues.
        if (
            to_ref in by_ref
            and "conversion" not in from_label.lower()
        ):
            professional = by_ref[to_ref]
            professional["received_volume"] += amount
            professional["received_count"] += 1

        # Émis par un professionnel cartographiable vers P ou U.
        # Cette définition reprend la logique déjà utilisée dans les fiches pros.
        if (
            from_ref in by_ref
            and (
                to_label.startswith("P")
                or to_label.startswith("U")
            )
        ):
            professional = by_ref[from_ref]
            professional["emitted_volume"] += amount
            professional["emitted_count"] += 1

    received_volume_norm = _normalize_activity_component(
        [professional["received_volume"] for professional in professionals]
    )
    emitted_volume_norm = _normalize_activity_component(
        [professional["emitted_volume"] for professional in professionals]
    )
    received_count_norm = _normalize_activity_component(
        [professional["received_count"] for professional in professionals]
    )
    emitted_count_norm = _normalize_activity_component(
        [professional["emitted_count"] for professional in professionals]
    )

    for index, professional in enumerate(professionals):
        activity_score = (
            0.35 * received_volume_norm[index]
            + 0.25 * emitted_volume_norm[index]
            + 0.20 * received_count_norm[index]
            + 0.20 * emitted_count_norm[index]
        )

        professional["received_volume"] = float(professional["received_volume"])
        professional["emitted_volume"] = float(professional["emitted_volume"])
        professional["received_count"] = int(professional["received_count"])
        professional["emitted_count"] = int(professional["emitted_count"])
        professional["activity_score"] = float(activity_score)

    return professionals


def _compute_map_lorenz_relief_scores(professionals):
    """
    Calcule un score de relief cartographique inspiré de la courbe de Lorenz.

    Base de calcul :
    - total_flow_volume = received_volume + emitted_volume

    Interprétation :
    - 1.0 pour le professionnel situé au sommet de la distribution ;
    - score décroissant selon la part cumulée du volume déjà portée
      par les professionnels plus actifs.

    Ce score est destiné à la hauteur visuelle des colonnes 3D, pas à
    remplacer l'indice d'activité composite.
    """
    for professional in professionals:
        received_volume = float(professional.get("received_volume") or 0.0)
        emitted_volume = float(professional.get("emitted_volume") or 0.0)

        professional["total_flow_volume"] = received_volume + emitted_volume
        professional["total_flow_share"] = 0.0
        professional["lorenz_relief_score"] = 0.0
        professional["flow_rank"] = None

    total_flow_all_professionals = sum(
        professional["total_flow_volume"]
        for professional in professionals
    )

    if total_flow_all_professionals <= 0:
        return professionals

    ranked = sorted(
        professionals,
        key=lambda professional: (
            -professional["total_flow_volume"],
            professional["professional_ref"],
        ),
    )

    cumulative_share_before = 0.0

    for rank, professional in enumerate(ranked, start=1):
        total_flow_volume = professional["total_flow_volume"]
        total_flow_share = total_flow_volume / total_flow_all_professionals

        professional["total_flow_share"] = float(total_flow_share)
        professional["lorenz_relief_score"] = float(
            max(0.0, 1.0 - cumulative_share_before)
        )
        professional["flow_rank"] = rank

        cumulative_share_before += total_flow_share

    return professionals


def get_professionals_map_data(start=None, end=None, year=None):
    """
    Retourne les professionnels cartographiables, leur activité
    sur la période demandée et un résumé de la qualité géographique.

    La carte V1 affiche uniquement les professionnels dont la géolocalisation
    a été confirmée par concordance Odoo ↔ Cyclos à moins de 1 km.
    """
    conn = get_connection()
    cur = conn.cursor()

    status_rows = cur.execute("""
        SELECT
            COALESCE(geo_match_status, 'unknown') AS geo_match_status,
            COUNT(*) AS count
        FROM odoo_professional_enrichment
        GROUP BY COALESCE(geo_match_status, 'unknown')
    """).fetchall()

    status_counts = {
        row["geo_match_status"]: row["count"]
        for row in status_rows
    }

    professional_rows = cur.execute("""
        SELECT
            professional_ref,
            odoo_partner_id,
            odoo_name,
            industry_id,
            industry_name,
            detailed_activity,
            city,
            zip,
            cyclos_city,
            cyclos_zip,
            cyclos_latitude AS latitude,
            cyclos_longitude AS longitude,
            geo_distance_meters
        FROM odoo_professional_enrichment
        WHERE geo_match_status = 'confirmed'
          AND cyclos_latitude IS NOT NULL
          AND cyclos_longitude IS NOT NULL
        ORDER BY professional_ref ASC
    """).fetchall()

    conn.close()

    professionals = [dict(row) for row in professional_rows]
    transaction_rows = fetch_transactions(start=start, end=end, year=year)
    professionals = _compute_map_activity_scores(professionals, transaction_rows)
    professionals = _compute_map_lorenz_relief_scores(professionals)

    summary = {
        "total_enriched": sum(status_counts.values()),
        "cartographiable_count": len(professionals),
        "confirmed": status_counts.get("confirmed", 0),
        "mismatch": status_counts.get("mismatch", 0),
        "no_odoo_coordinates": status_counts.get("no_odoo_coordinates", 0),
        "no_cyclos_coordinates": status_counts.get("no_cyclos_coordinates", 0),
        "no_cyclos_address": status_counts.get("no_cyclos_address", 0),
        "cyclos_error": status_counts.get("cyclos_error", 0),
        "unknown": status_counts.get("unknown", 0),
        "relief_metric": "lorenz_total_flow_volume",
        "period": {
            "start": start,
            "end": end,
            "year": year,
        },
    }

    return {
        "summary": summary,
        "professionals": professionals,
    }



def compute_zip_territorial_activity(start=None, end=None, year=None):
    """
    Agrège l'activité monétaire numérique par code postal.

    Périmètre :
    - professionnels MLCFlux enrichis depuis Odoo ;
    - activité calculée sur la période demandée ;
    - rattachement territorial par code postal Odoo,
      avec repli sur le code postal Cyclos si nécessaire.

    Mesures :
    - gonettes reçues ;
    - gonettes émises hors reconversion ;
    - pros actifs ;
    - taux de réutilisation territorial.
    """
    conn = get_connection()
    cur = conn.cursor()

    professional_rows = cur.execute("""
        SELECT
            professional_ref,
            odoo_partner_id,
            odoo_name,
            industry_id,
            industry_name,
            detailed_activity,
            COALESCE(
                NULLIF(TRIM(zip), ''),
                NULLIF(TRIM(cyclos_zip), '')
            ) AS zip_code,
            COALESCE(
                NULLIF(TRIM(city), ''),
                NULLIF(TRIM(cyclos_city), '')
            ) AS city_name
        FROM odoo_professional_enrichment
        ORDER BY professional_ref ASC
    """).fetchall()

    conn.close()

    professionals = [dict(row) for row in professional_rows]
    transaction_rows = fetch_transactions(start=start, end=end, year=year)
    professionals = _compute_map_activity_scores(professionals, transaction_rows)

    territories = {}

    territorialized_professional_count = 0
    professionals_without_zip = 0

    territorialized_active_professional_count = 0
    unassigned_active_professional_count = 0

    territorialized_received_volume = 0.0
    territorialized_emitted_volume = 0.0

    unassigned_received_volume = 0.0
    unassigned_emitted_volume = 0.0

    all_received_volume = 0.0
    all_emitted_volume = 0.0

    for professional in professionals:
        received_volume = float(professional.get("received_volume") or 0.0)
        emitted_volume = float(professional.get("emitted_volume") or 0.0)
        received_count = int(professional.get("received_count") or 0)
        emitted_count = int(professional.get("emitted_count") or 0)

        is_active = received_count > 0 or emitted_count > 0

        all_received_volume += received_volume
        all_emitted_volume += emitted_volume

        zip_code = str(professional.get("zip_code") or "").strip()
        city_name = str(professional.get("city_name") or "").strip()

        if not zip_code:
            professionals_without_zip += 1
            unassigned_received_volume += received_volume
            unassigned_emitted_volume += emitted_volume

            if is_active:
                unassigned_active_professional_count += 1

            continue

        territorialized_professional_count += 1
        territorialized_received_volume += received_volume
        territorialized_emitted_volume += emitted_volume

        if is_active:
            territorialized_active_professional_count += 1

        territory = territories.setdefault(zip_code, {
            "zip_code": zip_code,
            "cities": set(),
            "professional_count": 0,
            "active_professional_count": 0,
            "received_volume": 0.0,
            "emitted_volume": 0.0,
            "total_flow_volume": 0.0,
            "received_count": 0,
            "emitted_count": 0,
            "reuse_rate": None,
            "received_volume_share": 0.0,
        })

        if city_name:
            territory["cities"].add(city_name)

        territory["professional_count"] += 1

        if is_active:
            territory["active_professional_count"] += 1

        territory["received_volume"] += received_volume
        territory["emitted_volume"] += emitted_volume
        territory["total_flow_volume"] += received_volume + emitted_volume
        territory["received_count"] += received_count
        territory["emitted_count"] += emitted_count

    territory_rows = []

    for territory in territories.values():
        received_volume = territory["received_volume"]
        emitted_volume = territory["emitted_volume"]

        cities = sorted(territory["cities"], key=lambda value: value.lower())

        territory["cities"] = cities
        territory["city_label"] = ", ".join(cities) if cities else ""
        territory["reuse_rate"] = (
            emitted_volume / received_volume
            if received_volume > 0
            else None
        )
        territory["received_volume_share"] = (
            received_volume / territorialized_received_volume
            if territorialized_received_volume > 0
            else 0.0
        )

        territory_rows.append(territory)

    territory_rows.sort(
        key=lambda territory: (
            -territory["received_volume"],
            territory["zip_code"],
        )
    )

    territorialized_total_flow_volume = (
        territorialized_received_volume + territorialized_emitted_volume
    )

    summary = {
        "territory_count": len(territory_rows),
        "professional_count": len(professionals),
        "territorialized_professional_count": territorialized_professional_count,
        "professionals_without_zip": professionals_without_zip,
        "territorialized_active_professional_count": territorialized_active_professional_count,
        "unassigned_active_professional_count": unassigned_active_professional_count,
        "territorialized_received_volume": float(territorialized_received_volume),
        "territorialized_emitted_volume": float(territorialized_emitted_volume),
        "territorialized_total_flow_volume": float(territorialized_total_flow_volume),
        "unassigned_received_volume": float(unassigned_received_volume),
        "unassigned_emitted_volume": float(unassigned_emitted_volume),
        "received_volume_coverage": (
            territorialized_received_volume / all_received_volume
            if all_received_volume > 0
            else None
        ),
        "emitted_volume_coverage": (
            territorialized_emitted_volume / all_emitted_volume
            if all_emitted_volume > 0
            else None
        ),
        "overall_reuse_rate": (
            territorialized_emitted_volume / territorialized_received_volume
            if territorialized_received_volume > 0
            else None
        ),
        "period": {
            "start": start,
            "end": end,
            "year": year,
        },
    }

    return {
        "summary": summary,
        "territories": territory_rows,
    }



def compute_stats_charts(start=None, end=None, year=None):
    rows = fetch_transactions(start=start, end=end, year=year)

    if not rows:
        return {
            "daily": {"labels": [], "values": []},
            "weekly": {"labels": [], "values": []},
            "hourly": {"labels": [], "values": []},
            "weekday": {"labels": [], "values": []},
            "cumulative": {"labels": [], "values": []},
        }

    parsed = []
    for row in rows:
        raw_date = str(row.get("date", "")).strip()
        amount = float(row.get("amount", 0) or 0)

        try:
            dt = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
        except Exception:
            continue

        parsed.append({
            "dt": dt,
            "amount": amount
        })

    if not parsed:
        return {
            "daily": {"labels": [], "values": []},
            "weekly": {"labels": [], "values": []},
            "hourly": {"labels": [], "values": []},
            "weekday": {"labels": [], "values": []},
            "cumulative": {"labels": [], "values": []},
        }

    # 1) daily count
    daily_counts = {}
    for row in parsed:
        day = row["dt"].date().isoformat()
        daily_counts[day] = daily_counts.get(day, 0) + 1

    daily_labels = sorted(daily_counts.keys())
    daily_values = [daily_counts[day] for day in daily_labels]

    # 2) weekly average amount
    weekly_buckets = {}
    for row in parsed:
        iso_year, iso_week, _ = row["dt"].isocalendar()
        key = f"{iso_year}-W{iso_week:02d}"
        weekly_buckets.setdefault(key, {"sum": 0.0, "count": 0})
        weekly_buckets[key]["sum"] += row["amount"]
        weekly_buckets[key]["count"] += 1

    weekly_labels = sorted(weekly_buckets.keys())
    weekly_values = [
        weekly_buckets[key]["sum"] / weekly_buckets[key]["count"]
        if weekly_buckets[key]["count"] else 0.0
        for key in weekly_labels
    ]

    # 3) hourly count
    hourly_counts = {hour: 0 for hour in range(24)}
    for row in parsed:
        hourly_counts[row["dt"].hour] += 1

    hourly_labels = [f"{hour:02d}h" for hour in range(24)]
    hourly_values = [hourly_counts[hour] for hour in range(24)]

    # 4) weekday count
    weekday_labels = [
        "Lundi", "Mardi", "Mercredi",
        "Jeudi", "Vendredi", "Samedi", "Dimanche"
    ]
    weekday_counts = {i: 0 for i in range(7)}
    for row in parsed:
        weekday_counts[row["dt"].weekday()] += 1

    weekday_values = [weekday_counts[i] for i in range(7)]

    # 5) cumulative volume par jour
    daily_amounts = {}
    for row in parsed:
        day = row["dt"].date().isoformat()
        daily_amounts[day] = daily_amounts.get(day, 0.0) + row["amount"]

    cumulative_labels = sorted(daily_amounts.keys())
    cumulative_values = []
    running = 0.0

    for day in cumulative_labels:
        running += daily_amounts[day]
        cumulative_values.append(running)

    return {
        "daily": {
            "labels": daily_labels,
            "values": daily_values,
        },
        "weekly": {
            "labels": weekly_labels,
            "values": weekly_values,
        },
        "hourly": {
            "labels": hourly_labels,
            "values": hourly_values,
        },
        "weekday": {
            "labels": weekday_labels,
            "values": weekday_values,
        },
        "cumulative": {
            "labels": cumulative_labels,
            "values": cumulative_values,
        },
    }