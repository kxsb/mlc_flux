from __future__ import annotations

import json
import os
import tempfile
from collections import defaultdict
from datetime import UTC, datetime, date, timedelta
from pathlib import Path

from server.services.cyclos_client import get_transactions
from server.utils.anonymizer import (
    clean_professional_label,
    extract_user_display,
    is_professional_label,
)


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
PROFESSIONAL_ACTOR_USER_LINKS_PATH = DATA_DIR / "professional_actor_user_links.json"


class ProfessionalActorUserLinkConflict(RuntimeError):
    """Conflit de correspondance Pxxxx ↔ actor.id ↔ user.id."""


def _utc_now_iso():
    return datetime.now(UTC).isoformat(timespec="seconds")


def _ensure_data_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _load_json(path: Path, default):
    if not path.exists():
        return default

    raw = path.read_text().strip()
    if not raw:
        return default

    return json.loads(raw)


def _atomic_write_json(path: Path, payload):
    _ensure_data_dir()

    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"

    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        delete=False,
        prefix=f".{path.name}.",
        suffix=".tmp",
    ) as tmp:
        tmp.write(serialized)
        tmp_path = Path(tmp.name)

    os.replace(tmp_path, path)


def load_professional_actor_user_links():
    payload = _load_json(
        PROFESSIONAL_ACTOR_USER_LINKS_PATH,
        default={
            "version": 1,
            "updated_at": None,
            "links": {},
        },
    )

    payload.setdefault("version", 1)
    payload.setdefault("updated_at", None)
    payload.setdefault("links", {})

    return payload


def save_professional_actor_user_links(payload):
    payload["updated_at"] = _utc_now_iso()
    _atomic_write_json(PROFESSIONAL_ACTOR_USER_LINKS_PATH, payload)


def _month_ranges(date_from: str, date_to: str):
    start = date.fromisoformat(date_from)
    end = date.fromisoformat(date_to)

    cursor = start.replace(day=1)

    while cursor <= end:
        if cursor.month == 12:
            next_month = cursor.replace(year=cursor.year + 1, month=1, day=1)
        else:
            next_month = cursor.replace(month=cursor.month + 1, day=1)

        month_start = cursor
        month_end = next_month - timedelta(days=1)

        effective_start = max(month_start, start)
        effective_end = min(month_end, end)

        if effective_start <= effective_end:
            yield {
                "month_key": cursor.strftime("%Y-%m"),
                "date_from": effective_start.isoformat(),
                "date_to": effective_end.isoformat(),
            }

        cursor = next_month


def _actor_id(tx, side):
    return str((tx.get(side) or {}).get("id") or "").strip()


def _user_id(tx, side):
    side_payload = tx.get(side) or {}
    user = side_payload.get("user") or {}
    return str(user.get("id") or "").strip()


def _transaction_date(tx):
    raw_date = tx.get("date") or tx.get("transactionDate") or ""
    return str(raw_date)[:10] if raw_date else None


def _transaction_id(tx):
    return str(tx.get("id") or "").strip() or None


def _professional_ref_from_label(label: str) -> str:
    """
    Extrait le code Pxxxx depuis le label professionnel nettoyé.
    """
    normalized = str(label or "").strip()
    if not normalized:
        return ""

    first_part = normalized.split(" - ", 1)[0].strip()
    if first_part.startswith("P") and first_part[1:].isdigit():
        return first_part

    return ""


def _professional_identity_from_side(side_payload):
    display = extract_user_display(side_payload)

    if not display or not is_professional_label(display):
        return None

    professional_label = clean_professional_label(display)
    professional_ref = _professional_ref_from_label(professional_label)

    if not professional_ref:
        return None

    return {
        "professional_ref": professional_ref,
        "professional_label": professional_label,
    }


def _record_link_candidate(
    *,
    professional_ref,
    professional_label,
    actor_id,
    user_id,
    tx_date,
    tx_id,
    accumulator,
):
    if not professional_ref or not actor_id or not user_id:
        return False

    bucket = accumulator.setdefault(
        professional_ref,
        {
            "professional_ref": professional_ref,
            "professional_labels": set(),
            "actor_ids": set(),
            "user_ids": set(),
            "first_seen_transaction_date": tx_date,
            "last_seen_transaction_date": tx_date,
            "first_seen_transaction_id": tx_id,
            "last_seen_transaction_id": tx_id,
            "evidence_count": 0,
        },
    )

    if professional_label:
        bucket["professional_labels"].add(professional_label)

    bucket["actor_ids"].add(actor_id)
    bucket["user_ids"].add(user_id)
    bucket["evidence_count"] += 1

    if tx_date:
        current_first = bucket.get("first_seen_transaction_date")
        current_last = bucket.get("last_seen_transaction_date")

        if current_first is None or tx_date < current_first:
            bucket["first_seen_transaction_date"] = tx_date
            bucket["first_seen_transaction_id"] = tx_id

        if current_last is None or tx_date > current_last:
            bucket["last_seen_transaction_date"] = tx_date
            bucket["last_seen_transaction_id"] = tx_id

    return True


def _validate_candidate_conflicts(candidates):
    actor_to_refs = defaultdict(set)
    user_to_refs = defaultdict(set)

    for professional_ref, item in candidates.items():
        actor_ids = item["actor_ids"]
        user_ids = item["user_ids"]

        if len(actor_ids) > 1:
            raise ProfessionalActorUserLinkConflict(
                "Conflit détecté : "
                f"{professional_ref} associé à plusieurs actor.id."
            )

        if len(user_ids) > 1:
            raise ProfessionalActorUserLinkConflict(
                "Conflit détecté : "
                f"{professional_ref} associé à plusieurs user.id."
            )

        for actor_id in actor_ids:
            actor_to_refs[actor_id].add(professional_ref)

        for user_id in user_ids:
            user_to_refs[user_id].add(professional_ref)

    conflicting_actors = {
        actor_id: refs
        for actor_id, refs in actor_to_refs.items()
        if len(refs) > 1
    }

    if conflicting_actors:
        raise ProfessionalActorUserLinkConflict(
            "Conflit détecté : au moins un actor.id est associé "
            "à plusieurs codes professionnels."
        )

    conflicting_users = {
        user_id: refs
        for user_id, refs in user_to_refs.items()
        if len(refs) > 1
    }

    if conflicting_users:
        raise ProfessionalActorUserLinkConflict(
            "Conflit détecté : au moins un user.id est associé "
            "à plusieurs codes professionnels."
        )


def _merge_candidates(existing_payload, candidates):
    links = existing_payload.setdefault("links", {})

    created = 0
    updated = 0
    unchanged = 0

    existing_actor_to_ref = {}
    existing_user_to_ref = {}

    for professional_ref, record in links.items():
        actor_id = record.get("actor_id")
        user_id = record.get("user_id")

        if actor_id:
            existing_actor_to_ref[actor_id] = professional_ref
        if user_id:
            existing_user_to_ref[user_id] = professional_ref

    for professional_ref, candidate in candidates.items():
        actor_id = next(iter(candidate["actor_ids"]))
        user_id = next(iter(candidate["user_ids"]))
        professional_labels = sorted(candidate["professional_labels"])
        professional_label = professional_labels[-1] if professional_labels else professional_ref
        now = _utc_now_iso()

        existing = links.get(professional_ref)

        if existing is None:
            other_ref_for_actor = existing_actor_to_ref.get(actor_id)
            if other_ref_for_actor and other_ref_for_actor != professional_ref:
                raise ProfessionalActorUserLinkConflict(
                    "Conflit avec le mapping existant : "
                    f"actor.id déjà associé à {other_ref_for_actor}."
                )

            other_ref_for_user = existing_user_to_ref.get(user_id)
            if other_ref_for_user and other_ref_for_user != professional_ref:
                raise ProfessionalActorUserLinkConflict(
                    "Conflit avec le mapping existant : "
                    f"user.id déjà associé à {other_ref_for_user}."
                )

            links[professional_ref] = {
                "professional_ref": professional_ref,
                "professional_label": professional_label,
                "professional_labels_seen": professional_labels,
                "actor_id": actor_id,
                "user_id": user_id,
                "first_seen_at": now,
                "last_seen_at": now,
                "first_seen_transaction_date": candidate.get("first_seen_transaction_date"),
                "last_seen_transaction_date": candidate.get("last_seen_transaction_date"),
                "first_seen_transaction_id": candidate.get("first_seen_transaction_id"),
                "last_seen_transaction_id": candidate.get("last_seen_transaction_id"),
                "evidence_count": int(candidate.get("evidence_count") or 0),
            }

            existing_actor_to_ref[actor_id] = professional_ref
            existing_user_to_ref[user_id] = professional_ref
            created += 1
            continue

        changed = False

        if existing.get("professional_label") != professional_label:
            existing["professional_label"] = professional_label
            changed = True

        old_labels = sorted(existing.get("professional_labels_seen") or [])
        merged_labels = sorted(set(old_labels).union(professional_labels))
        if old_labels != merged_labels:
            existing["professional_labels_seen"] = merged_labels
            changed = True

        if existing.get("actor_id") and existing["actor_id"] != actor_id:
            raise ProfessionalActorUserLinkConflict(
                "Conflit avec le mapping existant : "
                f"{professional_ref} déjà lié à un autre actor.id."
            )

        if existing.get("user_id") and existing["user_id"] != user_id:
            raise ProfessionalActorUserLinkConflict(
                "Conflit avec le mapping existant : "
                f"{professional_ref} déjà lié à un autre user.id."
            )

        if not existing.get("actor_id"):
            existing["actor_id"] = actor_id
            changed = True

        if not existing.get("user_id"):
            existing["user_id"] = user_id
            changed = True

        old_first_date = existing.get("first_seen_transaction_date")
        new_first_date = candidate.get("first_seen_transaction_date")
        if new_first_date and (old_first_date is None or new_first_date < old_first_date):
            existing["first_seen_transaction_date"] = new_first_date
            existing["first_seen_transaction_id"] = candidate.get("first_seen_transaction_id")
            changed = True

        old_last_date = existing.get("last_seen_transaction_date")
        new_last_date = candidate.get("last_seen_transaction_date")
        if new_last_date and (old_last_date is None or new_last_date > old_last_date):
            existing["last_seen_transaction_date"] = new_last_date
            existing["last_seen_transaction_id"] = candidate.get("last_seen_transaction_id")
            changed = True

        candidate_evidence_count = int(candidate.get("evidence_count") or 0)
        existing_evidence_count = int(existing.get("evidence_count") or 0)

        if candidate_evidence_count > existing_evidence_count:
            existing["evidence_count"] = candidate_evidence_count
            changed = True

        existing["last_seen_at"] = now

        if changed:
            updated += 1
        else:
            unchanged += 1

    return {
        "created": created,
        "updated": updated,
        "unchanged": unchanged,
        "stored_total": len(links),
    }


def sync_professional_actor_user_links(date_from: str, date_to: str, *, progress_callback=None):
    """
    Parcourt les transactions Cyclos bulk sur une période,
    extrait les liens Pxxxx ↔ actor.id ↔ user.id disponibles,
    puis met à jour atomiquement professional_actor_user_links.json.
    """
    payload = load_professional_actor_user_links()

    candidates = {}
    months = []
    fetched_transactions = 0
    candidate_evidences = 0

    for month in _month_ranges(date_from, date_to):
        if progress_callback:
            progress_callback({
                "stage": "month_start",
                **month,
            })

        transactions = get_transactions(
            date_from=month["date_from"],
            date_to=month["date_to"],
        )

        fetched_transactions += len(transactions)

        month_evidences = 0
        month_refs = set()

        for tx in transactions:
            tx_date = _transaction_date(tx)
            tx_id = _transaction_id(tx)

            for side in ("from", "to"):
                side_payload = tx.get(side) or {}
                identity = _professional_identity_from_side(side_payload)

                if identity is None:
                    continue

                actor_id = _actor_id(tx, side)
                user_id = _user_id(tx, side)

                recorded = _record_link_candidate(
                    professional_ref=identity["professional_ref"],
                    professional_label=identity["professional_label"],
                    actor_id=actor_id,
                    user_id=user_id,
                    tx_date=tx_date,
                    tx_id=tx_id,
                    accumulator=candidates,
                )

                if recorded:
                    month_evidences += 1
                    candidate_evidences += 1
                    month_refs.add(identity["professional_ref"])

        month_result = {
            **month,
            "transactions_fetched": len(transactions),
            "candidate_evidences": month_evidences,
            "candidate_professional_ref_count": len(month_refs),
        }
        months.append(month_result)

        if progress_callback:
            progress_callback({
                "stage": "month_done",
                **month_result,
            })

    _validate_candidate_conflicts(candidates)
    merge_result = _merge_candidates(payload, candidates)
    save_professional_actor_user_links(payload)

    return {
        "date_from": date_from,
        "date_to": date_to,
        "transactions_fetched": fetched_transactions,
        "candidate_professional_ref_count": len(candidates),
        "candidate_evidences": candidate_evidences,
        "months": months,
        **merge_result,
        "output_path": str(PROFESSIONAL_ACTOR_USER_LINKS_PATH),
    }
