from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


_PROFILE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,63}$")
PROFILES_DIR = Path(__file__).resolve().parent / "data" / "mlc_profiles"


@dataclass(frozen=True)
class MlcProfile:
    id: str
    name: str
    short_name: str
    currency_name: str
    currency_symbol: str
    status: str
    description: str
    data_strategy: str
    sources: dict[str, Any]
    features: dict[str, Any]
    classification: dict[str, Any]
    raw: dict[str, Any]

    def public_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "short_name": self.short_name,
            "currency_name": self.currency_name,
            "currency_symbol": self.currency_symbol,
            "status": self.status,
            "description": self.description,
            "data_strategy": self.data_strategy,
            "sources": self.sources,
            "features": self.features,
            "classification": self.classification,
            "known_differences": self.raw.get("known_differences", []),
            "notes": self.raw.get("notes", []),
        }


def _validate_profile_id(profile_id: str) -> str:
    normalized = str(profile_id or "").strip()

    if not _PROFILE_ID_RE.fullmatch(normalized):
        raise ValueError(f"Identifiant de profil MLC invalide : {profile_id!r}")

    return normalized


def _load_profile_file(path: Path) -> MlcProfile:
    with path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)

    profile_id = _validate_profile_id(raw.get("id"))

    expected_filename = f"{profile_id}.json"
    if path.name != expected_filename:
        raise ValueError(
            f"Nom de fichier incohérent pour le profil {profile_id!r} : "
            f"{path.name!r}, attendu {expected_filename!r}"
        )

    return MlcProfile(
        id=profile_id,
        name=str(raw.get("name") or profile_id),
        short_name=str(raw.get("short_name") or raw.get("name") or profile_id),
        currency_name=str(raw.get("currency_name") or ""),
        currency_symbol=str(raw.get("currency_symbol") or ""),
        status=str(raw.get("status") or "unknown"),
        description=str(raw.get("description") or ""),
        data_strategy=str(raw.get("data_strategy") or "unknown"),
        sources=dict(raw.get("sources") or {}),
        features=dict(raw.get("features") or {}),
        classification=dict(raw.get("classification") or {}),
        raw=dict(raw),
    )


def load_mlc_profiles() -> list[MlcProfile]:
    if not PROFILES_DIR.exists():
        return []

    profiles: list[MlcProfile] = []

    for path in sorted(PROFILES_DIR.glob("*.json")):
        profiles.append(_load_profile_file(path))

    ids = [profile.id for profile in profiles]
    duplicate_ids = sorted({profile_id for profile_id in ids if ids.count(profile_id) > 1})
    if duplicate_ids:
        raise ValueError(
            "Identifiants de profils MLC dupliqués : "
            + ", ".join(duplicate_ids)
        )

    return profiles


def list_public_mlc_profiles() -> list[dict[str, Any]]:
    return [profile.public_dict() for profile in load_mlc_profiles()]


def get_mlc_profile(profile_id: str) -> MlcProfile:
    normalized_id = _validate_profile_id(profile_id)

    for profile in load_mlc_profiles():
        if profile.id == normalized_id:
            return profile

    raise KeyError(f"Profil MLC introuvable : {normalized_id}")
