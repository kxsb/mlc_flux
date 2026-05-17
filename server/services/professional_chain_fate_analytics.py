from __future__ import annotations

import json
import os
import statistics
import tempfile
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from server.analytics import (
    fetch_transactions,
    _actor_flow_family,
    _classify_analytical_transaction,
    _extract_professional_ref,
)


OPERATOR_PRO_REFS = {"P0000", "P9999"}

SERVER_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = SERVER_DIR / "data"
SUMMARY_PATH = DATA_DIR / "professional_chain_fate_summary.json"


@dataclass
class Lot:
    amount: float
    seed_kind: str
    seed_date: datetime
    seed_professional_ref: str
    depth: int
    actors: tuple[str, ...]
    tracked: bool = True


def _money(value: Any) -> float:
    return round(float(value or 0.0), 2)


def _ratio(value: float, base: float, digits: int = 6) -> float | None:
    if not base:
        return None
    return round(float(value) / float(base), digits)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _parse_dt(value: Any) -> datetime:
    raw = str(value or "").strip()
    if not raw:
        return datetime(1970, 1, 1, tzinfo=timezone.utc)

    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        try:
            return datetime.fromisoformat(raw[:10]).replace(tzinfo=timezone.utc)
        except ValueError:
            return datetime(1970, 1, 1, tzinfo=timezone.utc)


def _row_sort_key(row: dict) -> tuple:
    return (
        _parse_dt(row.get("date")),
        str(row.get("transaction_number") or ""),
        str(row.get("cyclos_id") or ""),
        str(row.get("id") or ""),
    )


def _professional_ref(label: str) -> str | None:
    ref = _extract_professional_ref(str(label or "").strip())
    if not ref or ref in OPERATOR_PRO_REFS:
        return None
    return ref


def _classify_event(row: dict, include_technical_seed: bool) -> dict | None:
    from_label = str(row.get("from_label") or "").strip()
    to_label = str(row.get("to_label") or "").strip()
    amount = float(row.get("amount") or 0.0)

    if amount <= 0:
        return None

    source_family = _actor_flow_family(from_label)
    target_family = _actor_flow_family(to_label)
    classification = _classify_analytical_transaction(row)

    from_p = _professional_ref(from_label) if source_family == "P" else None
    to_p = _professional_ref(to_label) if target_family == "P" else None

    event_date = _parse_dt(row.get("date"))

    # Paiement d'un particulier vers un professionnel :
    # graine principale du modèle métier.
    if (
        classification["is_activity"]
        and source_family == "U"
        and target_family == "P"
        and to_p
    ):
        return {
            "kind": "seed_u_to_p",
            "date": event_date,
            "amount": amount,
            "receiver": to_p,
            "row": row,
        }

    # Entrée technique vers un professionnel :
    # graine ajoutée seulement dans le modèle élargi.
    if (
        include_technical_seed
        and classification.get("bucket") == "inflows"
        and source_family == "T"
        and target_family == "P"
        and to_p
    ):
        return {
            "kind": "seed_t_to_p",
            "date": event_date,
            "amount": amount,
            "receiver": to_p,
            "row": row,
        }

    # Propagation professionnelle.
    if (
        classification["is_activity"]
        and source_family == "P"
        and target_family == "P"
        and from_p
        and to_p
    ):
        return {
            "kind": "p_to_p",
            "date": event_date,
            "amount": amount,
            "sender": from_p,
            "receiver": to_p,
            "row": row,
        }

    # Sortie du suivi professionnel, mais pas sortie du réseau Gonette.
    if (
        classification["is_activity"]
        and source_family == "P"
        and target_family == "U"
        and from_p
    ):
        return {
            "kind": "p_to_u",
            "date": event_date,
            "amount": amount,
            "sender": from_p,
            "row": row,
        }

    # Sortie du circuit professionnel vers compte technique.
    if (
        classification.get("bucket") == "outflows"
        and source_family == "P"
        and target_family == "T"
        and from_p
    ):
        return {
            "kind": "p_to_t",
            "date": event_date,
            "amount": amount,
            "sender": from_p,
            "row": row,
        }

    return None


def _event_balance_delta(event: dict, professional: str) -> float:
    kind = event["kind"]

    if kind in {"seed_u_to_p", "seed_t_to_p"}:
        return event["amount"] if event["receiver"] == professional else 0.0

    if kind == "p_to_p":
        if event["sender"] == professional:
            return -event["amount"]
        if event["receiver"] == professional:
            return event["amount"]
        return 0.0

    if kind in {"p_to_u", "p_to_t"}:
        return -event["amount"] if event["sender"] == professional else 0.0

    return 0.0


def _compute_initial_untracked(events: list[dict]) -> dict[str, float]:
    per_professional_events: dict[str, list[dict]] = defaultdict(list)

    for event in events:
        kind = event["kind"]

        if kind in {"seed_u_to_p", "seed_t_to_p"}:
            per_professional_events[event["receiver"]].append(event)

        elif kind == "p_to_p":
            per_professional_events[event["sender"]].append(event)
            per_professional_events[event["receiver"]].append(event)

        elif kind in {"p_to_u", "p_to_t"}:
            per_professional_events[event["sender"]].append(event)

    initial = {}

    for ref, ref_events in per_professional_events.items():
        cumulative = 0.0
        minimum = 0.0

        for event in sorted(ref_events, key=lambda item: item["date"]):
            cumulative += _event_balance_delta(event, ref)
            minimum = min(minimum, cumulative)

        initial[ref] = max(0.0, -minimum)

    return initial


def _consume_fifo(
    inventory: deque[Lot],
    amount: float,
) -> tuple[list[Lot], float]:
    remaining = float(amount or 0.0)
    consumed: list[Lot] = []

    while remaining > 1e-9 and inventory:
        lot = inventory[0]
        take = min(lot.amount, remaining)

        consumed.append(Lot(
            amount=take,
            seed_kind=lot.seed_kind,
            seed_date=lot.seed_date,
            seed_professional_ref=lot.seed_professional_ref,
            depth=lot.depth,
            actors=lot.actors,
            tracked=lot.tracked,
        ))

        lot.amount -= take
        remaining -= take

        if lot.amount <= 1e-9:
            inventory.popleft()

    return consumed, remaining


def _delay_bucket(days: int) -> str:
    if days <= 0:
        return "same_day"
    if days <= 7:
        return "d1_7"
    if days <= 30:
        return "d8_30"
    if days <= 90:
        return "d31_90"
    return "gt90"


def _depth_bucket(depth: int) -> str:
    if depth <= 0:
        return "0"
    if depth == 1:
        return "1"
    if depth == 2:
        return "2"
    if depth == 3:
        return "3"
    if depth == 4:
        return "4"
    return "5_plus"


def _summarize_exit_fragments(exit_fragments: list[dict]) -> dict:
    if not exit_fragments:
        return {
            "fragment_count": 0,
            "volume": 0.0,
            "delay_days": {},
            "depth": {},
            "volume_by_delay_bucket": {},
            "volume_by_depth_bucket": {},
        }

    delays = [int(fragment["delay_days"]) for fragment in exit_fragments]
    depths = [int(fragment["depth"]) for fragment in exit_fragments]

    by_delay = defaultdict(lambda: {"fragment_count": 0, "volume": 0.0})
    by_depth = defaultdict(lambda: {"fragment_count": 0, "volume": 0.0})

    for fragment in exit_fragments:
        delay_key = _delay_bucket(int(fragment["delay_days"]))
        depth_key = _depth_bucket(int(fragment["depth"]))

        by_delay[delay_key]["fragment_count"] += 1
        by_delay[delay_key]["volume"] += float(fragment["amount"] or 0.0)

        by_depth[depth_key]["fragment_count"] += 1
        by_depth[depth_key]["volume"] += float(fragment["amount"] or 0.0)

    delay_order = ["same_day", "d1_7", "d8_30", "d31_90", "gt90"]
    depth_order = ["0", "1", "2", "3", "4", "5_plus"]

    return {
        "fragment_count": len(exit_fragments),
        "volume": _money(sum(float(fragment["amount"] or 0.0) for fragment in exit_fragments)),
        "delay_days": {
            "min": min(delays),
            "median": round(statistics.median(delays), 2),
            "mean": round(statistics.mean(delays), 2),
            "max": max(delays),
        },
        "depth": {
            "min": min(depths),
            "median": round(statistics.median(depths), 2),
            "mean": round(statistics.mean(depths), 2),
            "max": max(depths),
        },
        "volume_by_delay_bucket": {
            key: {
                "fragment_count": int(by_delay[key]["fragment_count"]),
                "volume": _money(by_delay[key]["volume"]),
            }
            for key in delay_order
        },
        "volume_by_depth_bucket": {
            key: {
                "fragment_count": int(by_depth[key]["fragment_count"]),
                "volume": _money(by_depth[key]["volume"]),
            }
            for key in depth_order
        },
    }


def _run_model(
    rows: list[dict],
    *,
    model_key: str,
    model_label: str,
    include_technical_seed: bool,
) -> dict:
    events = []

    for row in rows:
        event = _classify_event(
            row,
            include_technical_seed=include_technical_seed,
        )
        if event is not None:
            events.append(event)

    events.sort(key=lambda item: (
        item["date"],
        str(item["row"].get("transaction_number") or ""),
        str(item["row"].get("cyclos_id") or ""),
    ))

    event_counts = Counter(event["kind"] for event in events)
    event_volumes = defaultdict(float)

    for event in events:
        event_volumes[event["kind"]] += float(event["amount"] or 0.0)

    initial_untracked = _compute_initial_untracked(events)

    inventory: dict[str, deque[Lot]] = defaultdict(deque)

    for ref, amount in initial_untracked.items():
        if amount <= 0:
            continue

        inventory[ref].append(Lot(
            amount=amount,
            seed_kind="initial_untracked",
            seed_date=datetime(1970, 1, 1, tzinfo=timezone.utc),
            seed_professional_ref=ref,
            depth=0,
            actors=(ref,),
            tracked=False,
        ))

    seeded_volume = 0.0
    seed_counts = Counter()

    tracked_exit_fragments: list[dict] = []
    tracked_p_to_u_fragments: list[dict] = []

    unmatched_p_to_p_volume = 0.0
    unmatched_p_to_u_volume = 0.0
    unmatched_p_to_t_volume = 0.0

    for event in events:
        kind = event["kind"]

        if kind in {"seed_u_to_p", "seed_t_to_p"}:
            receiver = event["receiver"]
            amount = float(event["amount"] or 0.0)

            inventory[receiver].append(Lot(
                amount=amount,
                seed_kind=kind,
                seed_date=event["date"],
                seed_professional_ref=receiver,
                depth=0,
                actors=(receiver,),
                tracked=True,
            ))

            seeded_volume += amount
            seed_counts[kind] += 1
            continue

        if kind == "p_to_p":
            sender = event["sender"]
            receiver = event["receiver"]
            consumed, unmatched = _consume_fifo(inventory[sender], event["amount"])
            unmatched_p_to_p_volume += unmatched

            for fragment in consumed:
                actors = fragment.actors
                if receiver not in actors:
                    actors = actors + (receiver,)

                inventory[receiver].append(Lot(
                    amount=fragment.amount,
                    seed_kind=fragment.seed_kind,
                    seed_date=fragment.seed_date,
                    seed_professional_ref=fragment.seed_professional_ref,
                    depth=fragment.depth + 1,
                    actors=actors,
                    tracked=fragment.tracked,
                ))

            continue

        if kind == "p_to_u":
            sender = event["sender"]
            consumed, unmatched = _consume_fifo(inventory[sender], event["amount"])
            unmatched_p_to_u_volume += unmatched

            for fragment in consumed:
                if not fragment.tracked:
                    continue

                delay_days = max(0, (event["date"] - fragment.seed_date).days)

                tracked_p_to_u_fragments.append({
                    "amount": _money(fragment.amount),
                    "seed_kind": fragment.seed_kind,
                    "seed_date": fragment.seed_date.date().isoformat(),
                    "departure_date": event["date"].date().isoformat(),
                    "delay_days": int(delay_days),
                    "depth": int(fragment.depth),
                    "distinct_actor_count": len(set(fragment.actors)),
                    "seed_professional_ref": fragment.seed_professional_ref,
                    "last_professional_ref": sender,
                })

            continue

        if kind == "p_to_t":
            sender = event["sender"]
            consumed, unmatched = _consume_fifo(inventory[sender], event["amount"])
            unmatched_p_to_t_volume += unmatched

            for fragment in consumed:
                if not fragment.tracked:
                    continue

                delay_days = max(0, (event["date"] - fragment.seed_date).days)

                tracked_exit_fragments.append({
                    "amount": _money(fragment.amount),
                    "seed_kind": fragment.seed_kind,
                    "seed_date": fragment.seed_date.date().isoformat(),
                    "exit_date": event["date"].date().isoformat(),
                    "delay_days": int(delay_days),
                    "depth": int(fragment.depth),
                    "distinct_actor_count": len(set(fragment.actors)),
                    "seed_professional_ref": fragment.seed_professional_ref,
                    "last_professional_ref": sender,
                    "actors": tuple(fragment.actors),
                })

            continue

    tracked_remaining_volume = 0.0
    untracked_remaining_volume = 0.0

    for ref_inventory in inventory.values():
        for lot in ref_inventory:
            if lot.tracked:
                tracked_remaining_volume += float(lot.amount or 0.0)
            else:
                untracked_remaining_volume += float(lot.amount or 0.0)

    tracked_exit_volume = sum(float(fragment["amount"] or 0.0) for fragment in tracked_exit_fragments)
    tracked_p_to_u_volume = sum(float(fragment["amount"] or 0.0) for fragment in tracked_p_to_u_fragments)

    total_p_to_t_volume = event_volumes["p_to_t"]
    total_p_to_u_volume = event_volumes["p_to_u"]

    same_day_direct_exit_fragments = [
        fragment for fragment in tracked_exit_fragments
        if int(fragment["depth"]) == 0 and int(fragment["delay_days"]) == 0
    ]

    quasi_immediate_exit_fragments = [
        fragment for fragment in tracked_exit_fragments
        if int(fragment["depth"]) == 0 and int(fragment["delay_days"]) <= 7
    ]

    deep_chain_fragments = [
        fragment for fragment in tracked_exit_fragments
        if int(fragment["depth"]) >= 3
    ]

    long_lived_exit_fragments = [
        fragment for fragment in tracked_exit_fragments
        if int(fragment["delay_days"]) > 90
    ]

    return {
        "model_key": model_key,
        "model_label": model_label,
        "seed_policy": {
            "include_u_to_p": True,
            "include_t_to_p": include_technical_seed,
            "p_to_p_propagates_depth": True,
            "p_to_t_is_exit": True,
            "p_to_u_leaves_professional_tracking": True,
            "operator_refs_excluded": sorted(OPERATOR_PRO_REFS),
        },
        "event_counts": {
            key: int(value)
            for key, value in event_counts.items()
        },
        "event_volumes": {
            key: _money(value)
            for key, value in event_volumes.items()
        },
        "initial_untracked_opening_stock": {
            "professional_count": sum(1 for amount in initial_untracked.values() if amount > 0),
            "volume": _money(sum(initial_untracked.values())),
        },
        "tracked_seeds": {
            "seed_counts": {
                key: int(value)
                for key, value in seed_counts.items()
            },
            "seeded_volume": _money(seeded_volume),
        },
        "tracked_exit_to_t": {
            "matched_volume": _money(tracked_exit_volume),
            "total_p_to_t_volume": _money(total_p_to_t_volume),
            "matched_share_of_p_to_t": _ratio(
                tracked_exit_volume,
                total_p_to_t_volume,
            ),
            "summary": _summarize_exit_fragments(tracked_exit_fragments),
        },
        "tracked_departure_to_users": {
            "matched_volume": _money(tracked_p_to_u_volume),
            "total_p_to_u_volume": _money(total_p_to_u_volume),
            "matched_share_of_p_to_u": _ratio(
                tracked_p_to_u_volume,
                total_p_to_u_volume,
            ),
            "summary": _summarize_exit_fragments(tracked_p_to_u_fragments),
        },
        "unmatched_outflows": {
            "p_to_p_volume": _money(unmatched_p_to_p_volume),
            "p_to_u_volume": _money(unmatched_p_to_u_volume),
            "p_to_t_volume": _money(unmatched_p_to_t_volume),
        },
        "remaining_inventory": {
            "tracked_volume": _money(tracked_remaining_volume),
            "untracked_volume": _money(untracked_remaining_volume),
        },
        "focus_indicators": {
            "same_day_direct_exit": {
                "fragment_count": len(same_day_direct_exit_fragments),
                "volume": _money(sum(float(fragment["amount"] or 0.0) for fragment in same_day_direct_exit_fragments)),
                "exit_professional_count": len({
                    fragment["last_professional_ref"]
                    for fragment in same_day_direct_exit_fragments
                }),
            },
            "quasi_immediate_direct_exit_depth0_le_7d": {
                "fragment_count": len(quasi_immediate_exit_fragments),
                "volume": _money(sum(float(fragment["amount"] or 0.0) for fragment in quasi_immediate_exit_fragments)),
                "exit_professional_count": len({
                    fragment["last_professional_ref"]
                    for fragment in quasi_immediate_exit_fragments
                }),
            },
            "deep_chains_depth_ge_3": {
                "fragment_count": len(deep_chain_fragments),
                "volume": _money(sum(float(fragment["amount"] or 0.0) for fragment in deep_chain_fragments)),
                "exit_professional_count": len({
                    fragment["last_professional_ref"]
                    for fragment in deep_chain_fragments
                }),
                "distinct_chain_actor_count": len({
                    actor
                    for fragment in deep_chain_fragments
                    for actor in fragment.get("actors", ())
                    if actor
                }),
            },
            "long_lived_exit_gt_90d": {
                "fragment_count": len(long_lived_exit_fragments),
                "volume": _money(sum(float(fragment["amount"] or 0.0) for fragment in long_lived_exit_fragments)),
                "exit_professional_count": len({
                    fragment["last_professional_ref"]
                    for fragment in long_lived_exit_fragments
                }),
            },
        },
    }


def compute_professional_chain_fate_summary() -> dict:
    rows = sorted(fetch_transactions(), key=_row_sort_key)

    first_date = str(rows[0].get("date")) if rows else None
    last_date = str(rows[-1].get("date")) if rows else None

    model_a = _run_model(
        rows,
        model_key="u_to_p_seeds_only",
        model_label="Lots issus des paiements particuliers → professionnels",
        include_technical_seed=False,
    )

    model_b = _run_model(
        rows,
        model_key="u_to_p_plus_t_to_p_seeds",
        model_label="Lots issus des paiements U→P et des entrées techniques T→P",
        include_technical_seed=True,
    )

    return {
        "generated_at": _utc_now_iso(),
        "primary_model": "u_to_p_seeds_only",
        "metadata": {
            "transaction_row_count": len(rows),
            "first_transaction_date": first_date,
            "last_transaction_date": last_date,
        },
        "models": {
            "u_to_p_seeds_only": model_a,
            "u_to_p_plus_t_to_p_seeds": model_b,
        },
        "methodological_notes": [
            "Il s'agit d'une attribution FIFO par lots, pas d'un traçage littéral de chaque unité de Gonette.",
            "Le modèle principal suit les lots issus des paiements U→P ; le modèle élargi ajoute les entrées techniques T→P pour contrôler la couverture des sorties.",
            "Les chaînes sont suivies dans le circuit professionnel. Les flux P→U interrompent volontairement le suivi dans cette première modélisation.",
            "Les stocks initiaux non traçables sont modélisés par un volume d'ouverture conservateur afin de limiter la sur-attribution des reconversions aux lots suivis.",
        ],
    }


def write_professional_chain_fate_summary(payload: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=str(DATA_DIR),
        prefix=".professional_chain_fate_summary.",
        suffix=".json.tmp",
        delete=False,
    ) as tmp:
        json.dump(payload, tmp, ensure_ascii=False, indent=2)
        tmp.write("\n")
        tmp_path = Path(tmp.name)

    os.replace(tmp_path, SUMMARY_PATH)


def load_professional_chain_fate_summary() -> dict | None:
    if not SUMMARY_PATH.exists():
        return None

    with SUMMARY_PATH.open("r", encoding="utf-8") as fh:
        return json.load(fh)
