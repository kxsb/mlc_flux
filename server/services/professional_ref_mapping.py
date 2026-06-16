from __future__ import annotations

import fcntl
import json
import os
import re
from pathlib import Path
from typing import Any

from server.mlc_context import get_mlc_instance_dir, get_mlc_locks_dir


def _profile_path(mlc_id: str) -> Path:
    return (
        Path(__file__).resolve().parents[1]
        / "data"
        / "mlc_profiles"
        / f"{mlc_id}.json"
    )


def _load_profile_rules(mlc_id: str) -> dict[str, Any]:
    path = _profile_path(mlc_id)
    return json.loads(path.read_text(encoding="utf-8"))


def _professional_mapping_config(mlc_id: str) -> dict[str, Any]:
    profile = _load_profile_rules(mlc_id)
    actor_rules = profile.get("actor_classification") or {}
    return actor_rules.get("professional_mapping") or {}


def _mapping_path(mlc_id: str) -> Path:
    config = _professional_mapping_config(mlc_id)
    filename = config.get("mapping_file") or "professional_mapping.json"
    return get_mlc_instance_dir(mlc_id) / filename


def _lock_path(mlc_id: str) -> Path:
    lock_dir = get_mlc_locks_dir(mlc_id)
    lock_dir.mkdir(parents=True, exist_ok=True)
    return lock_dir / "professional_mapping.lock"


def _read_mapping(path: Path, mlc_id: str) -> dict[str, Any]:
    if not path.exists():
        return {
            "kind": "mlcflux_professional_ref_mapping",
            "version": 1,
            "mlc_id": mlc_id,
            "mappings": {},
        }

    data = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(data.get("mappings"), dict):
        data["mappings"] = {}

    data.setdefault("kind", "mlcflux_professional_ref_mapping")
    data.setdefault("version", 1)
    data.setdefault("mlc_id", mlc_id)

    return data


def _write_mapping(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp_path, path)


def _get_path(actor: dict[str, Any], path: str) -> str | None:
    current: Any = actor

    for part in path.split("."):
        if not isinstance(current, dict):
            return None

        current = current.get(part)

    if current in (None, False, "", [], {}):
        return None

    return str(current).strip()


def build_professional_mapping_key(
    actor: dict[str, Any],
    *,
    mlc_id: str,
) -> str:
    config = _professional_mapping_config(mlc_id)
    key_priority = config.get("key_priority") or [
        "actor.number",
        "actor.id",
        "actor.user.id",
    ]

    normalized_actor = {
        "actor": actor,
    }

    for key_path in key_priority:
        value = _get_path(normalized_actor, key_path)
        if not value:
            continue

        return f"{key_path}:{value}"

    raise ValueError("Impossible de construire une clé stable pour le professionnel Cyclos.")


def _existing_professional_refs(mappings: dict[str, str]) -> set[str]:
    return {
        value
        for value in mappings.values()
        if isinstance(value, str) and re.fullmatch(r"P\d{4,}", value)
    }


def _next_professional_ref(mappings: dict[str, str], *, mlc_id: str) -> str:
    config = _professional_mapping_config(mlc_id)
    prefix = str(config.get("prefix") or "P")
    width = int(config.get("width") or 4)

    used = _existing_professional_refs(mappings)

    index = 1
    while True:
        candidate = f"{prefix}{index:0{width}d}"
        if candidate not in used:
            return candidate
        index += 1


def get_or_create_professional_ref(
    *,
    mlc_id: str,
    actor: dict[str, Any],
) -> str:
    mapping_key = build_professional_mapping_key(actor, mlc_id=mlc_id)
    path = _mapping_path(mlc_id)
    lock_path = _lock_path(mlc_id)

    with lock_path.open("w", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)

        data = _read_mapping(path, mlc_id)
        mappings = data.setdefault("mappings", {})

        if mapping_key in mappings:
            return mappings[mapping_key]

        professional_ref = _next_professional_ref(mappings, mlc_id=mlc_id)
        mappings[mapping_key] = professional_ref

        _write_mapping(path, data)

        return professional_ref


def count_professional_mappings(mlc_id: str) -> int:
    path = _mapping_path(mlc_id)
    data = _read_mapping(path, mlc_id)
    return len(data.get("mappings") or {})
