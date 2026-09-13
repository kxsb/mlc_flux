from __future__ import annotations

import os
from pathlib import Path

from server.mlc_profiles import get_mlc_profile, load_mlc_profiles


DATA_DIR = Path(__file__).resolve().parent / "data"
INSTANCES_DIR = DATA_DIR / "instances"
DEFAULT_MLC_ID_ENV = "MLCFLUX_DEFAULT_MLC_ID"


def get_default_mlc_id() -> str:
    configured = str(os.getenv(DEFAULT_MLC_ID_ENV, "") or "").strip()

    if configured:
        return get_mlc_profile(configured).id

    profiles = load_mlc_profiles()
    if not profiles:
        raise RuntimeError("Aucun profil MLC disponible.")

    # Pour le chantier actuel, La Graine est l'instance de travail prioritaire.
    for profile in profiles:
        if profile.id == "graine":
            return profile.id

    return profiles[0].id


def normalize_mlc_id(mlc_id: str | None) -> str:
    value = str(mlc_id or "").strip()

    if not value:
        raise ValueError("Identifiant MLC vide.")

    return get_mlc_profile(value).id


def get_active_mlc_id(*, fallback_to_default: bool = True) -> str | None:
    """
    Retourne l'unique MLC configurée pour cette installation.

    fallback_to_default est conservé temporairement dans la signature
    pour compatibilité avec les appels existants. En mode standalone,
    il n'existe plus d'instance active distincte de l'instance configurée.
    """
    _ = fallback_to_default
    return get_default_mlc_id()


def get_mlc_instance_dir(mlc_id: str | None = None) -> Path:
    normalized_id = normalize_mlc_id(mlc_id or get_default_mlc_id())
    return INSTANCES_DIR / normalized_id


def get_mlc_runtime_dir(mlc_id: str | None = None) -> Path:
    return get_mlc_instance_dir(mlc_id) / "runtime"


def get_mlc_locks_dir(mlc_id: str | None = None) -> Path:
    return get_mlc_runtime_dir(mlc_id) / "locks"


def get_mlc_db_path(mlc_id: str | None = None) -> Path:
    return get_mlc_instance_dir(mlc_id) / "mlcflux.db"


def get_active_mlc_db_path() -> Path:
    return get_mlc_db_path(get_default_mlc_id())


def get_mlc_input001_db_path(
    mlc_id: str | None = None,
) -> Path:
    return get_mlc_instance_dir(mlc_id) / "input001.db"


def get_active_mlc_input001_db_path() -> Path:
    return get_mlc_input001_db_path(
        get_default_mlc_id()
    )


def ensure_mlc_instance_dirs(mlc_id: str | None = None) -> dict[str, Path]:
    normalized_id = normalize_mlc_id(mlc_id or get_default_mlc_id())

    instance_dir = get_mlc_instance_dir(normalized_id)
    runtime_dir = get_mlc_runtime_dir(normalized_id)
    locks_dir = get_mlc_locks_dir(normalized_id)

    instance_dir.mkdir(parents=True, exist_ok=True)
    runtime_dir.mkdir(parents=True, exist_ok=True)
    locks_dir.mkdir(parents=True, exist_ok=True)

    return {
        "instance_dir": instance_dir,
        "runtime_dir": runtime_dir,
        "locks_dir": locks_dir,
        "db_path": get_mlc_db_path(normalized_id),
    }
