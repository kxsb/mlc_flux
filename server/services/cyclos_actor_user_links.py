from __future__ import annotations

import json
import os
import tempfile
from collections import defaultdict
from datetime import datetime, UTC
from pathlib import Path

from server.services.cyclos_client import get_transactions


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"

USER_MAPPING_PATH = DATA_DIR / "user_mapping.json"
ACTOR_USER_LINKS_PATH = DATA_DIR / "actor_user_links.json"


class ActorUserLinkConflict(RuntimeError):
    """Conflit de correspondance actor.id ↔ user.id."""


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


def load_actor_user_links():
    payload = _load_json(
        ACTOR_USER_LINKS_PATH,
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


def save_actor_user_links(payload):
    payload["updated_at"] = _utc_now_iso()
    _atomic_write_json(ACTOR_USER_LINKS_PATH, payload)


def load_known_actor_pseudonyms():
    """
    Charge le mapping actor:<id> -> U_Prénom déjà utilisé par MLCFlux.

    On ne tente de raccorder que ces actor.id particuliers connus :
    c'est le périmètre analytique qui nous intéresse.
    """
    raw_mapping = _load_json(USER_MAPPING_PATH, default={})

    actors = {}

    for key, pseudonym in raw_mapping.items():
        key = str(key)
        if not key.startswith("actor:"):
            continue

        actor_id = key.split(":", 1)[1].strip()
        if not actor_id:
            continue

        actors[actor_id] = str(pseudonym)

    return actors


def _month_ranges(date_from: str, date_to: str):
    start_year, start_month, _ = map(int, date_from.split("-"))
    end_year, end_month, _ = map(int, date_to.split("-"))

    year = start_year
    month = start_month

    while (year, month) <= (end_year, end_month):
        if month == 12:
            next_year, next_month = year + 1, 1
        else:
            next_year, next_month = year, month + 1

        month_start = f"{year:04d}-{month:02d}-01"

        if next_month == 1:
            month_end = f"{year:04d}-12-31"
        else:
            from datetime import date, timedelta

            next_month_start = date(next_year, next_month, 1)
            month_end_date = next_month_start - timedelta(days=1)
            month_end = month_end_date.isoformat()

        effective_start = max(month_start, date_from)
        effective_end = min(month_end, date_to)

        if effective_start <= effective_end:
            yield {
                "month_key": f"{year:04d}-{month:02d}",
                "date_from": effective_start,
                "date_to": effective_end,
            }

        year, month = next_year, next_month


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


def _record_link_candidate(
    *,
    known_actor_pseudonyms,
    actor_id,
    user_id,
    tx_date,
    tx_id,
    accumulator,
):
    if not actor_id or not user_id:
        return False

    pseudonym = known_actor_pseudonyms.get(actor_id)
    if pseudonym is None:
        return False

    bucket = accumulator.setdefault(
        actor_id,
        {
            "actor_id": actor_id,
            "user_ids": set(),
            "pseudonym": pseudonym,
            "first_seen_transaction_date": tx_date,
            "last_seen_transaction_date": tx_date,
            "first_seen_transaction_id": tx_id,
            "last_seen_transaction_id": tx_id,
            "evidence_count": 0,
        },
    )

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
    """
    Refuse :
    - un même actor.id lié à plusieurs user.id dans le lot ;
    - un même user.id lié à plusieurs actor.id dans le lot.
    """
    user_to_actors = defaultdict(set)

    for actor_id, item in candidates.items():
        user_ids = item["user_ids"]

        if len(user_ids) > 1:
            raise ActorUserLinkConflict(
                "Conflit détecté : "
                f"actor.id {actor_id} associé à plusieurs user.id."
            )

        for user_id in user_ids:
            user_to_actors[user_id].add(actor_id)

    conflicting_users = {
        user_id: actor_ids
        for user_id, actor_ids in user_to_actors.items()
        if len(actor_ids) > 1
    }

    if conflicting_users:
        raise ActorUserLinkConflict(
            "Conflit détecté : au moins un user.id est associé "
            "à plusieurs actor.id dans le lot."
        )


def _merge_candidates(existing_payload, candidates):
    links = existing_payload.setdefault("links", {})

    created = 0
    updated = 0
    unchanged = 0

    # Contrôle global user.id -> actor.id sur l'existant.
    existing_user_to_actor = {}
    for actor_id, record in links.items():
        user_id = record.get("user_id")
        if user_id:
            existing_user_to_actor[user_id] = actor_id

    for actor_id, candidate in candidates.items():
        user_id = next(iter(candidate["user_ids"]))
        pseudonym = candidate["pseudonym"]
        now = _utc_now_iso()

        existing = links.get(actor_id)

        if existing is None:
            other_actor = existing_user_to_actor.get(user_id)
            if other_actor and other_actor != actor_id:
                raise ActorUserLinkConflict(
                    "Conflit avec le mapping existant : "
                    f"user.id déjà associé à actor.id {other_actor}."
                )

            links[actor_id] = {
                "user_id": user_id,
                "pseudonym": pseudonym,
                "first_seen_at": now,
                "last_seen_at": now,
                "first_seen_transaction_date": candidate.get("first_seen_transaction_date"),
                "last_seen_transaction_date": candidate.get("last_seen_transaction_date"),
                "first_seen_transaction_id": candidate.get("first_seen_transaction_id"),
                "last_seen_transaction_id": candidate.get("last_seen_transaction_id"),
                "evidence_count": int(candidate.get("evidence_count") or 0),
            }
            existing_user_to_actor[user_id] = actor_id
            created += 1
            continue

        existing_user_id = existing.get("user_id")
        if existing_user_id and existing_user_id != user_id:
            raise ActorUserLinkConflict(
                "Conflit avec le mapping existant : "
                f"actor.id {actor_id} déjà lié à un autre user.id."
            )

        changed = False

        if not existing_user_id:
            existing["user_id"] = user_id
            changed = True

        if existing.get("pseudonym") != pseudonym:
            existing["pseudonym"] = pseudonym
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

        # Les fenêtres de synchronisation peuvent se chevaucher
        # (backfill complet après un test mensuel, sync quotidienne relancée, etc.).
        # Additionner aveuglément les preuves gonflerait artificiellement le compteur.
        # On conserve donc le niveau de preuve le plus élevé observé sur une synchronisation.
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


def sync_actor_user_links(date_from: str, date_to: str, *, progress_callback=None):
    """
    Parcourt les transactions Cyclos bulk sur une période,
    extrait les liens actor.id ↔ user.id disponibles,
    puis met à jour atomiquement actor_user_links.json.
    """
    known_actor_pseudonyms = load_known_actor_pseudonyms()
    payload = load_actor_user_links()

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
        month_actors = set()

        for tx in transactions:
            tx_date = _transaction_date(tx)
            tx_id = _transaction_id(tx)

            for side in ("from", "to"):
                actor_id = _actor_id(tx, side)
                user_id = _user_id(tx, side)

                recorded = _record_link_candidate(
                    known_actor_pseudonyms=known_actor_pseudonyms,
                    actor_id=actor_id,
                    user_id=user_id,
                    tx_date=tx_date,
                    tx_id=tx_id,
                    accumulator=candidates,
                )

                if recorded:
                    month_evidences += 1
                    candidate_evidences += 1
                    month_actors.add(actor_id)

        month_result = {
            **month,
            "transactions_fetched": len(transactions),
            "candidate_evidences": month_evidences,
            "candidate_actor_count": len(month_actors),
        }
        months.append(month_result)

        if progress_callback:
            progress_callback({
                "stage": "month_done",
                **month_result,
            })

    _validate_candidate_conflicts(candidates)
    merge_result = _merge_candidates(payload, candidates)
    save_actor_user_links(payload)

    return {
        "date_from": date_from,
        "date_to": date_to,
        "known_actor_count": len(known_actor_pseudonyms),
        "transactions_fetched": fetched_transactions,
        "candidate_actor_count": len(candidates),
        "candidate_evidences": candidate_evidences,
        "months": months,
        **merge_result,
        "output_path": str(ACTOR_USER_LINKS_PATH),
    }
