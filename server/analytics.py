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
        result = {
            "min_date": None,
            "max_date": None,
        }

    return {
        "min_date": row["min_date"],
        "max_date": row["max_date"],
    }


def compute_global_stats(start=None, end=None, year=None, include_transactions=False):
    rows = fetch_transactions(start=start, end=end, year=year)

    if not rows:
        result = {
            "periode": "-",

            # Compatibilité historique
            "nb_utilisateurs": 0,

            # Activité économique
            "nb_acteurs_activite": 0,
            "nb_acteurs_particuliers": 0,
            "nb_acteurs_professionnels": 0,
            "nb_jours_periode_activite": 0,
            "moyenne_transactions_PP": 0.0,
            "moyenne_paiement_UP": 0.0,
            "moyenne_transactions_UU": 0.0,
            "nb_transactions_activite_economique": 0,
            "volume_activite_economique": 0.0,
            "montant_moyen_activite": 0.0,
            "moyenne_transactions_par_jour": 0.0,
            "volume_moyen_par_jour": 0.0,
            "flux_activite": {},


            # Comptes particuliers de dispositif

            "nb_device_private_accounts_active": 0,

            "nb_transactions_device_private_accounts": 0,

            "volume_device_private_accounts": 0.0,

            "nb_transactions_device_private_activity": 0,

            "volume_device_private_activity": 0.0,

            "nb_transactions_device_private_operations": 0,

            "volume_device_private_operations": 0.0,

            "share_device_private_activity_transactions_pct": 0.0,

            "share_device_private_activity_volume_pct": 0.0,

            # Alimentation / sorties du circuit
            "nb_alimentations_circuit": 0,
            "volume_alimente_circuit": 0.0,
            "montant_moyen_alimentation": 0.0,
            "nb_sorties_circuit": 0,
            "volume_sorti_circuit": 0.0,
            "montant_moyen_sortie": 0.0,
            "ecart_net_circuit": 0.0,
            "circuit_inflow_destinations": {},

            # Opérations associatives / techniques
            "nb_operations_assoc_tech": 0,
            "volume_operations_assoc_tech": 0.0,
            "montant_moyen_operations_assoc_tech": 0.0,
            "nb_operations_operator_accounts": 0,
            "volume_operations_operator_accounts": 0.0,
            "nb_operations_user_to_technical_accounts": 0,
            "volume_operations_user_to_technical_accounts": 0.0,
            "montant_moyen_user_to_technical_accounts": 0.0,
            "operations_operator_profiles": {},

        }

        if include_transactions:
            result["transactions"] = []

        return result

    def parse_day(value):
        raw = str(value or "").strip()
        if not raw:
            return None
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
        except Exception:
            try:
                return datetime.fromisoformat(raw[:10]).date()
            except Exception:
                return None

    def avg_amount(items):
        if not items:
            return 0.0
        return float(
            sum(float(row.get("amount", 0) or 0) for row in items) / len(items)
        )

    def amount_sum(items):
        return float(sum(float(row.get("amount", 0) or 0) for row in items))

    dates = [row["date"] for row in rows if row.get("date")]
    parsed_row_days = [parse_day(value) for value in dates]
    parsed_row_days = [day for day in parsed_row_days if day is not None]

    explicit_start_day = parse_day(start)
    explicit_end_day = parse_day(end)

    if explicit_start_day and explicit_end_day:
        period_start_day = min(explicit_start_day, explicit_end_day)
        period_end_day = max(explicit_start_day, explicit_end_day)
    elif parsed_row_days:
        period_start_day = min(parsed_row_days)
        period_end_day = max(parsed_row_days)
    else:
        period_start_day = None
        period_end_day = None

    if period_start_day and period_end_day:
        periode = (
            f"{period_start_day.strftime('%d/%m/%Y')} - "
            f"{period_end_day.strftime('%d/%m/%Y')}"
        )
        nb_jours_periode_activite = max(
            (period_end_day - period_start_day).days + 1,
            1,
        )
    else:
        periode = "-"
        nb_jours_periode_activite = 0

    classified_rows = [
        (row, _classify_analytical_transaction(row))
        for row in rows
    ]

    # ---------------------------------------------------------------------
    # 1. Activité économique
    # ---------------------------------------------------------------------

    activity_rows = [
        row for row, classification in classified_rows
        if classification["is_activity"]
    ]

    particuliers = set()
    professionnels = set()
    acteurs_legacy = set()

    for row in activity_rows:
        from_label = str(row.get("from_label", "")).strip()
        to_label = str(row.get("to_label", "")).strip()

        for label in (from_label, to_label):
            if not label:
                continue

            acteurs_legacy.add(label)

            family = _actor_flow_family(label)
            if family == "U":
                particuliers.add(label)
            elif family == "P":
                professionnels.add(label)

    flux_buckets = {}

    for row in activity_rows:
        flux = _structural_flow_key(row)
        amount = float(row.get("amount", 0) or 0)

        bucket = flux_buckets.setdefault(flux, {
            "nb_transactions": 0,
            "volume_total": 0.0,
        })
        bucket["nb_transactions"] += 1
        bucket["volume_total"] += amount

    flux_activite = {}
    for flux, bucket in flux_buckets.items():
        nb_transactions = bucket["nb_transactions"]
        volume_total = bucket["volume_total"]
        flux_activite[flux] = {
            "nb_transactions": nb_transactions,
            "volume_total": float(volume_total),
            "montant_moyen": (
                float(volume_total / nb_transactions)
                if nb_transactions else 0.0
            ),
        }

    pp = [
        row for row in activity_rows
        if _actor_flow_family(row.get("from_label")) == "P"
        and _actor_flow_family(row.get("to_label")) == "P"
    ]

    up = [
        row for row in activity_rows
        if _actor_flow_family(row.get("from_label")) == "U"
        and _actor_flow_family(row.get("to_label")) == "P"
    ]

    uu = [
        row for row in activity_rows
        if _actor_flow_family(row.get("from_label")) == "U"
        and _actor_flow_family(row.get("to_label")) == "U"
    ]

    volume_activite_economique = amount_sum(activity_rows)
    nb_transactions_activite_economique = len(activity_rows)

    montant_moyen_activite = (
        volume_activite_economique / nb_transactions_activite_economique
        if nb_transactions_activite_economique else 0.0
    )

    moyenne_transactions_par_jour = (
        nb_transactions_activite_economique / nb_jours_periode_activite
        if nb_jours_periode_activite else 0.0
    )

    volume_moyen_par_jour = (
        volume_activite_economique / nb_jours_periode_activite
        if nb_jours_periode_activite else 0.0
    )

    # ---------------------------------------------------------------------
    # 2. Alimentation / sorties du circuit
    # ---------------------------------------------------------------------

    circuit_inflow_rows = [
        row for row, classification in classified_rows
        if classification["bucket"] == "inflows"
    ]

    circuit_outflow_rows = [
        row for row, classification in classified_rows
        if classification["bucket"] == "outflows"
    ]

    volume_alimente_circuit = amount_sum(circuit_inflow_rows)
    volume_sorti_circuit = amount_sum(circuit_outflow_rows)

    circuit_inflow_destination_buckets = {}

    for row in circuit_inflow_rows:
        flux = _structural_flow_key(row)
        amount = float(row.get("amount", 0) or 0)

        bucket = circuit_inflow_destination_buckets.setdefault(flux, {
            "nb_transactions": 0,
            "volume_total": 0.0,
        })
        bucket["nb_transactions"] += 1
        bucket["volume_total"] += amount

    circuit_inflow_destinations = {}

    for flux, bucket in circuit_inflow_destination_buckets.items():
        nb_transactions = bucket["nb_transactions"]
        volume_total = bucket["volume_total"]

        circuit_inflow_destinations[flux] = {
            "nb_transactions": nb_transactions,
            "volume_total": float(volume_total),
            "montant_moyen": (
                float(volume_total / nb_transactions)
                if nb_transactions else 0.0
            ),
        }

    # ---------------------------------------------------------------------
    # 3. Opérations associatives / techniques
    # ---------------------------------------------------------------------

    operations_pairs = [
        (row, classification)
        for row, classification in classified_rows
        if classification["bucket"] == "operations"
    ]

    operations_rows = [row for row, _ in operations_pairs]

    operator_rows = [
        row for row, classification in operations_pairs
        if _operations_family_key(classification) == "operator_accounts"
    ]

    user_to_technical_rows = [
        row for row, classification in operations_pairs
        if _operations_family_key(classification) == "user_to_technical_accounts"
    ]

    operator_profile_buckets = {}

    for row in operator_rows:
        profile = _operator_operation_profile(row)
        amount = float(row.get("amount", 0) or 0)

        bucket = operator_profile_buckets.setdefault(profile, {
            "nb_transactions": 0,
            "volume_total": 0.0,
        })
        bucket["nb_transactions"] += 1
        bucket["volume_total"] += amount

    operations_operator_profiles = {}

    for profile, bucket in operator_profile_buckets.items():
        nb_transactions = bucket["nb_transactions"]
        volume_total = bucket["volume_total"]

        operations_operator_profiles[profile] = {
            "nb_transactions": nb_transactions,
            "volume_total": float(volume_total),
            "montant_moyen": (
                float(volume_total / nb_transactions)
                if nb_transactions else 0.0
            ),
        }

    # ---------------------------------------------------------------------
    # 4. Transactions détaillées historiques
    # ---------------------------------------------------------------------

    transactions = None

    if include_transactions:
        transactions = [
            {
                "Date": row["date"][:10],
                "Réalisé par": row.get("from_label", ""),
                "Vers": row.get("to_label", ""),
                "Montant": float(row.get("amount", 0) or 0),
            }
            for row in rows
        ]

    # ---------------------------------------------------------------------
    # Comptes particuliers de dispositif
    # ---------------------------------------------------------------------
    #
    # Les pseudonymes UD_* correspondent à des comptes particuliers de
    # dispositif / temporaires. Ils restent analytiquement dans la famille
    # des particuliers, mais leur poids est isolé ici lorsqu'ils apparaissent
    # dans la période sélectionnée.
    def is_device_private_label(label):
        return str(label or "").strip().startswith("UD_")

    device_private_pairs = [
        (row, classification)
        for row, classification in classified_rows
        if (
            is_device_private_label(row.get("from_label"))
            or is_device_private_label(row.get("to_label"))
        )
    ]

    device_private_rows = [
        row for row, _classification in device_private_pairs
    ]

    device_private_activity_rows = [
        row for row, classification in device_private_pairs
        if classification.get("is_activity")
    ]

    device_private_operations_rows = [
        row for row, classification in device_private_pairs
        if classification.get("bucket") == "operations"
    ]

    device_private_accounts = set()
    for row in device_private_rows:
        from_label = str(row.get("from_label") or "").strip()
        to_label = str(row.get("to_label") or "").strip()

        if is_device_private_label(from_label):
            device_private_accounts.add(from_label)

        if is_device_private_label(to_label):
            device_private_accounts.add(to_label)

    device_private_activity_count = len(device_private_activity_rows)
    device_private_activity_volume = amount_sum(device_private_activity_rows)

    activity_count_for_device_share = len(activity_rows)
    activity_volume_for_device_share = amount_sum(activity_rows)

    share_device_private_activity_transactions_pct = (
        float(device_private_activity_count / activity_count_for_device_share * 100.0)
        if activity_count_for_device_share
        else 0.0
    )

    share_device_private_activity_volume_pct = (
        float(device_private_activity_volume / activity_volume_for_device_share * 100.0)
        if activity_volume_for_device_share
        else 0.0
    )

    result = {
        "periode": periode,

        # Compatibilité historique
        "nb_utilisateurs": len(acteurs_legacy),

        # Activité économique
        "nb_acteurs_activite": len(particuliers) + len(professionnels),
        "nb_acteurs_particuliers": len(particuliers),
        "nb_acteurs_professionnels": len(professionnels),
        "nb_jours_periode_activite": nb_jours_periode_activite,

        "moyenne_transactions_PP": avg_amount(pp),
        "moyenne_paiement_UP": avg_amount(up),
        "moyenne_transactions_UU": avg_amount(uu),

        "nb_transactions_activite_economique": nb_transactions_activite_economique,
        "volume_activite_economique": volume_activite_economique,
        "montant_moyen_activite": float(montant_moyen_activite),
        "moyenne_transactions_par_jour": float(moyenne_transactions_par_jour),
        "volume_moyen_par_jour": float(volume_moyen_par_jour),
        "flux_activite": flux_activite,

        # Comptes particuliers de dispositif
        "nb_device_private_accounts_active": len(device_private_accounts),
        "nb_transactions_device_private_accounts": len(device_private_rows),
        "volume_device_private_accounts": amount_sum(device_private_rows),
        "nb_transactions_device_private_activity": device_private_activity_count,
        "volume_device_private_activity": device_private_activity_volume,
        "nb_transactions_device_private_operations": len(device_private_operations_rows),
        "volume_device_private_operations": amount_sum(device_private_operations_rows),
        "share_device_private_activity_transactions_pct": share_device_private_activity_transactions_pct,
        "share_device_private_activity_volume_pct": share_device_private_activity_volume_pct,

        # Alimentation / sorties du circuit
        "nb_alimentations_circuit": len(circuit_inflow_rows),
        "volume_alimente_circuit": volume_alimente_circuit,
        "montant_moyen_alimentation": avg_amount(circuit_inflow_rows),

        "nb_sorties_circuit": len(circuit_outflow_rows),
        "volume_sorti_circuit": volume_sorti_circuit,
        "montant_moyen_sortie": avg_amount(circuit_outflow_rows),

        "ecart_net_circuit": float(volume_alimente_circuit - volume_sorti_circuit),
        "circuit_inflow_destinations": circuit_inflow_destinations,

        # Opérations associatives / techniques
        "nb_operations_assoc_tech": len(operations_rows),
        "volume_operations_assoc_tech": amount_sum(operations_rows),
        "montant_moyen_operations_assoc_tech": avg_amount(operations_rows),

        "nb_operations_operator_accounts": len(operator_rows),
        "volume_operations_operator_accounts": amount_sum(operator_rows),

        "nb_operations_user_to_technical_accounts": len(user_to_technical_rows),
        "volume_operations_user_to_technical_accounts": amount_sum(user_to_technical_rows),
        "montant_moyen_user_to_technical_accounts": avg_amount(user_to_technical_rows),

        "operations_operator_profiles": operations_operator_profiles,

    }

    if include_transactions:
        result["transactions"] = transactions or []

    return result

def compute_network_data(start=None, end=None, year=None, include_operators=False):
    rows = fetch_transactions(start=start, end=end, year=year)

    # Périmètre conservé pour cette vue :
    # le réseau interprofessionnel dirigé P -> P.
    pp_rows = [
        row for row in rows
        if str(row.get("from_label", "")).startswith("P")
        and str(row.get("to_label", "")).startswith("P")
    ]

    def is_operator_account_label(label):
        normalized = str(label or "").strip()
        return normalized.startswith("P0000") or normalized.startswith("P9999")

    if not include_operators:
        pp_rows = [
            row for row in pp_rows
            if not is_operator_account_label(row.get("from_label", ""))
            and not is_operator_account_label(row.get("to_label", ""))
        ]

    def empty_payload():
        return {
            "summary": {
                "node_count": 0,
                "edge_count": 0,
                "transaction_count": 0,
                "total_volume": 0.0,
                "average_edge_volume": 0.0,
                "median_edge_volume": 0.0,
                "reciprocal_pair_count": 0,
                "reciprocal_edge_count": 0,
                "reciprocal_edge_share": None,
                "operator_accounts_included": bool(include_operators),
            },
            "nodes": [],
            "edges": [],
        }

    if not pp_rows:
        return empty_payload()

    edge_stats = {}
    node_stats = {}

    def get_node_stats(node_id):
        if node_id not in node_stats:
            node_stats[node_id] = {
                "incoming_volume": 0.0,
                "outgoing_volume": 0.0,
                "incoming_transaction_count": 0,
                "outgoing_transaction_count": 0,
                "inbound_relation_count": 0,
                "outbound_relation_count": 0,
                "neighbors": set(),
            }
        return node_stats[node_id]

    for row in pp_rows:
        source = str(row.get("from_label", "")).strip()
        target = str(row.get("to_label", "")).strip()
        amount = float(row.get("amount", 0) or 0)

        if not source or not target:
            continue

        row_date = str(row.get("date", "") or "")[:10] or None

        source_stats = get_node_stats(source)
        target_stats = get_node_stats(target)

        source_stats["outgoing_volume"] += amount
        source_stats["outgoing_transaction_count"] += 1

        target_stats["incoming_volume"] += amount
        target_stats["incoming_transaction_count"] += 1

        edge_key = (source, target)
        if edge_key not in edge_stats:
            edge_stats[edge_key] = {
                "source": source,
                "target": target,
                "volume": 0.0,
                "transaction_count": 0,
                "first_date": row_date,
                "last_date": row_date,
            }

        edge = edge_stats[edge_key]
        edge["volume"] += amount
        edge["transaction_count"] += 1

        if row_date:
            if not edge["first_date"] or row_date < edge["first_date"]:
                edge["first_date"] = row_date
            if not edge["last_date"] or row_date > edge["last_date"]:
                edge["last_date"] = row_date

    if not edge_stats:
        return empty_payload()

    for (source, target), edge in edge_stats.items():
        source_stats = get_node_stats(source)
        target_stats = get_node_stats(target)

        source_stats["outbound_relation_count"] += 1
        target_stats["inbound_relation_count"] += 1

        source_stats["neighbors"].add(target)
        target_stats["neighbors"].add(source)

    nodes = []
    for node_id in sorted(node_stats):
        stats = node_stats[node_id]
        incoming_volume = float(stats["incoming_volume"])
        outgoing_volume = float(stats["outgoing_volume"])
        relation_volume_total = incoming_volume + outgoing_volume
        net_relation_balance = incoming_volume - outgoing_volume

        nodes.append({
            "data": {
                "id": node_id,
                "label": node_id,
                "incoming_volume": incoming_volume,
                "outgoing_volume": outgoing_volume,
                "relation_volume_total": relation_volume_total,
                "net_relation_balance": net_relation_balance,
                "incoming_transaction_count": int(stats["incoming_transaction_count"]),
                "outgoing_transaction_count": int(stats["outgoing_transaction_count"]),
                "inbound_relation_count": int(stats["inbound_relation_count"]),
                "outbound_relation_count": int(stats["outbound_relation_count"]),
                "relation_count_total": int(
                    stats["inbound_relation_count"] + stats["outbound_relation_count"]
                ),
                "neighbor_count": len(stats["neighbors"]),
                "is_operator_account": node_id.startswith("P0000") or node_id.startswith("P9999"),
            }
        })

    edges = []
    edge_volumes = []
    total_volume = 0.0
    total_transactions = 0

    for (source, target), edge in sorted(edge_stats.items()):
        volume = float(edge["volume"])
        transaction_count = int(edge["transaction_count"])
        average_amount = volume / transaction_count if transaction_count else 0.0

        edge_volumes.append(volume)
        total_volume += volume
        total_transactions += transaction_count

        edges.append({
            "data": {
                "source": source,
                "target": target,
                "weight": volume,
                "volume": volume,
                "transaction_count": transaction_count,
                "average_amount": float(average_amount),
                "first_date": edge["first_date"],
                "last_date": edge["last_date"],
            }
        })

    edge_volumes_sorted = sorted(edge_volumes)
    edge_count = len(edges)

    if edge_count % 2 == 1:
        median_edge_volume = edge_volumes_sorted[edge_count // 2]
    else:
        median_edge_volume = (
            edge_volumes_sorted[(edge_count // 2) - 1]
            + edge_volumes_sorted[edge_count // 2]
        ) / 2

    directed_edges = set(edge_stats.keys())
    reciprocal_pairs = set()

    for source, target in directed_edges:
        if source == target:
            continue
        if (target, source) in directed_edges:
            reciprocal_pairs.add(tuple(sorted((source, target))))

    reciprocal_pair_count = len(reciprocal_pairs)
    reciprocal_edge_count = reciprocal_pair_count * 2
    reciprocal_edge_share = (
        reciprocal_edge_count / edge_count
        if edge_count > 0
        else None
    )

    return {
        "summary": {
            "node_count": len(nodes),
            "edge_count": edge_count,
            "transaction_count": total_transactions,
            "total_volume": float(total_volume),
            "average_edge_volume": float(total_volume / edge_count) if edge_count else 0.0,
            "median_edge_volume": float(median_edge_volume),
            "reciprocal_pair_count": reciprocal_pair_count,
            "reciprocal_edge_count": reciprocal_edge_count,
            "reciprocal_edge_share": reciprocal_edge_share,
            "operator_accounts_included": bool(include_operators),
        },
        "nodes": nodes,
        "edges": edges,
    }

def _get_odoo_professional_enrichment_index(professional_refs):
    refs = sorted({ref for ref in professional_refs if ref})
    if not refs:
        return {}

    placeholders = ", ".join("?" for _ in refs)
    conn = get_connection()
    cur = conn.cursor()

    rows = cur.execute(f"""
        SELECT
            professional_ref,
            odoo_name,
            industry_name,
            detailed_activity,
            COALESCE(
                NULLIF(TRIM(zip), ''),
                NULLIF(TRIM(cyclos_zip), '')
            ) AS postal_code
        FROM odoo_professional_enrichment
        WHERE professional_ref IN ({placeholders})
    """, refs).fetchall()

    conn.close()
    return {
        row["professional_ref"]: dict(row)
        for row in rows
    }


def _format_professional_directory_label(professional_ref, observed_labels, enrichment):
    observed_label = str(observed_labels.get(professional_ref) or "").strip()
    if observed_label:
        return observed_label

    odoo_name = str((enrichment or {}).get("odoo_name") or "").strip()
    if odoo_name:
        return f"{professional_ref} - {odoo_name}"

    return professional_ref



def _is_conversion_source_label(label):
    """
    Identifie la source technique d'une conversion / alimentation
    vers un compte utilisateur ou professionnel.
    """
    return str(label or "").strip() == "T_Émission"


def _is_reconversion_target_label(label):
    """
    Identifie la cible technique d'une reconversion / sortie
    depuis un compte utilisateur ou professionnel.
    """
    return str(label or "").strip() == "T_Conversion"


def compute_professionals_ranking(start=None, end=None, year=None):
    rows = fetch_transactions(start=start, end=end, year=year)

    if not rows:
        return []

    b2b_recu = {}
    b2b_emis = {}
    b2c = {}
    remuneration = {}
    pros = set()
    observed_labels = {}
    converted = {}
    reconverted = {}

    for row in rows:
        from_label = str(row.get("from_label", "")).strip()
        to_label = str(row.get("to_label", "")).strip()
        amount = float(row.get("amount", 0) or 0)

        from_ref = _extract_professional_ref(from_label)
        to_ref = _extract_professional_ref(to_label)

        from_is_pro = from_ref is not None
        to_is_pro = to_ref is not None
        from_is_user = from_label.startswith("U")
        to_is_user = to_label.startswith("U")
        from_is_conversion = _is_conversion_source_label(from_label)
        to_is_reconversion = _is_reconversion_target_label(to_label)

        if from_is_pro:
            pros.add(from_ref)
            observed_labels.setdefault(from_ref, from_label)
        if to_is_pro:
            pros.add(to_ref)
            observed_labels.setdefault(to_ref, to_label)

        if from_is_pro and to_is_pro:
            b2b_recu[to_ref] = b2b_recu.get(to_ref, 0.0) + amount
            b2b_emis[from_ref] = b2b_emis.get(from_ref, 0.0) + amount

        if from_is_user and to_is_pro and not from_is_conversion:
            b2c[to_ref] = b2c.get(to_ref, 0.0) + amount

        if from_is_pro and to_is_user:
            remuneration[from_ref] = remuneration.get(from_ref, 0.0) + amount

        if to_is_pro and from_is_conversion:
            converted[to_ref] = converted.get(to_ref, 0.0) + amount

        if from_is_pro and to_is_reconversion:
            reconverted[from_ref] = reconverted.get(from_ref, 0.0) + amount

    enrichment_by_ref = _get_odoo_professional_enrichment_index(pros)
    ranking = []
    for pro in pros:
        enrichment = enrichment_by_ref.get(pro, {})
        total_recu = b2b_recu.get(pro, 0.0) + b2c.get(pro, 0.0)
        total_emis = b2b_emis.get(pro, 0.0) + remuneration.get(pro, 0.0)
        total_converti = converted.get(pro, 0.0)
        total_reconverti = reconverted.get(pro, 0.0)
        reuse_base = total_recu + total_converti
        reuse_rate = (total_emis / reuse_base) * 100 if reuse_base > 0 else 0.0
        industry_name = str(enrichment.get("industry_name") or "").strip()
        detailed_activity = str(enrichment.get("detailed_activity") or "").strip()

        ranking.append({
            "Professionnel": _format_professional_directory_label(
                pro,
                observed_labels,
                enrichment,
            ),
            "Secteur d’activité": industry_name or detailed_activity,
            "Code postal": enrichment.get("postal_code") or "",
            "Reçu des professionnels": round(b2b_recu.get(pro, 0.0), 2),
            "Reçu des particuliers": round(b2c.get(pro, 0.0), 2),
            "Total reçu": round(total_recu, 2),
            "Émis vers les professionnels": round(b2b_emis.get(pro, 0.0), 2),
            "Émis vers les particuliers": round(remuneration.get(pro, 0.0), 2),
            "Total émis": round(total_emis, 2),
            "Total converti": round(total_converti, 2),
            "Total reconverti": round(total_reconverti, 2),
            "Taux de réutilisation": round(reuse_rate, 2),

            # Clés historiques conservées pour les anciens clients.
            "B2B Reçu": round(b2b_recu.get(pro, 0.0), 2),
            "B2B Emis": round(b2b_emis.get(pro, 0.0), 2),
            "B2C": round(b2c.get(pro, 0.0), 2),
            "Paiements Reçu B+C": round(total_recu, 2),
            "Rémunération": round(remuneration.get(pro, 0.0), 2),
            "Total Reçu": round(total_recu, 2),
        })

    ranking.sort(key=lambda x: x["Total reçu"], reverse=True)
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
        and not _is_conversion_source_label(row.get("from_label", ""))
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
        and _is_reconversion_target_label(row.get("to_label", ""))
    )

    montant_converti = sum(
        float(row.get("amount", 0) or 0)
        for row in related
        if num_professionnel in str(row.get("to_label", ""))
        and _is_conversion_source_label(row.get("from_label", ""))
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
            and not _is_conversion_source_label(from_label)
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




def compute_sector_activity(start=None, end=None, year=None):
    """
    Agrège l'activité monétaire numérique par secteur principal.

    Périmètre :
    - professionnels MLCFlux enrichis depuis Odoo ;
    - secteur principal uniquement ;
    - activité calculée sur la période demandée.

    Mesures :
    - gonettes reçues ;
    - gonettes émises hors reconversion ;
    - pros actifs ;
    - taux de réutilisation ;
    - ventilation des recettes entre C2B, B2B et autres flux.
    """
    conn = get_connection()
    cur = conn.cursor()

    professional_rows = cur.execute("""
        SELECT
            professional_ref,
            odoo_partner_id,
            odoo_name,
            industry_id,
            industry_name
        FROM odoo_professional_enrichment
        ORDER BY professional_ref ASC
    """).fetchall()

    conn.close()

    professionals = [dict(row) for row in professional_rows]
    transaction_rows = fetch_transactions(start=start, end=end, year=year)
    professionals = _compute_map_activity_scores(professionals, transaction_rows)

    sectors = {}
    ref_to_sector_label = {}

    professional_count = len(professionals)
    professionals_with_sector = 0
    professionals_without_sector = 0

    active_professional_count = 0
    active_professionals_with_sector = 0
    active_professionals_without_sector = 0

    total_received_volume = 0.0
    total_emitted_volume = 0.0
    total_received_count = 0
    total_emitted_count = 0

    for professional in professionals:
        industry_name = str(professional.get("industry_name") or "").strip()
        sector_label = industry_name or "Secteur non renseigné"

        if industry_name:
            professionals_with_sector += 1
        else:
            professionals_without_sector += 1

        ref_to_sector_label[professional["professional_ref"]] = sector_label

        received_volume = float(professional.get("received_volume") or 0.0)
        emitted_volume = float(professional.get("emitted_volume") or 0.0)
        received_count = int(professional.get("received_count") or 0)
        emitted_count = int(professional.get("emitted_count") or 0)

        is_active = received_count > 0 or emitted_count > 0

        if is_active:
            active_professional_count += 1
            if industry_name:
                active_professionals_with_sector += 1
            else:
                active_professionals_without_sector += 1

        total_received_volume += received_volume
        total_emitted_volume += emitted_volume
        total_received_count += received_count
        total_emitted_count += emitted_count

        sector = sectors.setdefault(sector_label, {
            "sector_name": sector_label,
            "industry_id": professional.get("industry_id"),
            "professional_count": 0,
            "active_professional_count": 0,
            "received_volume": 0.0,
            "emitted_volume": 0.0,
            "total_flow_volume": 0.0,
            "received_count": 0,
            "emitted_count": 0,
            "reuse_rate": None,
            "received_volume_share": 0.0,
            "c2b_received_volume": 0.0,
            "b2b_received_volume": 0.0,
            "other_received_volume": 0.0,
            "c2b_received_count": 0,
            "b2b_received_count": 0,
            "other_received_count": 0,
            "c2b_received_share": 0.0,
            "b2b_received_share": 0.0,
            "other_received_share": 0.0,
        })

        sector["professional_count"] += 1

        if is_active:
            sector["active_professional_count"] += 1

        sector["received_volume"] += received_volume
        sector["emitted_volume"] += emitted_volume
        sector["total_flow_volume"] += received_volume + emitted_volume
        sector["received_count"] += received_count
        sector["emitted_count"] += emitted_count

    # Ventilation des recettes par origine : C2B / B2B / autres.
    for row in transaction_rows:
        from_label = str(row.get("from_label", "")).strip()
        to_label = str(row.get("to_label", "")).strip()
        amount = float(row.get("amount", 0) or 0)

        to_ref = _extract_professional_ref(to_label)

        if not to_ref:
            continue

        if to_ref not in ref_to_sector_label:
            continue

        if _is_conversion_source_label(from_label):
            continue

        sector_label = ref_to_sector_label[to_ref]
        sector = sectors[sector_label]

        if from_label.startswith("U"):
            sector["c2b_received_volume"] += amount
            sector["c2b_received_count"] += 1
        elif from_label.startswith("P"):
            sector["b2b_received_volume"] += amount
            sector["b2b_received_count"] += 1
        else:
            sector["other_received_volume"] += amount
            sector["other_received_count"] += 1

    sector_rows = []

    for sector in sectors.values():
        received_volume = sector["received_volume"]
        emitted_volume = sector["emitted_volume"]

        sector["reuse_rate"] = (
            emitted_volume / received_volume
            if received_volume > 0
            else None
        )

        sector["received_volume_share"] = (
            received_volume / total_received_volume
            if total_received_volume > 0
            else 0.0
        )

        if received_volume > 0:
            sector["c2b_received_share"] = sector["c2b_received_volume"] / received_volume
            sector["b2b_received_share"] = sector["b2b_received_volume"] / received_volume
            sector["other_received_share"] = sector["other_received_volume"] / received_volume

        sector_rows.append(sector)

    sector_rows.sort(
        key=lambda sector: (
            -sector["received_volume"],
            sector["sector_name"].lower(),
        )
    )

    total_flow_volume = total_received_volume + total_emitted_volume

    total_c2b_received_volume = sum(
        sector["c2b_received_volume"]
        for sector in sector_rows
    )
    total_b2b_received_volume = sum(
        sector["b2b_received_volume"]
        for sector in sector_rows
    )
    total_other_received_volume = sum(
        sector["other_received_volume"]
        for sector in sector_rows
    )

    summary = {
        "sector_count": len(sector_rows),
        "professional_count": professional_count,
        "professionals_with_sector": professionals_with_sector,
        "professionals_without_sector": professionals_without_sector,
        "active_professional_count": active_professional_count,
        "active_professionals_with_sector": active_professionals_with_sector,
        "active_professionals_without_sector": active_professionals_without_sector,
        "total_received_volume": float(total_received_volume),
        "total_emitted_volume": float(total_emitted_volume),
        "total_flow_volume": float(total_flow_volume),
        "total_received_count": int(total_received_count),
        "total_emitted_count": int(total_emitted_count),
        "overall_reuse_rate": (
            total_emitted_volume / total_received_volume
            if total_received_volume > 0
            else None
        ),
        "total_c2b_received_volume": float(total_c2b_received_volume),
        "total_b2b_received_volume": float(total_b2b_received_volume),
        "total_other_received_volume": float(total_other_received_volume),
        "period": {
            "start": start,
            "end": end,
            "year": year,
        },
    }

    return {
        "summary": summary,
        "sectors": sector_rows,
    }



def _actor_flow_family(label):
    """
    Retourne la grande famille d'un acteur anonymisé.

    P : professionnel
    U : particulier pseudonymisé, y compris UD_* = particulier de dispositif
    T : compte technique
    ? : cas résiduel inconnu

    """
    label = str(label or "").strip()

    if label.startswith("P"):
        return "P"

    if label.startswith("U_") or label.startswith("UD_"):
        return "U"

    if label.startswith("T_"):
        return "T"

    return "?"

def _classify_macro_flow(from_label, to_label):
    """
    Classe les transactions en quatre familles lisibles avec le vocabulaire
    métier de la monnaie locale.

    - payments :
        paiements et circulation économique entre acteurs P/U
    - conversions :
        entrées de Gonettes numériques vers les comptes du réseau
    - reconversions :
        sorties du circuit, principalement les flux professionnels vers
        un compte technique
    - regularizations :
        annulations, avoirs, clôtures, corrections ou cas techniques résiduels

    Cette typologie reste macroscopique. Elle sert à distinguer clairement
    l'activité économique courante des opérations de gestion monétaire.
    """
    source = _actor_flow_family(from_label)
    target = _actor_flow_family(to_label)

    if source in {"P", "U"} and target in {"P", "U"}:
        return "payments"

    if source in {"A", "C"} and target in {"P", "U"}:
        return "conversions"

    if source == "P" and target in {"A", "C"}:
        return "reconversions"

    # Les flux U→T, T→T et les cas résiduels sont rangés ici.
    # L'audit post-rebuild montre qu'ils correspondent très majoritairement
    # à des annulations, avoirs, clôtures ou corrections techniques.
    return "regularizations"


def _is_operator_account_label(label):
    """
    Identifie les comptes opérateurs exclus de l'activité économique centrale.

    - P0000 : compte historique / opérateur de l'association Gonette ;
    - P9999 : compte de collecte des cotisations mensualisées.

    On utilise le préfixe technique du compte, plus stable que son libellé complet.
    """
    label = str(label or "").strip()
    return label.startswith("P0000") or label.startswith("P9999")


def _classify_analytical_transaction(row):
    """
    Classification analytique structurelle des transactions.

    Cette classification ne s'appuie pas sur les libellés libres des transactions,
    mais uniquement sur :
    - group_label ;
    - la famille structurelle des acteurs source / destination ;
    - l'identification des comptes opérateurs P0000 et P9999.

    Buckets renvoyés :
    - activity :
        circulation économique du réseau hors comptes opérateurs ;
    - inflows :
        alimentations du circuit numérique ;
    - outflows :
        reconversions / sorties professionnelles ;
    - operations :
        opérations associatives, techniques ou hors périmètre économique central.
    """
    group_label = str(row.get("group_label") or "").strip()

    from_label = str(row.get("from_label") or "").strip()
    to_label = str(row.get("to_label") or "").strip()

    source = _actor_flow_family(from_label)
    target = _actor_flow_family(to_label)

    source_is_operator = _is_operator_account_label(from_label)
    target_is_operator = _is_operator_account_label(to_label)

    def result(bucket, family, is_activity=False):
        return {
            "bucket": bucket,
            "family": family,
            "is_activity": is_activity,
            "source_family": source,
            "target_family": target,
        }

    # ---------------------------------------------------------------------
    # 1. Alimentation du circuit numérique
    # ---------------------------------------------------------------------
    # L'audit de group_label montre que "Émission" isole structurellement
    # les entrées de monnaie numérique.
    if group_label == "Émission":
        return result(
            "inflows",
            "Alimentations du circuit numérique",
            is_activity=False,
        )

    # ---------------------------------------------------------------------
    # 2. Sorties / reconversions professionnelles
    # ---------------------------------------------------------------------
    # L'audit montre que Compte Pro + P→compte technique correspond au bloc
    # des reconversions et sorties professionnelles.
    if group_label == "Compte Pro" and source == "P" and target == "T":
        return result(
            "outflows",
            "Reconversions / sorties professionnelles",
            is_activity=False,
        )

    # ---------------------------------------------------------------------
    # 3. Activité économique centrale
    # ---------------------------------------------------------------------
    # Formule retenue :
    # - transactions des groupes Compte ou Compte Pro ;
    # - hors flux vers comptes techniques ;
    # - hors transactions impliquant P0000 ou P9999.
    if (
        group_label in {"Compte", "Compte Pro"}
        and target != "T"
        and not source_is_operator
        and not target_is_operator
    ):
        return result(
            "activity",
            "Activité économique hors comptes opérateurs",
            is_activity=True,
        )

    # ---------------------------------------------------------------------
    # 4. Opérations associatives, techniques ou hors activité centrale
    # ---------------------------------------------------------------------

    if source_is_operator or target_is_operator:
        return result(
            "operations",
            "Flux impliquant les comptes opérateurs P0000 / P9999",
            is_activity=False,
        )

    if group_label == "Compte" and source == "U" and target == "T":
        return result(
            "operations",
            "Flux particuliers vers comptes techniques",
            is_activity=False,
        )

    return result(
        "operations",
        "Autres opérations techniques ou résiduelles",
        is_activity=False,
    )


def _operator_account_code(label):
    """
    Retourne le code du compte opérateur explicitement reconnu,
    ou None si le libellé ne correspond pas à P0000 / P9999.
    """
    label = str(label or "").strip()

    if label.startswith("P0000"):
        return "P0000"

    if label.startswith("P9999"):
        return "P9999"

    return None


def _operator_operation_profile(row):
    """
    Profil structurel des opérations impliquant les comptes opérateurs.
    """
    source_code = _operator_account_code(row.get("from_label"))
    target_code = _operator_account_code(row.get("to_label"))

    if source_code and target_code:
        if source_code == target_code:
            return f"{source_code}_involved"
        return "P0000_P9999_bridge"

    if source_code:
        return f"{source_code}_involved"

    if target_code:
        return f"{target_code}_involved"

    return "no_operator_account"


def _operations_family_key(classification):
    """
    Clé courte utilisée dans les indicateurs et graphes de l'onglet 3.
    """
    family = classification.get("family")

    if family == "Flux impliquant les comptes opérateurs P0000 / P9999":
        return "operator_accounts"

    if family == "Flux particuliers vers comptes techniques":
        return "user_to_technical_accounts"

    return "other_operations"


def _structural_flow_key(row):
    """
    Flux structurel lisible de type P→P, U→T, etc.
    """
    source = _actor_flow_family(row.get("from_label"))
    target = _actor_flow_family(row.get("to_label"))
    return f"{source}→{target}"


def _operations_functional_flow_key(row):
    """
    Catégorise les opérations hors activité économique selon le rôle réel
    des comptes impliqués.

    Cette lecture évite d'afficher des catégories brutes P→P / U→P / P→U,
    trop ambiguës dans l'onglet 3 dès que P0000 ou P9999 sont impliqués.
    """
    source = _actor_flow_family(row.get("from_label"))
    target = _actor_flow_family(row.get("to_label"))

    source_operator = _operator_account_code(row.get("from_label"))
    target_operator = _operator_account_code(row.get("to_label"))

    if source == "P" and target == "P":
        if source_operator and target_operator:
            return "operator_to_operator"
        if target_operator:
            return "professional_to_operator"
        if source_operator:
            return "operator_to_professional"

    if source == "U" and target == "T":
        return "user_to_technical_accounts"

    if source == "U" and target == "P" and target_operator:
        return "user_to_operator"

    if source == "P" and source_operator and target == "U":
        return "operator_to_user"

    if source == "T" and target == "P" and target_operator:
        return "technical_account_to_operator"

    return "other_operations"


def compute_stats_charts(start=None, end=None, year=None):
    rows = fetch_transactions(start=start, end=end, year=year)

    weekly_activity_flow_definitions = [
        {
            "key": "U→P",
            "short_label": "U→P",
            "label": "Particuliers → professionnels",
        },
        {
            "key": "P→P",
            "short_label": "P→P",
            "label": "Professionnels → professionnels",
        },
        {
            "key": "P→U",
            "short_label": "P→U",
            "label": "Professionnels → particuliers",
        },
        {
            "key": "U→U",
            "short_label": "U→U",
            "label": "Particuliers → particuliers",
        },
        {
            "key": "atypical",
            "short_label": "Atypiques",
            "label": "Flux atypiques inclus dans l’activité",
        },
    ]

    monthly_circuit_flow_definitions = [
        {
            "key": "inflows",
            "short_label": "Alimentations",
            "label": "Alimentations du circuit",
        },
        {
            "key": "outflows",
            "short_label": "Sorties",
            "label": "Sorties / reconversions professionnelles",
        },
    ]

    monthly_inflow_destination_definitions = [
        {
            "key": "T→U",
            "short_label": "T→U",
            "label": "Comptes techniques → particuliers",
        },
        {
            "key": "T→P",
            "short_label": "T→P",
            "label": "Comptes techniques → professionnels",
        },
        {
            "key": "T→T",
            "short_label": "T→T",
            "label": "Entre comptes techniques",
        },
        {
            "key": "atypical",
            "short_label": "Autres",
            "label": "Autres flux d’alimentation",
        },
    ]


    monthly_operations_family_definitions = [
        {
            "key": "operator_accounts",
            "short_label": "Comptes opérateurs",
            "label": "Flux impliquant P0000 / P9999",
        },
        {
            "key": "user_to_technical_accounts",
            "short_label": "Particuliers → comptes techniques",
            "label": "Flux particuliers vers comptes techniques",
        },
    ]

    monthly_operator_profile_definitions = [
        {
            "key": "P0000_involved",
            "short_label": "P0000 impliqué",
            "label": "Opérations impliquant P0000",
        },
        {
            "key": "P9999_involved",
            "short_label": "P9999 impliqué",
            "label": "Opérations impliquant P9999",
        },
        {
            "key": "P0000_P9999_bridge",
            "short_label": "P0000 ↔ P9999",
            "label": "Opérations entre P0000 et P9999",
        },
    ]

    structural_operations_flow_definitions = [
        {
            "key": "professional_to_operator",
            "label": "Professionnel → compte opérateur",
        },
        {
            "key": "operator_to_professional",
            "label": "Compte opérateur → professionnel",
        },
        {
            "key": "operator_to_operator",
            "label": "Entre comptes opérateurs",
        },
        {
            "key": "user_to_technical_accounts",
            "label": "Particulier → compte technique",
        },
        {
            "key": "user_to_operator",
            "label": "Particulier → compte opérateur",
        },
        {
            "key": "operator_to_user",
            "label": "Compte opérateur → particulier",
        },
        {
            "key": "technical_account_to_operator",
            "label": "Compte technique → compte opérateur",
        },
    ]

    main_activity_flow_keys = {
        "U→P",
        "P→P",
        "P→U",
        "U→U",
    }

    main_inflow_destination_keys = {
        "T→U",
        "T→P",
        "T→T",
    }

    def empty_response():
        return {
            "daily": {
                "labels": [],
                "values": [],
                "activity_values": [],
                "inflow_values": [],
                "outflow_values": [],
                "non_economic_values": [],
                "amount_values": [],
                "activity_amount_values": [],
                "inflow_amount_values": [],
                "outflow_amount_values": [],
                "non_economic_amount_values": [],
                "payment_values": [],
                "conversion_values": [],
                "reconversion_values": [],
                "regularization_values": [],
                "payment_amount_values": [],
                "conversion_amount_values": [],
                "reconversion_amount_values": [],
                "regularization_amount_values": [],
            },

            # Contrats historiques conservés
            "weekly": {"labels": [], "values": []},
            "hourly": {"labels": [], "values": []},
            "weekday": {"labels": [], "values": []},
            "cumulative": {"labels": [], "values": []},

            # Activité économique — contrats consolidés
            "weekly_activity_flows": {
                "labels": [],
                "series": [
                    {
                        "key": definition["key"],
                        "short_label": definition["short_label"],
                        "label": definition["label"],
                        "count_values": [],
                        "amount_values": [],
                    }
                    for definition in weekly_activity_flow_definitions
                ],
            },
            "cumulative_activity": {
                "labels": [],
                "count_values": [],
                "amount_values": [],
            },
            "hourly_activity": {
                "labels": [f"{hour:02d}h" for hour in range(24)],
                "count_values": [0 for _ in range(24)],
                "amount_values": [0.0 for _ in range(24)],
            },
            "weekday_activity": {
                "labels": [
                    "Lundi", "Mardi", "Mercredi",
                    "Jeudi", "Vendredi", "Samedi", "Dimanche"
                ],
                "count_values": [0 for _ in range(7)],
                "amount_values": [0.0 for _ in range(7)],
            },

            # Alimentation / sorties — nouveaux contrats
            "circuit_monthly_flows": {
                "labels": [],
                "series": [
                    {
                        "key": definition["key"],
                        "short_label": definition["short_label"],
                        "label": definition["label"],
                        "count_values": [],
                        "amount_values": [],
                    }
                    for definition in monthly_circuit_flow_definitions
                ],
            },
            "circuit_monthly_inflow_destinations": {
                "labels": [],
                "series": [
                    {
                        "key": definition["key"],
                        "short_label": definition["short_label"],
                        "label": definition["label"],
                        "count_values": [],
                        "amount_values": [],
                    }
                    for definition in monthly_inflow_destination_definitions
                ],
            },
            "circuit_cumulative_flows": {
                "labels": [],
                "series": [
                    {
                        "key": definition["key"],
                        "short_label": definition["short_label"],
                        "label": definition["label"],
                        "count_values": [],
                        "amount_values": [],
                    }
                    for definition in monthly_circuit_flow_definitions
                ],
            },
            "circuit_cumulative_net_gap": {
                "labels": [],
                "amount_values": [],
            },
            "operations_monthly_families": {
                "labels": [],
                "series": [
                    {
                        "key": definition["key"],
                        "short_label": definition["short_label"],
                        "label": definition["label"],
                        "count_values": [],
                        "amount_values": [],
                    }
                    for definition in monthly_operations_family_definitions
                ],
            },
            "operations_monthly_operator_profiles": {
                "labels": [],
                "series": [
                    {
                        "key": definition["key"],
                        "short_label": definition["short_label"],
                        "label": definition["label"],
                        "count_values": [],
                        "amount_values": [],
                    }
                    for definition in monthly_operator_profile_definitions
                ],
            },
            "operations_structural_flow_distribution": {
                "labels": [
                    definition["label"]
                    for definition in structural_operations_flow_definitions
                ],
                "count_values": [
                    0 for _ in structural_operations_flow_definitions
                ],
                "amount_values": [
                    0.0 for _ in structural_operations_flow_definitions
                ],
            },
        }

    if not rows:
        return empty_response()

    parsed = []

    for row in rows:
        raw_date = str(row.get("date", "")).strip()
        amount = float(row.get("amount", 0) or 0)

        try:
            dt = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
        except Exception:
            continue

        classification = _classify_analytical_transaction(row)

        source = classification.get("source_family")
        target = classification.get("target_family")

        # Compatibilité défensive si une classification externe plus ancienne
        # ne fournit pas encore ces deux familles.
        if source is None or target is None:
            source = _actor_flow_family(row.get("from_label"))
            target = _actor_flow_family(row.get("to_label"))

        raw_flow = f"{source}→{target}"

        activity_flow_key = (
            raw_flow
            if raw_flow in main_activity_flow_keys
            else "atypical"
        )

        inflow_destination_key = (
            raw_flow
            if raw_flow in main_inflow_destination_keys
            else "atypical"
        )

        parsed.append({
            "dt": dt,
            "amount": amount,
            "classification": classification,
            "activity_flow_key": activity_flow_key,
            "inflow_destination_key": inflow_destination_key,

            # Conservés pour les analyses structurelles plus fines
            # des onglets Opérations associatives / techniques.
            "from_label": row.get("from_label"),
            "to_label": row.get("to_label"),
        })

    if not parsed:
        return empty_response()

    # ---------------------------------------------------------------------
    # 1. Graphe transversal quotidien
    # ---------------------------------------------------------------------

    daily_buckets = {}

    for row in parsed:
        day = row["dt"].date().isoformat()

        bucket = daily_buckets.setdefault(day, {
            "total": 0,
            "activity": 0,
            "inflows": 0,
            "outflows": 0,
            "operations": 0,
            "total_amount": 0.0,
            "activity_amount": 0.0,
            "inflows_amount": 0.0,
            "outflows_amount": 0.0,
            "operations_amount": 0.0,
        })

        bucket["total"] += 1
        bucket["total_amount"] += row["amount"]

        classification_bucket = row["classification"]["bucket"]
        if classification_bucket in {"activity", "inflows", "outflows", "operations"}:
            bucket[classification_bucket] += 1
            bucket[f"{classification_bucket}_amount"] += row["amount"]

    daily_labels = sorted(daily_buckets.keys())
    daily_values = [daily_buckets[day]["total"] for day in daily_labels]

    daily_activity_values = [daily_buckets[day]["activity"] for day in daily_labels]
    daily_inflow_values = [daily_buckets[day]["inflows"] for day in daily_labels]
    daily_outflow_values = [daily_buckets[day]["outflows"] for day in daily_labels]
    daily_non_economic_values = [daily_buckets[day]["operations"] for day in daily_labels]

    daily_amount_values = [daily_buckets[day]["total_amount"] for day in daily_labels]
    daily_activity_amount_values = [daily_buckets[day]["activity_amount"] for day in daily_labels]
    daily_inflow_amount_values = [daily_buckets[day]["inflows_amount"] for day in daily_labels]
    daily_outflow_amount_values = [daily_buckets[day]["outflows_amount"] for day in daily_labels]
    daily_non_economic_amount_values = [daily_buckets[day]["operations_amount"] for day in daily_labels]

    # ---------------------------------------------------------------------
    # 2. Activité économique
    # ---------------------------------------------------------------------

    activity_rows = [
        row for row in parsed
        if row["classification"]["is_activity"]
    ]

    weekly_buckets = {}
    weekly_flow_buckets = {}

    def empty_activity_flow_bucket():
        return {
            definition["key"]: {
                "count": 0,
                "amount": 0.0,
            }
            for definition in weekly_activity_flow_definitions
        }

    hourly_labels = [f"{hour:02d}h" for hour in range(24)]
    hourly_counts = {hour: 0 for hour in range(24)}
    hourly_amounts = {hour: 0.0 for hour in range(24)}

    weekday_labels = [
        "Lundi", "Mardi", "Mercredi",
        "Jeudi", "Vendredi", "Samedi", "Dimanche"
    ]
    weekday_counts = {i: 0 for i in range(7)}
    weekday_amounts = {i: 0.0 for i in range(7)}

    daily_activity_cumulative_buckets = {}

    # Un seul passage sur l'activité économique :
    # - moyenne hebdomadaire ;
    # - flux hebdomadaires détaillés ;
    # - répartition horaire ;
    # - répartition par jour de semaine ;
    # - cumul quotidien de l'activité.
    for row in activity_rows:
        amount = row["amount"]
        dt = row["dt"]

        iso_year, iso_week, _ = dt.isocalendar()
        week_key = f"{iso_year}-W{iso_week:02d}"

        weekly_bucket = weekly_buckets.get(week_key)
        if weekly_bucket is None:
            weekly_bucket = {"sum": 0.0, "count": 0}
            weekly_buckets[week_key] = weekly_bucket
        weekly_bucket["sum"] += amount
        weekly_bucket["count"] += 1

        weekly_flow_bucket = weekly_flow_buckets.get(week_key)
        if weekly_flow_bucket is None:
            weekly_flow_bucket = empty_activity_flow_bucket()
            weekly_flow_buckets[week_key] = weekly_flow_bucket

        flow_key = row["activity_flow_key"]
        weekly_flow_bucket[flow_key]["count"] += 1
        weekly_flow_bucket[flow_key]["amount"] += amount

        hour = dt.hour
        hourly_counts[hour] += 1
        hourly_amounts[hour] += amount

        weekday = dt.weekday()
        weekday_counts[weekday] += 1
        weekday_amounts[weekday] += amount

        day = dt.date().isoformat()
        daily_bucket = daily_activity_cumulative_buckets.get(day)
        if daily_bucket is None:
            daily_bucket = {
                "count": 0,
                "amount": 0.0,
            }
            daily_activity_cumulative_buckets[day] = daily_bucket

        daily_bucket["count"] += 1
        daily_bucket["amount"] += amount

    weekly_labels = sorted(weekly_buckets.keys())
    weekly_values = [
        weekly_buckets[key]["sum"] / weekly_buckets[key]["count"]
        if weekly_buckets[key]["count"] else 0.0
        for key in weekly_labels
    ]

    weekly_activity_flow_labels = sorted(weekly_flow_buckets.keys())
    weekly_activity_flow_series = []

    for definition in weekly_activity_flow_definitions:
        flow_key = definition["key"]
        weekly_activity_flow_series.append({
            "key": flow_key,
            "short_label": definition["short_label"],
            "label": definition["label"],
            "count_values": [
                weekly_flow_buckets[week][flow_key]["count"]
                for week in weekly_activity_flow_labels
            ],
            "amount_values": [
                weekly_flow_buckets[week][flow_key]["amount"]
                for week in weekly_activity_flow_labels
            ],
        })

    hourly_values = [hourly_counts[hour] for hour in range(24)]
    hourly_amount_values = [hourly_amounts[hour] for hour in range(24)]

    weekday_values = [weekday_counts[i] for i in range(7)]
    weekday_amount_values = [weekday_amounts[i] for i in range(7)]

    cumulative_labels = sorted(daily_activity_cumulative_buckets.keys())
    cumulative_values = []
    cumulative_count_values = []
    cumulative_amount_values = []

    running_count = 0
    running_amount = 0.0

    for day in cumulative_labels:
        running_count += daily_activity_cumulative_buckets[day]["count"]
        running_amount += daily_activity_cumulative_buckets[day]["amount"]

        cumulative_count_values.append(running_count)
        cumulative_amount_values.append(running_amount)
        cumulative_values.append(running_amount)

    # ---------------------------------------------------------------------
    # 3. Alimentation / sorties du circuit
    # ---------------------------------------------------------------------

    circuit_inflow_rows = [
        row for row in parsed
        if row["classification"]["bucket"] == "inflows"
    ]

    circuit_outflow_rows = [
        row for row in parsed
        if row["classification"]["bucket"] == "outflows"
    ]

    circuit_monthly_buckets = {}

    def empty_circuit_flow_bucket():
        return {
            definition["key"]: {
                "count": 0,
                "amount": 0.0,
            }
            for definition in monthly_circuit_flow_definitions
        }

    monthly_inflow_destination_buckets = {}

    def empty_inflow_destination_bucket():
        return {
            definition["key"]: {
                "count": 0,
                "amount": 0.0,
            }
            for definition in monthly_inflow_destination_definitions
        }

    # Un seul passage sur les alimentations :
    # - alimente la série mensuelle alimentations/sorties ;
    # - alimente la série des destinations mensuelles d'alimentation.
    for row in circuit_inflow_rows:
        month = row["dt"].strftime("%Y-%m")

        monthly_bucket = circuit_monthly_buckets.get(month)
        if monthly_bucket is None:
            monthly_bucket = empty_circuit_flow_bucket()
            circuit_monthly_buckets[month] = monthly_bucket
        monthly_bucket["inflows"]["count"] += 1
        monthly_bucket["inflows"]["amount"] += row["amount"]

        destination_bucket = monthly_inflow_destination_buckets.get(month)
        if destination_bucket is None:
            destination_bucket = empty_inflow_destination_bucket()
            monthly_inflow_destination_buckets[month] = destination_bucket

        destination_key = row["inflow_destination_key"]
        destination_bucket[destination_key]["count"] += 1
        destination_bucket[destination_key]["amount"] += row["amount"]

    for row in circuit_outflow_rows:
        month = row["dt"].strftime("%Y-%m")
        bucket = circuit_monthly_buckets.get(month)
        if bucket is None:
            bucket = empty_circuit_flow_bucket()
            circuit_monthly_buckets[month] = bucket
        bucket["outflows"]["count"] += 1
        bucket["outflows"]["amount"] += row["amount"]

    circuit_month_labels = sorted(circuit_monthly_buckets.keys())
    circuit_monthly_flow_series = []

    for definition in monthly_circuit_flow_definitions:
        key = definition["key"]
        circuit_monthly_flow_series.append({
            "key": key,
            "short_label": definition["short_label"],
            "label": definition["label"],
            "count_values": [
                circuit_monthly_buckets[month][key]["count"]
                for month in circuit_month_labels
            ],
            "amount_values": [
                circuit_monthly_buckets[month][key]["amount"]
                for month in circuit_month_labels
            ],
        })

    circuit_inflow_destination_month_labels = sorted(
        monthly_inflow_destination_buckets.keys()
    )

    circuit_monthly_inflow_destination_series = []

    for definition in monthly_inflow_destination_definitions:
        key = definition["key"]
        circuit_monthly_inflow_destination_series.append({
            "key": key,
            "short_label": definition["short_label"],
            "label": definition["label"],
            "count_values": [
                monthly_inflow_destination_buckets[month][key]["count"]
                for month in circuit_inflow_destination_month_labels
            ],
            "amount_values": [
                monthly_inflow_destination_buckets[month][key]["amount"]
                for month in circuit_inflow_destination_month_labels
            ],
        })

    circuit_cumulative_flow_series = [
        {
            "key": definition["key"],
            "short_label": definition["short_label"],
            "label": definition["label"],
            "count_values": [],
            "amount_values": [],
        }
        for definition in monthly_circuit_flow_definitions
    ]

    cumulative_series_by_key = {
        series["key"]: series
        for series in circuit_cumulative_flow_series
    }

    running_circuit_counts = {"inflows": 0, "outflows": 0}
    running_circuit_amounts = {"inflows": 0.0, "outflows": 0.0}
    circuit_net_gap_amount_values = []

    for month in circuit_month_labels:
        for key in ("inflows", "outflows"):
            running_circuit_counts[key] += circuit_monthly_buckets[month][key]["count"]
            running_circuit_amounts[key] += circuit_monthly_buckets[month][key]["amount"]

            cumulative_series_by_key[key]["count_values"].append(
                running_circuit_counts[key]
            )
            cumulative_series_by_key[key]["amount_values"].append(
                running_circuit_amounts[key]
            )

        circuit_net_gap_amount_values.append(
            running_circuit_amounts["inflows"] - running_circuit_amounts["outflows"]
        )


    # ---------------------------------------------------------------------
    # 4. Opérations associatives / techniques
    # ---------------------------------------------------------------------

    operations_rows = [
        row for row in parsed
        if row["classification"]["bucket"] == "operations"
    ]

    monthly_operations_family_buckets = {}

    def empty_operations_family_bucket():
        return {
            definition["key"]: {
                "count": 0,
                "amount": 0.0,
            }
            for definition in monthly_operations_family_definitions
        }

    monthly_operator_profile_buckets = {}

    def empty_operator_profile_bucket():
        return {
            definition["key"]: {
                "count": 0,
                "amount": 0.0,
            }
            for definition in monthly_operator_profile_definitions
        }

    structural_flow_totals = {
        definition["key"]: {
            "count": 0,
            "amount": 0.0,
        }
        for definition in structural_operations_flow_definitions
    }

    # Un seul passage sur les opérations :
    # - familles mensuelles ;
    # - profils de comptes opérateurs ;
    # - distribution structurelle fonctionnelle.
    for row in operations_rows:
        month = row["dt"].strftime("%Y-%m")
        family_key = _operations_family_key(row["classification"])

        if family_key in {"operator_accounts", "user_to_technical_accounts"}:
            family_bucket = monthly_operations_family_buckets.get(month)
            if family_bucket is None:
                family_bucket = empty_operations_family_bucket()
                monthly_operations_family_buckets[month] = family_bucket
            family_bucket[family_key]["count"] += 1
            family_bucket[family_key]["amount"] += row["amount"]

        if family_key == "operator_accounts":
            profile_key = _operator_operation_profile({
                "from_label": row.get("from_label"),
                "to_label": row.get("to_label"),
            })

            if profile_key in {
                "P0000_involved",
                "P9999_involved",
                "P0000_P9999_bridge",
            }:
                profile_bucket = monthly_operator_profile_buckets.get(month)
                if profile_bucket is None:
                    profile_bucket = empty_operator_profile_bucket()
                    monthly_operator_profile_buckets[month] = profile_bucket
                profile_bucket[profile_key]["count"] += 1
                profile_bucket[profile_key]["amount"] += row["amount"]

        flow_key = _operations_functional_flow_key({
            "from_label": row.get("from_label"),
            "to_label": row.get("to_label"),
        })

        if flow_key in structural_flow_totals:
            structural_flow_totals[flow_key]["count"] += 1
            structural_flow_totals[flow_key]["amount"] += row["amount"]

    operations_month_labels = sorted(monthly_operations_family_buckets.keys())
    operations_monthly_family_series = []

    for definition in monthly_operations_family_definitions:
        key = definition["key"]
        operations_monthly_family_series.append({
            "key": key,
            "short_label": definition["short_label"],
            "label": definition["label"],
            "count_values": [
                monthly_operations_family_buckets[month][key]["count"]
                for month in operations_month_labels
            ],
            "amount_values": [
                monthly_operations_family_buckets[month][key]["amount"]
                for month in operations_month_labels
            ],
        })

    operator_profile_month_labels = sorted(monthly_operator_profile_buckets.keys())
    operations_monthly_operator_profile_series = []

    for definition in monthly_operator_profile_definitions:
        key = definition["key"]
        operations_monthly_operator_profile_series.append({
            "key": key,
            "short_label": definition["short_label"],
            "label": definition["label"],
            "count_values": [
                monthly_operator_profile_buckets[month][key]["count"]
                for month in operator_profile_month_labels
            ],
            "amount_values": [
                monthly_operator_profile_buckets[month][key]["amount"]
                for month in operator_profile_month_labels
            ],
        })

    operations_structural_flow_labels = [
        definition["label"]
        for definition in structural_operations_flow_definitions
    ]
    operations_structural_flow_count_values = [
        structural_flow_totals[definition["key"]]["count"]
        for definition in structural_operations_flow_definitions
    ]
    operations_structural_flow_amount_values = [
        structural_flow_totals[definition["key"]]["amount"]
        for definition in structural_operations_flow_definitions
    ]
    return {
        "daily": {
            "labels": daily_labels,
            "values": daily_values,

            "activity_values": daily_activity_values,
            "inflow_values": daily_inflow_values,
            "outflow_values": daily_outflow_values,
            "non_economic_values": daily_non_economic_values,

            "amount_values": daily_amount_values,

            "activity_amount_values": daily_activity_amount_values,
            "inflow_amount_values": daily_inflow_amount_values,
            "outflow_amount_values": daily_outflow_amount_values,
            "non_economic_amount_values": daily_non_economic_amount_values,

            "payment_values": daily_activity_values,
            "conversion_values": daily_inflow_values,
            "reconversion_values": daily_outflow_values,
            "regularization_values": daily_non_economic_values,

            "payment_amount_values": daily_activity_amount_values,
            "conversion_amount_values": daily_inflow_amount_values,
            "reconversion_amount_values": daily_outflow_amount_values,
            "regularization_amount_values": daily_non_economic_amount_values,
        },

        # Contrats historiques conservés
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

        # Activité économique
        "weekly_activity_flows": {
            "labels": weekly_activity_flow_labels,
            "series": weekly_activity_flow_series,
        },
        "hourly_activity": {
            "labels": hourly_labels,
            "count_values": hourly_values,
            "amount_values": hourly_amount_values,
        },
        "weekday_activity": {
            "labels": weekday_labels,
            "count_values": weekday_values,
            "amount_values": weekday_amount_values,
        },
        "cumulative_activity": {
            "labels": cumulative_labels,
            "count_values": cumulative_count_values,
            "amount_values": cumulative_amount_values,
        },

        # Alimentation / sorties
        "circuit_monthly_flows": {
            "labels": circuit_month_labels,
            "series": circuit_monthly_flow_series,
        },
        "circuit_monthly_inflow_destinations": {
            "labels": circuit_inflow_destination_month_labels,
            "series": circuit_monthly_inflow_destination_series,
        },
        "circuit_cumulative_flows": {
            "labels": circuit_month_labels,
            "series": circuit_cumulative_flow_series,
        },
        "circuit_cumulative_net_gap": {
            "labels": circuit_month_labels,
            "amount_values": circuit_net_gap_amount_values,
        },
        "operations_monthly_families": {
            "labels": operations_month_labels,
            "series": operations_monthly_family_series,
        },
        "operations_monthly_operator_profiles": {
            "labels": operator_profile_month_labels,
            "series": operations_monthly_operator_profile_series,
        },
        "operations_structural_flow_distribution": {
            "labels": operations_structural_flow_labels,
            "count_values": operations_structural_flow_count_values,
            "amount_values": operations_structural_flow_amount_values,
        },
    }