from __future__ import annotations

import csv
import json
import os
import re
import unicodedata
from pathlib import Path
from typing import Any

from server.mlc_context import get_mlc_db_path, normalize_mlc_id


APP_ROOT = Path(__file__).resolve().parents[2]
SERVER_DIR = APP_ROOT / "server"
DATA_DIR = SERVER_DIR / "data"
PROFILE_DIR = DATA_DIR / "mlc_profiles"


def _mapping_path(mlc_id: str) -> Path:
    normalized = normalize_mlc_id(mlc_id)
    db_path = get_mlc_db_path(normalized)
    return db_path.parent / "private_actor_mapping.json"


def _profile_path(mlc_id: str) -> Path:
    return PROFILE_DIR / f"{normalize_mlc_id(mlc_id)}.json"


def _load_profile_rules(mlc_id: str) -> dict[str, Any]:
    path = _profile_path(mlc_id)
    if not path.exists():
        return {}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

    return (
        data.get("actor_classification", {})
        .get("private_actor_mapping", {})
        or {}
    )


def _load_mapping(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "next_sequence": 1,
            "items": {},
        }

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        data = {}

    if not isinstance(data, dict):
        data = {}

    data.setdefault("next_sequence", 1)
    data.setdefault("items", {})

    if not isinstance(data["items"], dict):
        data["items"] = {}

    return data


def _write_mapping(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    os.chmod(tmp_path, 0o600)
    tmp_path.replace(path)
    os.chmod(path, 0o600)


def _resolve_dictionary_path(mlc_id: str, configured: str | None) -> Path | None:
    candidates: list[Path] = []

    if configured:
        configured_path = Path(configured)
        if configured_path.is_absolute():
            candidates.append(configured_path)
        else:
            candidates.extend([
                APP_ROOT / configured_path,
                DATA_DIR / configured_path,
                PROFILE_DIR / configured_path,
                get_mlc_db_path(normalize_mlc_id(mlc_id)).parent / configured_path,
            ])

    candidates.extend([
        get_mlc_db_path(normalize_mlc_id(mlc_id)).parent / "prenoms.csv",
        DATA_DIR / "prenoms.csv",
        DATA_DIR / "prénoms.csv",
        DATA_DIR / "firstnames.csv",
        PROFILE_DIR / "prenoms.csv",
    ])

    for path in candidates:
        if path.exists() and path.is_file():
            return path

    return None


def _clean_firstname(value: str) -> str:
    raw = unicodedata.normalize("NFKC", str(value or "")).strip()
    if not raw:
        return ""

    # On évite les espaces et signes gênants dans les labels affichés.
    raw = raw.replace("-", "_").replace(" ", "_").replace("'", "")
    raw = re.sub(r"[^\wÀ-ÿ]", "", raw, flags=re.UNICODE)
    raw = re.sub(r"_+", "_", raw).strip("_")

    if not raw:
        return ""

    return raw[0].upper() + raw[1:]


def _load_firstnames(path: Path | None) -> list[str]:
    if path is None or not path.exists():
        return []

    text = path.read_text(encoding="utf-8-sig")
    names: list[str] = []
    seen: set[str] = set()

    def add_candidate(value: str) -> None:
        cleaned = _clean_firstname(value)
        if not cleaned:
            return

        if cleaned.lower() in {"prenom", "prénom", "firstname", "first_name", "name"}:
            return

        key = cleaned.casefold()
        if key in seen:
            return

        seen.add(key)
        names.append(cleaned)

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return []

    # Cas simple et fréquent : un prénom par ligne.
    # On le traite avant csv.Sniffer, qui peut échouer sans séparateur.
    if all(("," not in line and ";" not in line and "\t" not in line) for line in lines[:50]):
        for line in lines:
            add_candidate(line)
        return names

    try:
        sample = text[:2048]
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        reader = csv.reader(text.splitlines(), dialect)
        for row in reader:
            if not row:
                continue
            add_candidate(str(row[0] or ""))
    except csv.Error:
        # Fallback robuste : on reprend ligne par ligne.
        for line in lines:
            first_cell = line.split(";")[0].split(",")[0].split("\t")[0]
            add_candidate(first_cell)

    return names

def _label_from_sequence(prefix: str, sequence: int, names: list[str]) -> str:
    clean_prefix = "".join(ch for ch in str(prefix or "U") if ch.isalnum()).upper()
    if not clean_prefix:
        clean_prefix = "U"

    if not names:
        return f"{clean_prefix}{sequence:06d}"

    index = sequence - 1
    name = names[index % len(names)]
    cycle = index // len(names)

    if cycle == 0:
        return f"{clean_prefix}_{name}"

    return f"{clean_prefix}_{name}_{cycle + 1:03d}"


def get_or_create_private_ref(
    *,
    mlc_id: str,
    stable_key: str,
    prefix: str = "U",
) -> str:
    """
    Retourne un pseudonyme particulier stable, sans exposer d'identifiant Cyclos.

    Stratégie par défaut pour les profils MLCFlux : prénoms lisibles.
    Fallback si aucun dictionnaire n'est disponible : séquence U000001.
    """
    key = str(stable_key or "").strip()
    if not key:
        return f"{prefix}_inconnu"

    path = _mapping_path(mlc_id)
    data = _load_mapping(path)
    items = data["items"]

    existing = items.get(key)
    if isinstance(existing, str):
        return existing
    if isinstance(existing, dict) and existing.get("label"):
        return str(existing["label"])

    rules = _load_profile_rules(mlc_id)
    strategy = str(rules.get("strategy") or "firstname_sequence_mapping")
    dictionary_path = _resolve_dictionary_path(
        mlc_id,
        rules.get("firstname_dictionary") or rules.get("dictionary_path"),
    )
    firstnames = _load_firstnames(dictionary_path)

    sequence = int(data.get("next_sequence") or 1)

    if strategy == "stable_sequence_mapping":
        label = f"{prefix}{sequence:06d}"
    else:
        label = _label_from_sequence(prefix, sequence, firstnames)

    items[key] = {
        "label": label,
        "sequence": sequence,
    }

    data["strategy"] = strategy
    data["firstname_dictionary"] = str(dictionary_path) if dictionary_path else None
    data["next_sequence"] = sequence + 1

    _write_mapping(path, data)
    return label
