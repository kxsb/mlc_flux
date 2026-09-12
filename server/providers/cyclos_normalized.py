from __future__ import annotations

from typing import Any

from server.providers.cyclos_facts import CyclosActorFacts


class CyclosIdentityError(ValueError):
    """Un acteur Cyclos présent ne fournit pas d'identité de compte stable."""


def cyclos_account_row(
    actor: CyclosActorFacts | None,
) -> dict[str, Any] | None:
    """
    Convertit un acteur Cyclos natif vers une ligne `accounts`
    du contrat financier normalisé.

    Décision étayée sur Gonette + Graine :
    - account_id = actor.id
    - native_account_number = actor.number
    - native_owner_id = actor.user.id
    - native_account_type = actor.type.internalName

    Aucun fallback de account_id vers actor.number ou actor.user.id.
    """
    if actor is None:
        return None

    if not actor.actor_id:
        raise CyclosIdentityError(
            "Acteur Cyclos présent sans actor.id : "
            "impossible de produire un account_id stable."
        )

    return {
        "account_id": actor.actor_id,
        "native_account_number": actor.actor_number,
        "native_account_type": actor.native_account_type,
        "native_status": None,
        "display_label": actor.user_display,
        "native_owner_id": actor.user_id,
        "source_system": "cyclos",
    }
