from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class CyclosConfig:
    """
    Configuration d'accès à une instance Cyclos.

    Ce module ne contient aucun secret.
    Les valeurs proviennent exclusivement de l'environnement.
    """

    mlc_id: str
    base_url: str
    username: str
    password: str

    @property
    def is_complete(self) -> bool:
        return bool(
            self.base_url
            and self.username
            and self.password
        )


def get_cyclos_config(
    mlc_id: str | None = None,
) -> CyclosConfig:
    """
    Résout la configuration Cyclos.

    Une installation standalone peut utiliser les variables génériques :

        CYCLOS_BASE_URL
        CYCLOS_USERNAME
        CYCLOS_PASSWORD

    Les déploiements nécessitant plusieurs configurations peuvent
    conserver les variables préfixées par identifiant MLC :

        MLC_<ID>_CYCLOS_BASE_URL
        MLC_<ID>_CYCLOS_USERNAME
        MLC_<ID>_CYCLOS_PASSWORD

    Les variables spécifiques à la MLC sont prioritaires.
    """

    if mlc_id is None:
        from server.mlc_context import get_active_mlc_id

        mlc_id = get_active_mlc_id(
            fallback_to_default=True
        )

    normalized_id = str(
        mlc_id or ""
    ).strip().lower()

    if not normalized_id:
        raise ValueError(
            "Identifiant MLC absent."
        )

    env_id = (
        normalized_id
        .upper()
        .replace("-", "_")
    )

    def resolve(
        specific_name: str,
        generic_name: str,
    ) -> str:
        return str(
            os.getenv(
                f"MLC_{env_id}_{specific_name}"
            )
            or os.getenv(generic_name)
            or ""
        ).strip()

    return CyclosConfig(
        mlc_id=normalized_id,
        base_url=resolve(
            "CYCLOS_BASE_URL",
            "CYCLOS_BASE_URL",
        ).rstrip("/"),
        username=resolve(
            "CYCLOS_USERNAME",
            "CYCLOS_USERNAME",
        ),
        password=resolve(
            "CYCLOS_PASSWORD",
            "CYCLOS_PASSWORD",
        ),
    )
