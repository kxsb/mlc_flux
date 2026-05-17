from __future__ import annotations

from typing import Any

from server.analytics import (
    fetch_transactions,
    _actor_flow_family,
    _classify_analytical_transaction,
    _extract_professional_ref,
)


def _money2(value: Any) -> float:
    return round(float(value or 0.0), 2)


def _ratio(value: float, base: float, digits: int = 6) -> float | None:
    if not base:
        return None
    return round(float(value) / float(base), digits)


def get_professional_activity_flow_summary(
    requested_start: str | None,
    requested_end: str | None,
) -> dict:
    """
    Synthèse des flux économiques professionnels sur la période demandée.

    Périmètre :
    - uniquement les transactions classées comme activité économique centrale
      par _classify_analytical_transaction() ;
    - les comptes opérateurs P0000 / P9999 sont donc exclus en amont ;
    - les comptes techniques T_* sont exclus en amont ;
    - les comptes UD_* sont bien inclus dans la famille U.
    """
    rows = fetch_transactions(
        start=requested_start,
        end=requested_end,
    )

    activity_rows = [
        row
        for row in rows
        if _classify_analytical_transaction(row)["is_activity"]
    ]

    active_professional_refs: set[str] = set()
    receiving_professional_refs: set[str] = set()
    emitting_professional_refs: set[str] = set()
    b2b_professional_refs: set[str] = set()
    outflowing_professional_refs: set[str] = set()

    up_volume = 0.0
    pp_volume = 0.0
    pu_volume = 0.0
    pt_outflows_volume = 0.0

    up_count = 0
    pp_count = 0
    pu_count = 0
    pt_outflows_count = 0

    for row in activity_rows:
        from_label = str(row.get("from_label") or "").strip()
        to_label = str(row.get("to_label") or "").strip()
        amount = float(row.get("amount") or 0.0)

        source_family = _actor_flow_family(from_label)
        target_family = _actor_flow_family(to_label)

        from_professional_ref = (
            _extract_professional_ref(from_label)
            if source_family == "P"
            else None
        )
        to_professional_ref = (
            _extract_professional_ref(to_label)
            if target_family == "P"
            else None
        )

        # U→P : paiements des particuliers vers les professionnels.
        # La famille U inclut explicitement les UD_*.
        if source_family == "U" and target_family == "P":
            up_volume += amount
            up_count += 1

            if to_professional_ref:
                active_professional_refs.add(to_professional_ref)
                receiving_professional_refs.add(to_professional_ref)

            continue

        # P→P : circulation interprofessionnelle.
        if source_family == "P" and target_family == "P":
            pp_volume += amount
            pp_count += 1

            if from_professional_ref:
                active_professional_refs.add(from_professional_ref)
                emitting_professional_refs.add(from_professional_ref)
                b2b_professional_refs.add(from_professional_ref)

            if to_professional_ref:
                active_professional_refs.add(to_professional_ref)
                receiving_professional_refs.add(to_professional_ref)
                b2b_professional_refs.add(to_professional_ref)

            continue

        # P→U : flux des professionnels vers les particuliers.
        if source_family == "P" and target_family == "U":
            pu_volume += amount
            pu_count += 1

            if from_professional_ref:
                active_professional_refs.add(from_professional_ref)
                emitting_professional_refs.add(from_professional_ref)

            continue

    # ------------------------------------------------------------------
    # Sorties professionnelles du circuit :
    # - flux P→T classés dans le bucket analytique "outflows" ;
    # - ils ne relèvent pas de l'activité économique centrale,
    #   mais sont indispensables pour lire les tensions d'usage professionnel.
    # ------------------------------------------------------------------
    for row in rows:
        classification = _classify_analytical_transaction(row)

        if classification["bucket"] != "outflows":
            continue

        from_label = str(row.get("from_label") or "").strip()
        to_label = str(row.get("to_label") or "").strip()
        amount = float(row.get("amount") or 0.0)

        source_family = _actor_flow_family(from_label)
        target_family = _actor_flow_family(to_label)

        if source_family != "P" or target_family != "T":
            continue

        pt_outflows_volume += amount
        pt_outflows_count += 1

        from_professional_ref = _extract_professional_ref(from_label)

        if from_professional_ref:
            outflowing_professional_refs.add(from_professional_ref)

    received_volume = up_volume + pp_volume
    emitted_volume = pp_volume + pu_volume

    received_count = up_count + pp_count
    emitted_count = pp_count + pu_count

    return {
        "requested_period": {
            "start": requested_start,
            "end": requested_end,
        },

        "professional_counts": {
            "active": len(active_professional_refs),
            "receiving": len(receiving_professional_refs),
            "emitting": len(emitting_professional_refs),
            "involved_in_b2b": len(b2b_professional_refs),
            "outflowing": len(outflowing_professional_refs),
        },

        "flows": {
            "up": {
                "count": int(up_count),
                "volume": _money2(up_volume),
            },
            "pp": {
                "count": int(pp_count),
                "volume": _money2(pp_volume),
            },
            "pu": {
                "count": int(pu_count),
                "volume": _money2(pu_volume),
            },
            "pt_outflows": {
                "count": int(pt_outflows_count),
                "volume": _money2(pt_outflows_volume),
            },
        },

        "aggregates": {
            "received_volume": _money2(received_volume),
            "emitted_volume": _money2(emitted_volume),
            "received_count": int(received_count),
            "emitted_count": int(emitted_count),

            "received_from_users_share": _ratio(
                up_volume,
                received_volume,
            ),
            "received_from_professionals_share": _ratio(
                pp_volume,
                received_volume,
            ),

            # Indicateur descriptif simple :
            # ce qui ressort économiquement depuis les pros /
            # ce qui entre économiquement vers eux sur la même période.
            #
            # Il peut dépasser 100 % si les professionnels dépensent
            # un stock acquis avant la période.
            "observed_reemission_rate": _ratio(
                emitted_volume,
                received_volume,
            ),

            "outflow_to_received_rate": _ratio(
                pt_outflows_volume,
                received_volume,
            ),
            "reemission_to_outflow_ratio": _ratio(
                emitted_volume,
                pt_outflows_volume,
            ),
        },
    }

def _professional_month_key(row: dict) -> str | None:
    raw_date = str(row.get("date") or "").strip()
    month_key = raw_date[:7]

    if (
        len(month_key) == 7
        and month_key[:4].isdigit()
        and month_key[4] == "-"
        and month_key[5:7].isdigit()
    ):
        return month_key

    return None


def _empty_professional_circulation_month(month_key: str) -> dict:
    return {
        "month_key": month_key,
        "flows": {
            "up": {"count": 0, "volume": 0.0},
            "pp": {"count": 0, "volume": 0.0},
            "pu": {"count": 0, "volume": 0.0},
            "pt_outflows": {"count": 0, "volume": 0.0},
        },
    }


def get_professional_circulation_timeseries(
    requested_start: str | None,
    requested_end: str | None,
) -> dict:
    """
    Série mensuelle de circulation professionnelle.

    Périmètre :
    - U→P, P→P et P→U issus de l'activité économique centrale MLCFlux ;
    - P→T issu du bucket analytique "outflows", correspondant aux
      reconversions / sorties professionnelles du circuit numérique.

    Cette série est transactionnelle et n'est pas limitée aux périodes
    couvertes par les snapshots monétaires Odoo.
    """
    rows = fetch_transactions(
        start=requested_start,
        end=requested_end,
    )

    monthly: dict[str, dict] = {}

    for row in rows:
        month_key = _professional_month_key(row)
        if month_key is None:
            continue

        from_label = str(row.get("from_label") or "").strip()
        to_label = str(row.get("to_label") or "").strip()
        amount = float(row.get("amount") or 0.0)

        source_family = _actor_flow_family(from_label)
        target_family = _actor_flow_family(to_label)
        classification = _classify_analytical_transaction(row)

        bucket = monthly.setdefault(
            month_key,
            _empty_professional_circulation_month(month_key),
        )

        flows = bucket["flows"]

        if classification["is_activity"]:
            if source_family == "U" and target_family == "P":
                flows["up"]["count"] += 1
                flows["up"]["volume"] += amount

            elif source_family == "P" and target_family == "P":
                flows["pp"]["count"] += 1
                flows["pp"]["volume"] += amount

            elif source_family == "P" and target_family == "U":
                flows["pu"]["count"] += 1
                flows["pu"]["volume"] += amount

        elif classification["bucket"] == "outflows":
            if source_family == "P" and target_family == "T":
                flows["pt_outflows"]["count"] += 1
                flows["pt_outflows"]["volume"] += amount

    items = []

    for month_key in sorted(monthly.keys()):
        item = monthly[month_key]
        flows = item["flows"]

        up_volume = float(flows["up"]["volume"] or 0.0)
        pp_volume = float(flows["pp"]["volume"] or 0.0)
        pu_volume = float(flows["pu"]["volume"] or 0.0)
        pt_outflows_volume = float(flows["pt_outflows"]["volume"] or 0.0)

        received_volume = up_volume + pp_volume
        emitted_volume = pp_volume + pu_volume

        item["flows"]["up"]["volume"] = _money2(up_volume)
        item["flows"]["pp"]["volume"] = _money2(pp_volume)
        item["flows"]["pu"]["volume"] = _money2(pu_volume)
        item["flows"]["pt_outflows"]["volume"] = _money2(pt_outflows_volume)

        item["aggregates"] = {
            "received_volume": _money2(received_volume),
            "emitted_volume": _money2(emitted_volume),
            "observed_reemission_rate": _ratio(
                emitted_volume,
                received_volume,
            ),
            "b2b_receipts_share": _ratio(
                pp_volume,
                received_volume,
            ),
            "outflow_to_received_rate": _ratio(
                pt_outflows_volume,
                received_volume,
            ),
        }

        items.append(item)

    return {
        "requested_period": {
            "start": requested_start,
            "end": requested_end,
        },
        "items": items,
    }

