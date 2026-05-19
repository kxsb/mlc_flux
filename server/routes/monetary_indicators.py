from datetime import date, timedelta
from bisect import bisect_right

from flask import Blueprint, jsonify, request

from server.analytics import (
    _actor_flow_family,
    _classify_analytical_transaction,
    compute_global_stats,
    compute_stats_charts,
    fetch_transactions,
)
from server.database import get_connection
from server.services.monetary_holdings_analytics import (
    get_pilotage_holdings_summary,
    get_pilotage_holdings_timeseries,
)
from server.services.pilotage_yearly_cache import (
    PILOTAGE_LM3_YEARLY_SERIES_KEY,
    PILOTAGE_REUSE_YEARLY_SERIES_KEY,
    load_pilotage_yearly_cache_items,
)


monetary_indicators_bp = Blueprint("monetary_indicators", __name__)


MONETARY_INDICATOR_COLUMNS = """
    year,
    gonettes_num_circulation,
    gonettes_paper_circulation,
    gonettes_total_circulation,
    fonds_garantie_num,
    fonds_garantie_paper,
    ecart_num,
    ecart_paper,
    fetched_at,
    source
"""


def _row_to_dict(row):
    if row is None:
        return None

    return {
        "year": row["year"],
        "gonettes_num_circulation": row["gonettes_num_circulation"],
        "gonettes_paper_circulation": row["gonettes_paper_circulation"],
        "gonettes_total_circulation": row["gonettes_total_circulation"],
        "fonds_garantie_num": row["fonds_garantie_num"],
        "fonds_garantie_paper": row["fonds_garantie_paper"],
        "ecart_num": row["ecart_num"],
        "ecart_paper": row["ecart_paper"],
        "fetched_at": row["fetched_at"],
        "source": row["source"],
    }


@monetary_indicators_bp.route("/api/monetary-indicators/yearly", methods=["GET"])
def monetary_indicators_yearly():
    conn = get_connection()
    cur = conn.cursor()

    rows = cur.execute(f"""
        SELECT
            {MONETARY_INDICATOR_COLUMNS}
        FROM odoo_monetary_indicators_yearly
        ORDER BY year ASC
    """).fetchall()

    conn.close()

    return jsonify({
        "status": "ok",
        "items": [_row_to_dict(row) for row in rows],
    })


@monetary_indicators_bp.route("/api/monetary-indicators/latest", methods=["GET"])
def monetary_indicators_latest():
    conn = get_connection()
    cur = conn.cursor()

    row = cur.execute(f"""
        SELECT
            {MONETARY_INDICATOR_COLUMNS}
        FROM odoo_monetary_indicators_yearly
        ORDER BY year DESC
        LIMIT 1
    """).fetchone()

    conn.close()

    if row is None:
        return jsonify({
            "status": "empty",
            "error": "Aucun indicateur monétaire Odoo disponible.",
        }), 404

    return jsonify({
        "status": "ok",
        "item": _row_to_dict(row),
    })



DAILY_MONETARY_COLUMNS = """
    snapshot_date,
    year,
    month,
    day,
    gonettes_num_circulation,
    gonettes_paper_circulation,
    gonettes_total_circulation,
    fonds_garantie_num,
    fonds_garantie_paper,
    ecart_num,
    ecart_paper,
    fetched_at,
    source
"""


def _daily_row_to_dict(row):
    if row is None:
        return None

    return {
        "snapshot_date": row["snapshot_date"],
        "year": row["year"],
        "month": row["month"],
        "day": row["day"],
        "gonettes_num_circulation": row["gonettes_num_circulation"],
        "gonettes_paper_circulation": row["gonettes_paper_circulation"],
        "gonettes_total_circulation": row["gonettes_total_circulation"],
        "fonds_garantie_num": row["fonds_garantie_num"],
        "fonds_garantie_paper": row["fonds_garantie_paper"],
        "ecart_num": row["ecart_num"],
        "ecart_paper": row["ecart_paper"],
        "fetched_at": row["fetched_at"],
        "source": row["source"],
    }


def _parse_optional_iso_date(raw_value, field_name):
    if raw_value in (None, ""):
        return None

    try:
        return date.fromisoformat(raw_value)
    except ValueError:
        raise ValueError(
            f"Paramètre '{field_name}' invalide. Format attendu : YYYY-MM-DD."
        )


def _get_daily_bounds(cur):
    row = cur.execute("""
        SELECT
            MIN(snapshot_date) AS min_date,
            MAX(snapshot_date) AS max_date
        FROM odoo_monetary_indicators_daily
    """).fetchone()

    if row is None or row["min_date"] is None or row["max_date"] is None:
        return None

    return {
        "min_date": row["min_date"],
        "max_date": row["max_date"],
    }


def _resolve_period(cur, requested_start, requested_end):
    bounds = _get_daily_bounds(cur)

    if bounds is None:
        return {
            "bounds": None,
            "requested_start": requested_start,
            "requested_end": requested_end,
            "effective_start": None,
            "effective_end": None,
        }

    min_date = date.fromisoformat(bounds["min_date"])
    max_date = date.fromisoformat(bounds["max_date"])

    start = requested_start or min_date
    end = requested_end or max_date

    if start > end:
        raise ValueError(
            "Période invalide : la date de début est postérieure à la date de fin."
        )

    effective_start = max(start, min_date)
    effective_end = min(end, max_date)

    if effective_start > effective_end:
        effective_start = None
        effective_end = None

    return {
        "bounds": bounds,
        "requested_start": start.isoformat(),
        "requested_end": end.isoformat(),
        "effective_start": effective_start.isoformat() if effective_start else None,
        "effective_end": effective_end.isoformat() if effective_end else None,
    }


def _zero_opening_snapshot(day_before_start):
    """
    Snapshot synthétique utilisé uniquement lorsque la période commence
    au tout premier jour disponible de la série daily.
    Dans notre backfill, le stock d'ouverture au 2023-12-31 a été audité à zéro.
    """
    return {
        "snapshot_date": day_before_start.isoformat(),
        "year": day_before_start.year,
        "month": day_before_start.month,
        "day": day_before_start.day,
        "gonettes_num_circulation": 0.0,
        "gonettes_paper_circulation": 0.0,
        "gonettes_total_circulation": 0.0,
        "fonds_garantie_num": 0.0,
        "fonds_garantie_paper": 0.0,
        "ecart_num": 0.0,
        "ecart_paper": 0.0,
        "fetched_at": None,
        "source": "synthetic_zero_opening_before_first_daily_snapshot",
        "is_synthetic": True,
    }


def _compute_variation(closing, opening, key):
    if closing is None or opening is None:
        return None

    # Le point d'ouverture synthétique à zéro sert à reconstruire
    # techniquement la série quotidienne Odoo, mais ne doit pas être
    # interprété comme un vrai stock historique connu.
    if opening.get("is_synthetic"):
        return None

    return round(float(closing[key] or 0.0) - float(opening[key] or 0.0), 2)


def _compute_variation_rate(closing, opening, key):
    if closing is None or opening is None:
        return None

    opening_value = float(opening[key] or 0.0)
    if opening_value == 0:
        return None

    variation = _compute_variation(closing, opening, key)
    if variation is None:
        return None

    return round((variation / opening_value) * 100, 4)


@monetary_indicators_bp.route("/api/monetary-indicators/daily", methods=["GET"])
def monetary_indicators_daily():
    try:
        requested_start = _parse_optional_iso_date(request.args.get("start"), "start")
        requested_end = _parse_optional_iso_date(request.args.get("end"), "end")
    except ValueError as exc:
        return jsonify({"status": "error", "error": str(exc)}), 400

    conn = get_connection()
    cur = conn.cursor()

    try:
        period = _resolve_period(cur, requested_start, requested_end)
    except ValueError as exc:
        conn.close()
        return jsonify({"status": "error", "error": str(exc)}), 400

    if period["effective_start"] is None or period["effective_end"] is None:
        conn.close()
        return jsonify({
            "status": "ok",
            "bounds": period["bounds"],
            "requested_period": {
                "start": period["requested_start"],
                "end": period["requested_end"],
            },
            "effective_period": None,
            "items": [],
        })

    rows = cur.execute(f"""
        SELECT
            {DAILY_MONETARY_COLUMNS}
        FROM odoo_monetary_indicators_daily
        WHERE snapshot_date BETWEEN ? AND ?
        ORDER BY snapshot_date ASC
    """, (
        period["effective_start"],
        period["effective_end"],
    )).fetchall()

    conn.close()

    return jsonify({
        "status": "ok",
        "bounds": period["bounds"],
        "requested_period": {
            "start": period["requested_start"],
            "end": period["requested_end"],
        },
        "effective_period": {
            "start": period["effective_start"],
            "end": period["effective_end"],
        },
        "items": [_daily_row_to_dict(row) for row in rows],
    })


@monetary_indicators_bp.route("/api/monetary-indicators/period-summary", methods=["GET"])
def monetary_indicators_period_summary():
    try:
        requested_start = _parse_optional_iso_date(request.args.get("start"), "start")
        requested_end = _parse_optional_iso_date(request.args.get("end"), "end")
    except ValueError as exc:
        return jsonify({"status": "error", "error": str(exc)}), 400

    conn = get_connection()
    cur = conn.cursor()

    try:
        period = _resolve_period(cur, requested_start, requested_end)
    except ValueError as exc:
        conn.close()
        return jsonify({"status": "error", "error": str(exc)}), 400

    if period["effective_start"] is None or period["effective_end"] is None:
        conn.close()
        return jsonify({
            "status": "ok",
            "bounds": period["bounds"],
            "requested_period": {
                "start": period["requested_start"],
                "end": period["requested_end"],
            },
            "effective_period": None,
            "opening_snapshot": None,
            "closing_snapshot": None,
            "period_metrics": None,
        })

    effective_start = date.fromisoformat(period["effective_start"])
    effective_end = date.fromisoformat(period["effective_end"])
    opening_reference_date = effective_start - timedelta(days=1)

    opening_row = cur.execute(f"""
        SELECT
            {DAILY_MONETARY_COLUMNS}
        FROM odoo_monetary_indicators_daily
        WHERE snapshot_date < ?
        ORDER BY snapshot_date DESC
        LIMIT 1
    """, (period["effective_start"],)).fetchone()

    if opening_row is not None:
        opening_snapshot = _daily_row_to_dict(opening_row)
        opening_snapshot["is_synthetic"] = False
    else:
        opening_snapshot = _zero_opening_snapshot(opening_reference_date)

    closing_row = cur.execute(f"""
        SELECT
            {DAILY_MONETARY_COLUMNS}
        FROM odoo_monetary_indicators_daily
        WHERE snapshot_date <= ?
        ORDER BY snapshot_date DESC
        LIMIT 1
    """, (period["effective_end"],)).fetchone()

    closing_snapshot = _daily_row_to_dict(closing_row)
    if closing_snapshot is not None:
        closing_snapshot["is_synthetic"] = False

    averages = cur.execute("""
        SELECT
            COUNT(*) AS day_count,
            AVG(gonettes_num_circulation) AS avg_num,
            AVG(gonettes_paper_circulation) AS avg_paper,
            AVG(gonettes_total_circulation) AS avg_total,
            AVG(fonds_garantie_num) AS avg_fdg_num,
            AVG(fonds_garantie_paper) AS avg_fdg_paper
        FROM odoo_monetary_indicators_daily
        WHERE snapshot_date BETWEEN ? AND ?
    """, (
        period["effective_start"],
        period["effective_end"],
    )).fetchone()

    conn.close()

    period_metrics = {
        "day_count": averages["day_count"],
        "average_gonettes_num_circulation": round(float(averages["avg_num"] or 0.0), 2),
        "average_gonettes_paper_circulation": round(float(averages["avg_paper"] or 0.0), 2),
        "average_gonettes_total_circulation": round(float(averages["avg_total"] or 0.0), 2),
        "average_fonds_garantie_num": round(float(averages["avg_fdg_num"] or 0.0), 2),
        "average_fonds_garantie_paper": round(float(averages["avg_fdg_paper"] or 0.0), 2),

        "variation_gonettes_num_circulation": _compute_variation(
            closing_snapshot,
            opening_snapshot,
            "gonettes_num_circulation",
        ),
        "variation_gonettes_paper_circulation": _compute_variation(
            closing_snapshot,
            opening_snapshot,
            "gonettes_paper_circulation",
        ),
        "variation_gonettes_total_circulation": _compute_variation(
            closing_snapshot,
            opening_snapshot,
            "gonettes_total_circulation",
        ),

        "variation_rate_gonettes_num_circulation": _compute_variation_rate(
            closing_snapshot,
            opening_snapshot,
            "gonettes_num_circulation",
        ),
        "variation_rate_gonettes_paper_circulation": _compute_variation_rate(
            closing_snapshot,
            opening_snapshot,
            "gonettes_paper_circulation",
        ),
        "variation_rate_gonettes_total_circulation": _compute_variation_rate(
            closing_snapshot,
            opening_snapshot,
            "gonettes_total_circulation",
        ),
    }

    return jsonify({
        "status": "ok",
        "bounds": period["bounds"],
        "requested_period": {
            "start": period["requested_start"],
            "end": period["requested_end"],
        },
        "effective_period": {
            "start": period["effective_start"],
            "end": period["effective_end"],
        },
        "semantics": {
            "opening_snapshot": "Stock observé la veille du début de période.",
            "closing_snapshot": "Stock observé au dernier jour disponible de la période.",
            "period_metrics": "Indicateurs calculés sur l'ensemble de la période effective.",
        },
        "opening_snapshot": opening_snapshot,
        "closing_snapshot": closing_snapshot,
        "period_metrics": period_metrics,
    })



def _money2(value):
    return round(float(value or 0.0), 2)


def _ratio(value, base, digits=6):
    numerator = float(value or 0.0)
    denominator = float(base or 0.0)

    if denominator == 0:
        return None

    return round(numerator / denominator, digits)


def _annualized_ratio(period_ratio, day_count, digits=6):
    if period_ratio is None:
        return None

    days = int(day_count or 0)
    if days <= 0:
        return None

    return round(float(period_ratio) * 365 / days, digits)


def _internal_multiplier_from_propensity(propensity, digits=6):
    """
    Multiplicateur interne estimé dérivé d'une propension pondérée
    de réemploi interne :

        k = 1 / (1 - c)

    où c est bornée en amont entre 0 et 1 par construction.
    """
    if propensity is None:
        return None

    value = float(propensity)

    if value >= 1:
        return None

    return round(1 / (1 - value), digits)


def _internal_reuse_actor_family(label):
    family = _actor_flow_family(label)
    return family if family in {"P", "U"} else "?"


def _summarize_internal_reuse_group(group):
    """
    Résume la capacité de réemploi d'un groupe d'acteurs receveurs.

    Principe :
    - recettes internes = volumes économiques reçus ;
    - dépenses internes = volumes économiques émis ;
    - réemploi borné acteur par acteur :
        min(recettes, dépenses)
    - propension pondérée :
        somme(réemploi borné) / somme(recettes)
    """
    received_volume = sum(
        float(actor["received_volume"] or 0.0)
        for actor in group
    )
    emitted_volume = sum(
        float(actor["emitted_volume"] or 0.0)
        for actor in group
    )
    reused_capped_volume = sum(
        min(
            float(actor["received_volume"] or 0.0),
            float(actor["emitted_volume"] or 0.0),
        )
        for actor in group
    )

    weighted_internal_reuse_propensity = _ratio(
        reused_capped_volume,
        received_volume,
    )

    internal_multiplier_estimated = _internal_multiplier_from_propensity(
        weighted_internal_reuse_propensity
    )

    redespent_actor_count = sum(
        1 for actor in group
        if float(actor["emitted_volume"] or 0.0) > 0
    )

    over_100_actor_count = sum(
        1 for actor in group
        if (
            float(actor["received_volume"] or 0.0) > 0
            and float(actor["emitted_volume"] or 0.0)
            > float(actor["received_volume"] or 0.0)
        )
    )

    over_100_receipts_volume = sum(
        float(actor["received_volume"] or 0.0)
        for actor in group
        if (
            float(actor["received_volume"] or 0.0) > 0
            and float(actor["emitted_volume"] or 0.0)
            > float(actor["received_volume"] or 0.0)
        )
    )

    actor_count = len(group)

    return {
        "actor_count": actor_count,

        "received_volume": _money2(received_volume),
        "emitted_volume": _money2(emitted_volume),
        "reused_capped_volume": _money2(reused_capped_volume),

        "weighted_internal_reuse_propensity": (
            weighted_internal_reuse_propensity
        ),
        "internal_multiplier_estimated": internal_multiplier_estimated,

        "redespent_actor_count": redespent_actor_count,
        "redespent_actor_rate": _ratio(
            redespent_actor_count,
            actor_count,
        ),

        "over_100_actor_count": over_100_actor_count,
        "over_100_actor_rate": _ratio(
            over_100_actor_count,
            actor_count,
        ),
        "over_100_receipts_volume": _money2(
            over_100_receipts_volume
        ),
        "over_100_receipts_share": _ratio(
            over_100_receipts_volume,
            received_volume,
        ),
    }


def _compute_internal_reuse_metrics(rows):
    """
    Calcule les métriques de réemploi interne sur le périmètre
    de l'activité économique déjà consolidé dans MLCFlux.

    Le calcul réutilise _classify_analytical_transaction(row),
    garantissant une cohérence stricte avec les autres vues de l'application.
    """
    actors = {}
    activity_transaction_count = 0
    economic_activity_volume = 0.0

    raw_dates = [
        str(row.get("date") or "")[:10]
        for row in rows
        if row.get("date")
    ]

    for row in rows:
        classification = _classify_analytical_transaction(row)

        if not classification["is_activity"]:
            continue

        activity_transaction_count += 1

        amount = float(row.get("amount") or 0.0)
        economic_activity_volume += amount

        from_label = str(row.get("from_label") or "").strip()
        to_label = str(row.get("to_label") or "").strip()

        if from_label:
            actor = actors.setdefault(from_label, {
                "label": from_label,
                "family": _internal_reuse_actor_family(from_label),
                "received_volume": 0.0,
                "emitted_volume": 0.0,
            })
            actor["emitted_volume"] += amount

        if to_label:
            actor = actors.setdefault(to_label, {
                "label": to_label,
                "family": _internal_reuse_actor_family(to_label),
                "received_volume": 0.0,
                "emitted_volume": 0.0,
            })
            actor["received_volume"] += amount

    receivers = [
        actor for actor in actors.values()
        if float(actor["received_volume"] or 0.0) > 0
    ]

    professionals = [
        actor for actor in receivers
        if actor["family"] == "P"
    ]

    users = [
        actor for actor in receivers
        if actor["family"] == "U"
    ]

    return {
        "period_start": min(raw_dates) if raw_dates else None,
        "period_end": max(raw_dates) if raw_dates else None,
        "raw_transaction_count": len(rows),
        "economic_activity_transaction_count": activity_transaction_count,
        "economic_activity_volume": _money2(economic_activity_volume),

        "global": _summarize_internal_reuse_group(receivers),
        "professionals": _summarize_internal_reuse_group(professionals),
        "users": _summarize_internal_reuse_group(users),
    }


def _lm3_actor_family(label):
    family = _actor_flow_family(label)
    return family if family in {"A", "C", "P", "U"} else "?"


def _is_lm3_conversion_row(row):
    """
    Injection monétaire externe vers la communauté monétaire.

    Le LM3 reprend ici la classification analytique centrale de MLCFlux :
    une injection est une transaction classée dans le bucket ``inflows``.

    Cette logique évite de dupliquer une taxonomie d'acteurs devenue fragile
    après la refonte des comptes techniques en ``T_*``.
    """
    return _classify_analytical_transaction(row).get("bucket") == "inflows"


def _compute_lm3_metrics(rows):
    """
    Calcule un LM3 annuel estimé à partir des transactions MLCFlux.

    Méthode :
    - P1 : acteurs ayant reçu une conversion / alimentation A/C -> P/U ;
    - P2 : acteurs atteints par les paiements économiques de P1 ;
    - P3 : acteurs atteints par les paiements économiques propagés de P2 ;
    - propension de réemploi individuelle = dépenses / recettes économiques,
      bornée à 1 ;
    - LM3 = 1 + gain de vague 2 + gain de vague 3.

    Cette implémentation reproduit le prototype LM3-001 validé.
    """
    raw_dates = sorted(
        str(row.get("date") or "")[:10]
        for row in rows
        if row.get("date")
    )

    conversions = [
        row for row in rows
        if _is_lm3_conversion_row(row)
    ]

    activity_rows = [
        row for row in rows
        if _classify_analytical_transaction(row)["is_activity"]
    ]

    conversion_volume = sum(
        float(row.get("amount") or 0.0)
        for row in conversions
    )

    p1_conversion_actors = {
        str(row.get("to_label") or "").strip()
        for row in conversions
        if str(row.get("to_label") or "").strip()
    }

    receipts = {}
    spending = {}
    edges = {}

    def _increment(mapping, key, amount):
        mapping[key] = float(mapping.get(key, 0.0)) + float(amount or 0.0)

    def _increment_edge(sender, receiver, amount):
        sender_edges = edges.setdefault(sender, {})
        sender_edges[receiver] = (
            float(sender_edges.get(receiver, 0.0))
            + float(amount or 0.0)
        )

    for row in activity_rows:
        sender = str(row.get("from_label") or "").strip()
        receiver = str(row.get("to_label") or "").strip()
        amount = float(row.get("amount") or 0.0)

        if amount <= 0:
            continue

        if sender:
            _increment(spending, sender, amount)

        if receiver:
            _increment(receipts, receiver, amount)

        if sender and receiver:
            _increment_edge(sender, receiver, amount)

    all_actors = set(receipts) | set(spending)
    propensity = {}

    for actor in all_actors:
        received = float(receipts.get(actor, 0.0))
        spent = float(spending.get(actor, 0.0))

        if received <= 0:
            propensity[actor] = 0.0
        else:
            propensity[actor] = min(spent / received, 1.0)

    p1_spending_actors = {
        actor for actor in p1_conversion_actors
        if float(spending.get(actor, 0.0)) > 0
    }

    p1_total_spending = sum(
        float(spending.get(actor, 0.0))
        for actor in p1_spending_actors
    )

    p1_weights = {}

    if p1_total_spending > 0:
        p1_weights = {
            actor: float(spending.get(actor, 0.0)) / p1_total_spending
            for actor in p1_spending_actors
        }

    p2_weights = {}

    for actor, actor_weight in p1_weights.items():
        actor_spending = float(spending.get(actor, 0.0))

        if actor_spending <= 0:
            continue

        for partner, amount in edges.get(actor, {}).items():
            share = float(amount or 0.0) / actor_spending
            p2_weights[partner] = (
                float(p2_weights.get(partner, 0.0))
                + actor_weight * share
            )

    wave_2 = sum(
        float(weight or 0.0) * float(propensity.get(actor, 0.0))
        for actor, weight in p2_weights.items()
    )

    p2_weight_mass = sum(float(weight or 0.0) for weight in p2_weights.values())
    p2_effective_propensity = _ratio(wave_2, p2_weight_mass)

    p3_weights = {}

    for actor, actor_weight in p2_weights.items():
        actor_propensity = float(propensity.get(actor, 0.0))
        actor_spending = float(spending.get(actor, 0.0))

        if actor_propensity <= 0 or actor_spending <= 0:
            continue

        propagated_mass = float(actor_weight or 0.0) * actor_propensity

        for partner, amount in edges.get(actor, {}).items():
            share = float(amount or 0.0) / actor_spending
            p3_weights[partner] = (
                float(p3_weights.get(partner, 0.0))
                + propagated_mass * share
            )

    wave_3 = sum(
        float(weight or 0.0) * float(propensity.get(actor, 0.0))
        for actor, weight in p3_weights.items()
    )

    p3_weight_mass = sum(float(weight or 0.0) for weight in p3_weights.values())
    p3_effective_propensity = _ratio(wave_3, p3_weight_mass)

    wave_1 = 1.0
    lm3 = wave_1 + wave_2 + wave_3

    return {
        "period_start": raw_dates[0] if raw_dates else None,
        "period_end": raw_dates[-1] if raw_dates else None,

        "raw_transaction_count": len(rows),

        "conversion_transaction_count": len(conversions),
        "conversion_volume": _money2(conversion_volume),

        "economic_activity_transaction_count": len(activity_rows),
        "economic_activity_volume": _money2(
            sum(float(row.get("amount") or 0.0) for row in activity_rows)
        ),

        "p1_conversion_actor_count": len(p1_conversion_actors),
        "p1_spending_actor_count": len(p1_spending_actors),
        "p1_spending_volume": _money2(p1_total_spending),

        "p2_actor_count": len(p2_weights),
        "p3_actor_count": len(p3_weights),

        "wave_1": round(wave_1, 6),
        "wave_2": round(wave_2, 6),
        "wave_3": round(wave_3, 6),
        "lm3_estimated": round(lm3, 6),

        "p2_effective_propensity": p2_effective_propensity,
        "p3_effective_propensity": p3_effective_propensity,

        "p2_weight_mass": round(p2_weight_mass, 6),
        "p3_weight_mass": round(p3_weight_mass, 6),
    }


def _lm3_chain_date(row):
    return str(row.get("date") or "")


def _lm3_chain_amount(row):
    return float(row.get("amount") or 0.0)


def _compute_lm3_observed_chains(rows, limit=15):
    """
    Triplets transactionnels compatibles avec une propagation LM3 :
        alimentation -> P1 -> P2 -> P3

    Optimisation PERF1 :
    - on ne matérialise plus chaque paire tx1/tx2 compatible ;
    - pour chaque triplet potentiel P1 -> P2 -> P3, on compte
      les transactions P2 -> P3 postérieures par bisect_right ;
    - les compteurs et exemples restent sémantiquement identiques.
    """
    conversions = [
        row for row in rows
        if _is_lm3_conversion_row(row)
    ]

    activity_rows = [
        row for row in rows
        if _classify_analytical_transaction(row)["is_activity"]
    ]

    raw_dates = sorted(
        str(row.get("date") or "")[:10]
        for row in rows
        if row.get("date")
    )

    # ------------------------------------------------------------------
    # 1. Alimentations par P1
    # ------------------------------------------------------------------
    conversions_by_receiver = {}

    for row in conversions:
        receiver = str(row.get("to_label") or "").strip()
        if receiver:
            conversions_by_receiver.setdefault(receiver, []).append(row)

    conversion_dates_by_receiver = {}

    for actor, actor_rows in conversions_by_receiver.items():
        actor_rows.sort(key=_lm3_chain_date)
        conversion_dates_by_receiver[actor] = [
            _lm3_chain_date(row)
            for row in actor_rows
        ]

    # ------------------------------------------------------------------
    # 2. Paiements aval regroupés par P2 puis P3
    # ------------------------------------------------------------------
    downstream_by_sender_receiver = {}

    for row in activity_rows:
        sender = str(row.get("from_label") or "").strip()
        receiver = str(row.get("to_label") or "").strip()

        if not sender or not receiver:
            continue

        downstream_by_sender_receiver.setdefault(sender, {}).setdefault(
            receiver,
            [],
        ).append(row)

    downstream_dates_by_sender_receiver = {}

    for sender, receiver_map in downstream_by_sender_receiver.items():
        downstream_dates_by_sender_receiver[sender] = {}

        for receiver, tx_rows in receiver_map.items():
            tx_rows.sort(key=_lm3_chain_date)
            downstream_dates_by_sender_receiver[sender][receiver] = [
                _lm3_chain_date(row)
                for row in tx_rows
            ]

    # ------------------------------------------------------------------
    # 3. Paiements P1 -> P2 admissibles :
    #    P1 doit avoir été alimenté avant.
    # ------------------------------------------------------------------
    p1_p2_groups = {}
    candidate_p1_to_p2_count = 0

    for tx1 in activity_rows:
        p1 = str(tx1.get("from_label") or "").strip()
        p2 = str(tx1.get("to_label") or "").strip()
        tx1_date = _lm3_chain_date(tx1)

        if not p1 or not p2 or not tx1_date:
            continue

        conversion_dates = conversion_dates_by_receiver.get(p1, [])
        if not conversion_dates:
            continue

        conversion_index = bisect_right(conversion_dates, tx1_date) - 1
        if conversion_index < 0:
            continue

        prior_conversion = conversions_by_receiver[p1][conversion_index]
        candidate_p1_to_p2_count += 1

        group = p1_p2_groups.setdefault((p1, p2), {
            "p1": p1,
            "p2": p2,
            "tx1_entries": [],
        })

        group["tx1_entries"].append({
            "row": tx1,
            "prior_conversion": prior_conversion,
        })

    # ------------------------------------------------------------------
    # 4. Agrégation optimisée par triplet P1 -> P2 -> P3
    # ------------------------------------------------------------------
    items = []
    observed_configuration_count = 0

    for (p1, p2), group in p1_p2_groups.items():
        downstream_map = downstream_by_sender_receiver.get(p2, {})
        downstream_dates_map = downstream_dates_by_sender_receiver.get(p2, {})

        if not downstream_map:
            continue

        tx1_entries = sorted(
            group["tx1_entries"],
            key=lambda entry: _lm3_chain_date(entry["row"]),
        )

        for p3, tx2_rows in downstream_map.items():
            tx2_dates = downstream_dates_map[p3]

            configuration_count = 0
            p1_to_p2_transaction_count = 0
            earliest_compatible_tx1 = None
            first_example = None

            for entry in tx1_entries:
                tx1 = entry["row"]
                tx1_date = _lm3_chain_date(tx1)

                first_tx2_index = bisect_right(tx2_dates, tx1_date)
                compatible_tx2_count = len(tx2_dates) - first_tx2_index

                if compatible_tx2_count <= 0:
                    continue

                configuration_count += compatible_tx2_count
                p1_to_p2_transaction_count += 1

                if earliest_compatible_tx1 is None:
                    earliest_compatible_tx1 = tx1_date

                first_tx2 = tx2_rows[first_tx2_index]
                prior_conversion = entry["prior_conversion"]

                example = {
                    "conversion_date": _lm3_chain_date(prior_conversion)[:10],
                    "conversion_amount": _money2(_lm3_chain_amount(prior_conversion)),
                    "p1_to_p2_date": tx1_date[:10],
                    "p1_to_p2_amount": _money2(_lm3_chain_amount(tx1)),
                    "p2_to_p3_date": _lm3_chain_date(first_tx2)[:10],
                    "p2_to_p3_amount": _money2(_lm3_chain_amount(first_tx2)),
                }

                if first_example is None or (
                    example["p2_to_p3_date"],
                    example["p1_to_p2_date"],
                    example["conversion_date"],
                ) < (
                    first_example["p2_to_p3_date"],
                    first_example["p1_to_p2_date"],
                    first_example["conversion_date"],
                ):
                    first_example = example

            if configuration_count <= 0:
                continue

            observed_configuration_count += configuration_count

            # Union des transactions P2 -> P3 compatibles :
            # toutes celles postérieures au premier tx1 compatible.
            earliest_tx2_index = bisect_right(
                tx2_dates,
                earliest_compatible_tx1,
            )
            p2_to_p3_transaction_count = len(tx2_dates) - earliest_tx2_index

            items.append({
                "p1": p1,
                "p2": p2,
                "p3": p3,
                "configuration_count": configuration_count,
                "p1_to_p2_transaction_count": p1_to_p2_transaction_count,
                "p2_to_p3_transaction_count": p2_to_p3_transaction_count,
                "first_example": first_example,
            })

    items.sort(
        key=lambda item: (
            int(item["configuration_count"] or 0),
            int(item["p1_to_p2_transaction_count"] or 0),
            int(item["p2_to_p3_transaction_count"] or 0),
        ),
        reverse=True,
    )

    safe_limit = max(1, min(int(limit or 15), 50))

    return {
        "period_start": raw_dates[0] if raw_dates else None,
        "period_end": raw_dates[-1] if raw_dates else None,

        "raw_transaction_count": len(rows),
        "conversion_transaction_count": len(conversions),
        "economic_activity_transaction_count": len(activity_rows),
        "p1_conversion_actor_count": len(conversions_by_receiver),

        "candidate_p1_to_p2_count": candidate_p1_to_p2_count,
        "observed_configuration_count": observed_configuration_count,
        "distinct_triplet_count": len(items),

        "sort": "configuration_count_desc",
        "limit": safe_limit,
        "items": items[:safe_limit],
    }


def _build_pilotage_monetary_bundle(cur, period):
    """
    Reconstitue les mêmes repères de stock que period-summary,
    sans faire d'appel HTTP interne.
    """
    if period["effective_start"] is None or period["effective_end"] is None:
        return {
            "opening_snapshot": None,
            "closing_snapshot": None,
            "period_metrics": None,
        }

    effective_start = date.fromisoformat(period["effective_start"])
    opening_reference_date = effective_start - timedelta(days=1)

    opening_row = cur.execute(f"""
        SELECT
            {DAILY_MONETARY_COLUMNS}
        FROM odoo_monetary_indicators_daily
        WHERE snapshot_date < ?
        ORDER BY snapshot_date DESC
        LIMIT 1
    """, (period["effective_start"],)).fetchone()

    if opening_row is not None:
        opening_snapshot = _daily_row_to_dict(opening_row)
        opening_snapshot["is_synthetic"] = False
    else:
        opening_snapshot = _zero_opening_snapshot(opening_reference_date)

    closing_row = cur.execute(f"""
        SELECT
            {DAILY_MONETARY_COLUMNS}
        FROM odoo_monetary_indicators_daily
        WHERE snapshot_date <= ?
        ORDER BY snapshot_date DESC
        LIMIT 1
    """, (period["effective_end"],)).fetchone()

    closing_snapshot = _daily_row_to_dict(closing_row)
    if closing_snapshot is not None:
        closing_snapshot["is_synthetic"] = False

    averages = cur.execute("""
        SELECT
            COUNT(*) AS day_count,
            AVG(gonettes_num_circulation) AS avg_num,
            AVG(gonettes_paper_circulation) AS avg_paper,
            AVG(gonettes_total_circulation) AS avg_total,
            AVG(fonds_garantie_num) AS avg_fdg_num,
            AVG(fonds_garantie_paper) AS avg_fdg_paper
        FROM odoo_monetary_indicators_daily
        WHERE snapshot_date BETWEEN ? AND ?
    """, (
        period["effective_start"],
        period["effective_end"],
    )).fetchone()

    period_metrics = {
        "day_count": averages["day_count"],
        "average_gonettes_num_circulation": _money2(averages["avg_num"]),
        "average_gonettes_paper_circulation": _money2(averages["avg_paper"]),
        "average_gonettes_total_circulation": _money2(averages["avg_total"]),
        "average_fonds_garantie_num": _money2(averages["avg_fdg_num"]),
        "average_fonds_garantie_paper": _money2(averages["avg_fdg_paper"]),

        "variation_gonettes_num_circulation": _compute_variation(
            closing_snapshot,
            opening_snapshot,
            "gonettes_num_circulation",
        ),
        "variation_gonettes_paper_circulation": _compute_variation(
            closing_snapshot,
            opening_snapshot,
            "gonettes_paper_circulation",
        ),
        "variation_gonettes_total_circulation": _compute_variation(
            closing_snapshot,
            opening_snapshot,
            "gonettes_total_circulation",
        ),
    }

    return {
        "opening_snapshot": opening_snapshot,
        "closing_snapshot": closing_snapshot,
        "period_metrics": period_metrics,
    }




def _month_key_from_iso_day(raw_day):
    return str(raw_day or "")[:7]


def _aggregate_daily_activity_by_month(charts):
    """
    Recompose l'activité économique mensuelle depuis les séries quotidiennes
    déjà produites par compute_stats_charts().
    """
    daily = charts.get("daily") or {}
    labels = daily.get("labels") or []
    count_values = daily.get("activity_values") or []
    amount_values = daily.get("activity_amount_values") or []

    monthly = {}

    for index, day_label in enumerate(labels):
        month_key = _month_key_from_iso_day(day_label)
        if not month_key:
            continue

        bucket = monthly.setdefault(month_key, {
            "economic_activity_transaction_count": 0,
            "economic_activity_volume": 0.0,
        })

        bucket["economic_activity_transaction_count"] += int(
            count_values[index] if index < len(count_values) else 0
        )
        bucket["economic_activity_volume"] += float(
            amount_values[index] if index < len(amount_values) else 0.0
        )

    for bucket in monthly.values():
        bucket["economic_activity_volume"] = _money2(
            bucket["economic_activity_volume"]
        )

    return monthly


def _map_monthly_circuit_flow_series(charts, flow_key):
    """
    Transforme les séries mensuelles d'alimentation / sortie déjà produites
    par compute_stats_charts() en dictionnaire month_key -> valeurs.
    """
    payload = charts.get("circuit_monthly_flows") or {}
    labels = payload.get("labels") or []
    series = payload.get("series") or []

    selected_series = next(
        (item for item in series if item.get("key") == flow_key),
        None,
    )

    if selected_series is None:
        return {}

    count_values = selected_series.get("count_values") or []
    amount_values = selected_series.get("amount_values") or []

    monthly = {}

    for index, month_key in enumerate(labels):
        monthly[month_key] = {
            "transaction_count": int(
                count_values[index] if index < len(count_values) else 0
            ),
            "volume": _money2(
                amount_values[index] if index < len(amount_values) else 0.0
            ),
        }

    return monthly


def _build_pilotage_monthly_item(
    row,
    *,
    activity_by_month,
    inflows_by_month,
    outflows_by_month,
):
    month_key = row["month_key"]
    day_count = int(row["day_count"] or 0)

    activity = activity_by_month.get(month_key) or {}
    inflows = inflows_by_month.get(month_key) or {}
    outflows = outflows_by_month.get(month_key) or {}

    average_numeric_mass = _money2(row["avg_numeric_mass"])
    average_numeric_guarantee = _money2(row["avg_numeric_guarantee"])

    economic_activity_volume = _money2(
        activity.get("economic_activity_volume")
    )
    economic_activity_transaction_count = int(
        activity.get("economic_activity_transaction_count") or 0
    )

    inflow_volume = _money2(inflows.get("volume"))
    inflow_transaction_count = int(inflows.get("transaction_count") or 0)

    outflow_volume = _money2(outflows.get("volume"))
    outflow_transaction_count = int(outflows.get("transaction_count") or 0)

    net_cyclos_flow = _money2(inflow_volume - outflow_volume)

    economic_activity_intensity = _ratio(
        economic_activity_volume,
        average_numeric_mass,
    )
    inflow_pressure = _ratio(
        inflow_volume,
        average_numeric_mass,
    )
    outflow_pressure = _ratio(
        outflow_volume,
        average_numeric_mass,
    )
    net_flow_pressure = _ratio(
        net_cyclos_flow,
        average_numeric_mass,
    )
    outflow_inflow_ratio = _ratio(
        outflow_volume,
        inflow_volume,
    )
    net_inflow_retention_rate = _ratio(
        net_cyclos_flow,
        inflow_volume,
    )

    average_daily_outflow = (
        _money2(outflow_volume / day_count)
        if day_count > 0
        else None
    )

    apparent_reconversion_coverage_days = _ratio(
        average_numeric_guarantee,
        average_daily_outflow,
        digits=3,
    ) if average_daily_outflow not in (None, 0) else None

    apparent_reconversion_coverage_30_day_periods = (
        round(apparent_reconversion_coverage_days / 30, 3)
        if apparent_reconversion_coverage_days is not None
        else None
    )

    return {
        "month_key": month_key,
        "year": int(row["year"]),
        "month": int(row["month"]),
        "day_count": day_count,

        "average_numeric_mass": average_numeric_mass,
        "average_numeric_guarantee_fund": average_numeric_guarantee,

        "economic_activity_transaction_count": (
            economic_activity_transaction_count
        ),
        "economic_activity_volume": economic_activity_volume,

        "inflow_transaction_count": inflow_transaction_count,
        "inflow_volume": inflow_volume,

        "outflow_transaction_count": outflow_transaction_count,
        "outflow_volume": outflow_volume,

        "net_cyclos_flow": net_cyclos_flow,

        "economic_activity_intensity": economic_activity_intensity,
        "annualized_economic_activity_intensity_indicative": (
            _annualized_ratio(economic_activity_intensity, day_count)
        ),

        "inflow_pressure": inflow_pressure,
        "annualized_inflow_pressure_indicative": (
            _annualized_ratio(inflow_pressure, day_count)
        ),

        "outflow_pressure": outflow_pressure,
        "annualized_outflow_pressure_indicative": (
            _annualized_ratio(outflow_pressure, day_count)
        ),

        "net_flow_pressure": net_flow_pressure,
        "outflow_inflow_ratio": outflow_inflow_ratio,
        "net_inflow_retention_rate": net_inflow_retention_rate,

        "average_daily_outflow": average_daily_outflow,
        "apparent_reconversion_coverage_days": (
            apparent_reconversion_coverage_days
        ),
        "apparent_reconversion_coverage_30_day_periods": (
            apparent_reconversion_coverage_30_day_periods
        ),
    }


@monetary_indicators_bp.route(
    "/api/monetary-indicators/pilotage-timeseries",
    methods=["GET"],
)
def monetary_indicators_pilotage_timeseries():
    """
    Séries mensuelles de pilotage monétaire.

    Chaque mois articule :
    - stocks Odoo moyens sur les jours effectivement couverts ;
    - activité économique Cyclos ;
    - alimentations et sorties Cyclos ;
    - ratios de pilotage dérivés.
    """
    try:
        requested_start = _parse_optional_iso_date(request.args.get("start"), "start")
        requested_end = _parse_optional_iso_date(request.args.get("end"), "end")
    except ValueError as exc:
        return jsonify({"status": "error", "error": str(exc)}), 400

    conn = get_connection()
    cur = conn.cursor()

    try:
        period = _resolve_period(cur, requested_start, requested_end)
    except ValueError as exc:
        conn.close()
        return jsonify({"status": "error", "error": str(exc)}), 400

    if period["effective_start"] is None or period["effective_end"] is None:
        conn.close()
        return jsonify({
            "status": "ok",
            "bounds": period["bounds"],
            "requested_period": {
                "start": period["requested_start"],
                "end": period["requested_end"],
            },
            "effective_period": None,
            "items": [],
        })

    monthly_rows = cur.execute("""
        SELECT
            substr(snapshot_date, 1, 7) AS month_key,
            year,
            month,
            COUNT(*) AS day_count,
            AVG(gonettes_num_circulation) AS avg_numeric_mass,
            AVG(fonds_garantie_num) AS avg_numeric_guarantee
        FROM odoo_monetary_indicators_daily
        WHERE snapshot_date BETWEEN ? AND ?
        GROUP BY
            substr(snapshot_date, 1, 7),
            year,
            month
        ORDER BY month_key ASC
    """, (
        period["effective_start"],
        period["effective_end"],
    )).fetchall()

    conn.close()

    charts = compute_stats_charts(
        start=period["effective_start"],
        end=period["effective_end"],
        year=None,
    )

    activity_by_month = _aggregate_daily_activity_by_month(charts)
    inflows_by_month = _map_monthly_circuit_flow_series(charts, "inflows")
    outflows_by_month = _map_monthly_circuit_flow_series(charts, "outflows")

    items = [
        _build_pilotage_monthly_item(
            row,
            activity_by_month=activity_by_month,
            inflows_by_month=inflows_by_month,
            outflows_by_month=outflows_by_month,
        )
        for row in monthly_rows
    ]

    return jsonify({
        "status": "ok",
        "bounds": period["bounds"],
        "requested_period": {
            "start": period["requested_start"],
            "end": period["requested_end"],
        },
        "effective_period": {
            "start": period["effective_start"],
            "end": period["effective_end"],
        },
        "semantics": {
            "monthly_stocks": (
                "Les stocks monétaires sont moyennés sur les jours quotidiens "
                "Odoo effectivement disponibles dans chaque mois."
            ),
            "monthly_flows": (
                "Les flux Cyclos sont agrégés sur la même période effective "
                "et ventilés par mois calendaire."
            ),
            "partial_months": (
                "Le premier ou le dernier mois peuvent être partiels lorsque "
                "la période sélectionnée ne couvre pas un mois complet."
            ),
        },
        "items": items,
    })


def _group_pilotage_transactions_by_year(rows):
    rows_by_year = {}

    for row in rows:
        raw_date = str(row.get("date") or "")
        year_token = raw_date[:4]

        if not year_token.isdigit():
            continue

        rows_by_year.setdefault(int(year_token), []).append(row)

    return rows_by_year


def _build_pilotage_yearly_items(rows, metrics_builder):
    rows_by_year = _group_pilotage_transactions_by_year(rows)

    return [
        {
            "year": year,
            **metrics_builder(rows_by_year[year]),
        }
        for year in sorted(rows_by_year)
    ]


def _build_pilotage_reuse_yearly_items(rows=None):
    if rows is None:
        rows = fetch_transactions()

    return _build_pilotage_yearly_items(
        rows,
        _compute_internal_reuse_metrics,
    )


def _build_pilotage_lm3_yearly_items(rows=None):
    if rows is None:
        rows = fetch_transactions()

    return _build_pilotage_yearly_items(
        rows,
        _compute_lm3_metrics,
    )


@monetary_indicators_bp.route(
    "/api/monetary-indicators/pilotage-reuse-yearly",
    methods=["GET"],
)
def monetary_indicators_pilotage_reuse_yearly():
    """
    Série historique annuelle de réemploi interne et de multiplicateur
    de recirculation estimé.

    Cette série est transactionnelle : elle repose uniquement sur
    les flux économiques Cyclos, et n'est donc pas limitée par
    les bornes quotidiennes Odoo utilisées dans le pilotage monétaire
    stock ↔ flux.
    """
    items = load_pilotage_yearly_cache_items(
        PILOTAGE_REUSE_YEARLY_SERIES_KEY,
    )

    # Fallback résilient : une instance neuve ou mal bootstrapée
    # continue de répondre juste, au prix du calcul historique live.
    if not items:
        items = _build_pilotage_reuse_yearly_items()

    return jsonify({
        "status": "ok",
        "semantics": {
            "economic_activity_scope": (
                "Le calcul reprend strictement le périmètre d'activité "
                "économique MLCFlux, hors flux techniques et hors opérateurs."
            ),
            "weighted_internal_reuse_propensity": (
                "Somme des volumes réemployés bornés acteur par acteur, "
                "divisée par les recettes économiques internes reçues."
            ),
            "internal_multiplier_estimated": (
                "Multiplicateur indicatif dérivé par k = 1 / (1 - c), "
                "où c est la propension pondérée de réemploi interne."
            ),
            "lm3_estimated": (
                "LM3 estimé sur la période de pilotage effective : "
                "1 + gain de vague 2 + gain de vague 3."
            ),
            "lm3_period_scope": (
                "Les KPI LM3 de synthèse sont recalculés sur la période active. "
                "Les séries annuelles servent de repère historique séparé."
            ),
            "partial_years": (
                "2019 et l'année en cours peuvent être partielles ; "
                "leurs valeurs doivent être comparées avec prudence."
            ),
        },
        "items": items,
    })


@monetary_indicators_bp.route(
    "/api/monetary-indicators/pilotage-lm3-yearly",
    methods=["GET"],
)
def monetary_indicators_pilotage_lm3_yearly():
    """
    Série annuelle du LM3 estimé.

    Le calcul suit trois vagues de circulation à partir des acteurs
    ayant reçu une conversion / alimentation, selon une adaptation
    transactionnelle de la méthode LM3 documentée dans le chantier.
    """
    items = load_pilotage_yearly_cache_items(
        PILOTAGE_LM3_YEARLY_SERIES_KEY,
    )

    # Fallback résilient : une instance neuve ou mal bootstrapée
    # continue de répondre juste, au prix du calcul historique live.
    if not items:
        items = _build_pilotage_lm3_yearly_items()

    return jsonify({
        "status": "ok",
        "semantics": {
            "lm3_estimated": (
                "LM3 estimé = 1 + gain de vague 2 + gain de vague 3."
            ),
            "p1": (
                "P1 regroupe les acteurs ayant reçu une conversion "
                "ou alimentation A/C -> P/U pendant l'année."
            ),
            "p2": (
                "P2 regroupe les acteurs atteints par les paiements "
                "économiques pondérés de P1."
            ),
            "p3": (
                "P3 regroupe les acteurs atteints par les paiements "
                "économiques propagés de P2."
            ),
            "propensity": (
                "Les propensions de réemploi individuelles sont calculées "
                "sur l'année puis bornées à 1 avant propagation."
            ),
            "partial_years": (
                "2019 et l'année en cours peuvent être partielles ; "
                "leurs valeurs doivent être comparées avec prudence."
            ),
        },
        "items": items,
    })


@monetary_indicators_bp.route(
    "/api/monetary-indicators/pilotage-lm3-chains",
    methods=["GET"],
)
def monetary_indicators_pilotage_lm3_chains():
    """
    Chaînes de circulation observées jusqu'au troisième niveau LM3,
    calculées sur la période active.
    """
    start = request.args.get("start")
    end = request.args.get("end")

    try:
        limit = int(request.args.get("limit", "15"))
    except ValueError:
        limit = 15

    rows = fetch_transactions(
        start=start,
        end=end,
        year=None,
    )

    chains = _compute_lm3_observed_chains(
        rows,
        limit=limit,
    )

    return jsonify({
        "status": "ok",
        "semantics": {
            "observed_chain": (
                "Une chaîne retenue vérifie : alimentation de P1, puis "
                "paiement économique P1 -> P2, puis paiement économique "
                "ultérieur P2 -> P3."
            ),
            "configuration_count": (
                "Nombre d'appariements temporellement compatibles entre "
                "les paiements P1 -> P2 et les paiements ultérieurs P2 -> P3."
            ),
            "caution": (
                "Ces chaînes sont réelles au niveau transactionnel et temporel, "
                "mais ne constituent pas un traçage littéral des mêmes unités de Gonette."
            ),
        },
        **chains,
    })


@monetary_indicators_bp.route(
    "/api/monetary-indicators/pilotage-summary",
    methods=["GET"],
)
def monetary_indicators_pilotage_summary():
    """
    Croise les stocks Odoo quotidiens et les flux Cyclos
    sur la même période monétaire effective.
    """
    try:
        requested_start = _parse_optional_iso_date(request.args.get("start"), "start")
        requested_end = _parse_optional_iso_date(request.args.get("end"), "end")
    except ValueError as exc:
        return jsonify({"status": "error", "error": str(exc)}), 400

    conn = get_connection()
    cur = conn.cursor()

    try:
        period = _resolve_period(cur, requested_start, requested_end)
    except ValueError as exc:
        conn.close()
        return jsonify({"status": "error", "error": str(exc)}), 400

    bundle = _build_pilotage_monetary_bundle(cur, period)
    conn.close()

    period_metrics = bundle["period_metrics"] or {}

    effective_start = period["effective_start"]
    effective_end = period["effective_end"]

    analysis_start = effective_start or period["requested_start"]
    analysis_end = effective_end or period["requested_end"]

    stats = compute_global_stats(
        start=analysis_start,
        end=analysis_end,
        year=None,
    )

    period_transactions = fetch_transactions(
        start=analysis_start,
        end=analysis_end,
        year=None,
    )

    reuse_metrics = _compute_internal_reuse_metrics(period_transactions)
    lm3_metrics = _compute_lm3_metrics(period_transactions)

    day_count = int(period_metrics.get("day_count") or 0)
    average_numeric_mass = _money2(
        period_metrics.get("average_gonettes_num_circulation")
    )
    average_numeric_guarantee = _money2(
        period_metrics.get("average_fonds_garantie_num")
    )

    economic_activity_volume = _money2(
        stats.get("volume_activite_economique")
    )
    inflow_volume = _money2(
        stats.get("volume_alimente_circuit")
    )
    outflow_volume = _money2(
        stats.get("volume_sorti_circuit")
    )
    net_cyclos_flow = _money2(inflow_volume - outflow_volume)

    raw_numeric_stock_variation = period_metrics.get(
        "variation_gonettes_num_circulation"
    )

    numeric_stock_variation = (
        _money2(raw_numeric_stock_variation)
        if raw_numeric_stock_variation is not None
        else None
    )

    reconciliation_residual = (
        _money2(numeric_stock_variation - net_cyclos_flow)
        if numeric_stock_variation is not None
        else None
    )

    economic_activity_intensity = _ratio(
        economic_activity_volume,
        average_numeric_mass,
    )
    inflow_pressure = _ratio(
        inflow_volume,
        average_numeric_mass,
    )
    outflow_pressure = _ratio(
        outflow_volume,
        average_numeric_mass,
    )
    net_flow_pressure = _ratio(
        net_cyclos_flow,
        average_numeric_mass,
    )
    outflow_inflow_ratio = _ratio(
        outflow_volume,
        inflow_volume,
    )

    net_inflow_retention_rate = _ratio(
        net_cyclos_flow,
        inflow_volume,
    )

    economic_activity_per_outflow = _ratio(
        economic_activity_volume,
        outflow_volume,
    )

    economic_activity_per_inflow = _ratio(
        economic_activity_volume,
        inflow_volume,
    )

    transaction_intensity_per_1000_g = _ratio(
        int(stats.get("nb_transactions_activite_economique") or 0) * 1000,
        average_numeric_mass,
        digits=3,
    )

    average_numeric_guarantee_coverage_rate = _ratio(
        average_numeric_guarantee,
        average_numeric_mass,
    )

    average_daily_outflow = (
        _money2(outflow_volume / day_count)
        if day_count > 0
        else None
    )

    apparent_reconversion_coverage_days = _ratio(
        average_numeric_guarantee,
        average_daily_outflow,
        digits=3,
    ) if average_daily_outflow not in (None, 0) else None

    apparent_reconversion_coverage_30_day_periods = (
        round(apparent_reconversion_coverage_days / 30, 3)
        if apparent_reconversion_coverage_days is not None
        else None
    )

    return jsonify({
        "status": "ok",
        "bounds": period["bounds"],
        "requested_period": {
            "start": period["requested_start"],
            "end": period["requested_end"],
        },
        "effective_period": (
            {
                "start": effective_start,
                "end": effective_end,
            }
            if effective_start and effective_end
            else None
        ),
        "semantics": {
            "effective_period": (
                "Les KPI croisent les stocks Odoo et les flux Cyclos "
                "sur la même période monétaire effectivement disponible."
            ),
            "economic_activity_intensity": (
                "Volume d'activité économique numérique divisé par "
                "la masse numérique moyenne de la période."
            ),
            "reconciliation_residual": (
                "Variation du stock numérique moins le solde net "
                "alimentations-sorties observé dans Cyclos."
            ),
            "apparent_reconversion_coverage_days": (
                "Proxy indicatif : fonds de garantie numérique moyen "
                "divisé par les sorties quotidiennes moyennes."
            ),
            "apparent_reconversion_coverage_30_day_periods": (
                "Même proxy exprimé en équivalents de périodes de 30 jours."
            ),
            "net_inflow_retention_rate": (
                "Solde net alimentations-sorties divisé par le volume des alimentations."
            ),
            "economic_activity_per_outflow": (
                "Volume d’activité économique divisé par le volume des sorties."
            ),
            "economic_activity_per_inflow": (
                "Volume d’activité économique divisé par le volume des alimentations."
            ),
            "transaction_intensity_per_1000_g": (
                "Nombre de transactions économiques pour 1 000 G de masse numérique moyenne."
            ),
            "average_numeric_guarantee_coverage_rate": (
                "Fonds de garantie numérique moyen divisé par la masse numérique moyenne."
            ),
            "weighted_internal_reuse_propensity": (
                "Somme des volumes réemployés bornés acteur par acteur, "
                "divisée par les recettes économiques internes reçues."
            ),
            "internal_multiplier_estimated": (
                "Multiplicateur indicatif dérivé par k = 1 / (1 - c), "
                "où c est la propension pondérée de réemploi interne."
            ),
        },
        "monetary_reference": {
            "day_count": day_count,
            "average_numeric_mass": average_numeric_mass,
            "average_numeric_guarantee_fund": average_numeric_guarantee,
            "numeric_stock_variation": numeric_stock_variation,
        },
        "flow_reference": {
            "economic_activity_transaction_count": int(
                stats.get("nb_transactions_activite_economique") or 0
            ),
            "economic_activity_volume": economic_activity_volume,
            "inflow_transaction_count": int(
                stats.get("nb_alimentations_circuit") or 0
            ),
            "inflow_volume": inflow_volume,
            "outflow_transaction_count": int(
                stats.get("nb_sorties_circuit") or 0
            ),
            "outflow_volume": outflow_volume,
            "net_cyclos_flow": net_cyclos_flow,
        },
        "pilotage_metrics": {
            "circulation": {
                "economic_activity_intensity": economic_activity_intensity,
                "annualized_economic_activity_intensity_indicative": (
                    _annualized_ratio(economic_activity_intensity, day_count)
                ),
                "transaction_intensity_per_1000_g": (
                    transaction_intensity_per_1000_g
                ),
            },
            "entry_exit_pressure": {
                "inflow_pressure": inflow_pressure,
                "outflow_pressure": outflow_pressure,
                "net_flow_pressure": net_flow_pressure,
                "outflow_inflow_ratio": outflow_inflow_ratio,
                "annualized_inflow_pressure_indicative": (
                    _annualized_ratio(inflow_pressure, day_count)
                ),
                "annualized_outflow_pressure_indicative": (
                    _annualized_ratio(outflow_pressure, day_count)
                ),
            },
            "retention_and_yield": {
                "net_inflow_retention_rate": net_inflow_retention_rate,
                "economic_activity_per_outflow": economic_activity_per_outflow,
                "economic_activity_per_inflow": economic_activity_per_inflow,
            },
            "stock_flow_reconciliation": {
                "numeric_stock_variation": numeric_stock_variation,
                "net_cyclos_flow": net_cyclos_flow,
                "residual": reconciliation_residual,
            },
            "reconversion_coverage_proxy": {
                "average_daily_outflow": average_daily_outflow,
                "apparent_reconversion_coverage_days": (
                    apparent_reconversion_coverage_days
                ),
                "apparent_reconversion_coverage_30_day_periods": (
                    apparent_reconversion_coverage_30_day_periods
                ),
            },
            "guarantee_coverage": {
                "average_numeric_guarantee_coverage_rate": (
                    average_numeric_guarantee_coverage_rate
                ),
            },
            "internal_reuse": {
                "global": reuse_metrics["global"],
                "professionals": reuse_metrics["professionals"],
                "users": reuse_metrics["users"],
            },
            "lm3": lm3_metrics,
        },
    })


@monetary_indicators_bp.route(
    "/api/monetary-indicators/pilotage-holdings-summary",
    methods=["GET"],
)
def monetary_indicators_pilotage_holdings_summary():
    """
    Synthèse Détention & ancrage :
    stocks particuliers, dormance, mobilisation U→P et réactivation.
    """
    try:
        requested_start = _parse_optional_iso_date(request.args.get("start"), "start")
        requested_end = _parse_optional_iso_date(request.args.get("end"), "end")
        payload = get_pilotage_holdings_summary(
            requested_start=requested_start,
            requested_end=requested_end,
        )
    except ValueError as exc:
        return jsonify({"status": "error", "error": str(exc)}), 400

    return jsonify({
        "status": "ok",
        **payload,
    })


@monetary_indicators_bp.route(
    "/api/monetary-indicators/pilotage-holdings-timeseries",
    methods=["GET"],
)
def monetary_indicators_pilotage_holdings_timeseries():
    """
    Séries mensuelles Détention & ancrage :
    stock U, part de masse, mobilisation U→P et structure actif / dormant.
    """
    try:
        requested_start = _parse_optional_iso_date(request.args.get("start"), "start")
        requested_end = _parse_optional_iso_date(request.args.get("end"), "end")
        payload = get_pilotage_holdings_timeseries(
            requested_start=requested_start,
            requested_end=requested_end,
        )
    except ValueError as exc:
        return jsonify({"status": "error", "error": str(exc)}), 400

    return jsonify({
        "status": "ok",
        **payload,
    })

