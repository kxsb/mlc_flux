from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from server.mlc_profiles import get_mlc_profile
from server.services.professional_ref_mapping import get_or_create_professional_ref
from server.services.private_actor_mapping import get_or_create_private_ref


def _load_profile_rules(mlc_id: str) -> dict[str, Any]:
    """
    Charge les règles complètes du profil MLC côté backend.

    public_dict() filtre les clés internes destinées au backend,
    notamment actor_classification.
    """
    profile_path = (
        Path(__file__).resolve().parents[1]
        / "data"
        / "mlc_profiles"
        / f"{mlc_id}.json"
    )

    if not profile_path.exists():
        return get_mlc_profile(mlc_id).public_dict()

    return json.loads(profile_path.read_text(encoding="utf-8"))


@dataclass(frozen=True)
class ActorClassification:
    family: str
    label: str
    actor_type_internal: str | None
    actor_id: str | None
    actor_number: str | None
    user_id: str | None
    confidence: str
    reason: str


def _clean(value: Any) -> str | None:
    if value in (None, False):
        return None

    text = str(value).strip()
    return text or None


def _actor_type_internal(actor: dict[str, Any] | None) -> str | None:
    if not isinstance(actor, dict):
        return None

    actor_type = actor.get("type")
    if not isinstance(actor_type, dict):
        return None

    return _clean(actor_type.get("internalName"))


def _actor_number(actor: dict[str, Any] | None) -> str | None:
    if not isinstance(actor, dict):
        return None
    return _clean(actor.get("number"))


def _actor_id(actor: dict[str, Any] | None) -> str | None:
    if not isinstance(actor, dict):
        return None
    return _clean(actor.get("id"))


def _user_data(actor: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(actor, dict):
        return {}

    user = actor.get("user")
    if not isinstance(user, dict):
        return {}

    return user


def _user_id(actor: dict[str, Any] | None) -> str | None:
    return _clean(_user_data(actor).get("id"))


def _user_display(actor: dict[str, Any] | None) -> str | None:
    return _clean(_user_data(actor).get("display"))


def _safe_slug(value: str | None, *, fallback: str = "inconnu") -> str:
    text = _clean(value) or fallback
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"[^A-Za-z0-9À-ÿ_-]+", "", text)
    return text[:80] or fallback


def _family_prefix(family: str) -> str:
    if family == "P":
        return "P"
    if family == "U":
        return "U"
    if family == "UD":
        return "UD"
    if family == "T":
        return "T"
    return "X"


def _technical_label(actor_type_internal: str | None, actor_number: str | None) -> str:
    value = actor_type_internal or actor_number or "Technique"

    aliases = {
        "emission": "Émission",
        "emissionNum": "Émission",
        "Conversion": "Conversion",
        "stockBch": "StockBillets",
        "compteBillets": "Billets",
    }

    return "T_" + _safe_slug(aliases.get(value, value), fallback="Technique")


def _professional_label(
    *,
    mlc_id: str,
    actor: dict[str, Any] | None,
    actor_number: str | None,
    actor_id: str | None,
    user_id: str | None,
    user_display: str | None,
    rules: dict[str, Any],
) -> str:
    professional_strategy = rules.get("professional_ref_strategy")

    preserve_regex = (
        (rules.get("professional_mapping") or {}).get("preserve_regex")
        or (rules.get("fallbacks") or {}).get("display_prefix_p_regex")
        or r"\b(P\d{4,})\b"
    )

    for value in (user_display, actor_number):
        if not value:
            continue
        match = re.search(preserve_regex, value)
        if match:
            return match.group(1)

    if professional_strategy == "stable_sequence_mapping":
        if not isinstance(actor, dict):
            return "P_inconnu"
        return get_or_create_professional_ref(mlc_id=mlc_id, actor=actor)

    if actor_number:
        return "P" + _safe_slug(actor_number)

    if actor_id:
        return "P_actor_" + _safe_slug(actor_id)

    if user_id:
        return "P_user_" + _safe_slug(user_id)

    return "P_inconnu"


def _private_label(
    *,
    mlc_id: str,
    actor_id: str | None,
    user_id: str | None,
    actor_number: str | None,
    prefix: str = "U",
) -> str:
    """
    Pseudonymise les particuliers avec un mapping stable à prénoms.

    Les identifiants Cyclos ne sont plus exposés dans les labels stockés en base.
    """
    if actor_id:
        stable_key = f"{prefix}:actor:{actor_id}"
    elif user_id:
        stable_key = f"{prefix}:user:{user_id}"
    elif actor_number:
        stable_key = f"{prefix}:number:{actor_number}"
    else:
        return f"{prefix}_inconnu"

    return get_or_create_private_ref(
        mlc_id=mlc_id,
        stable_key=stable_key,
        prefix=prefix,
    )

def classify_cyclos_actor(
    actor: dict[str, Any] | None,
    *,
    mlc_id: str,
) -> ActorClassification:
    profile = _load_profile_rules(mlc_id)
    rules = profile.get("actor_classification") or {}

    families_by_type = rules.get("families_by_actor_type_internal") or {}

    if not isinstance(actor, dict):
        missing_family = rules.get("missing_actor_family")
        if missing_family == "T":
            return ActorClassification(
                family="T",
                label=rules.get("missing_actor_label") or "T_ActeurIndéterminé",
                actor_type_internal=None,
                actor_id=None,
                actor_number=None,
                user_id=None,
                confidence="medium",
                reason="missing actor -> T by profile rule",
            )

    actor_type_internal = _actor_type_internal(actor)
    actor_id = _actor_id(actor)
    actor_number = _actor_number(actor)
    user_id = _user_id(actor)
    user_display = _user_display(actor)

    if actor_type_internal is None:
        missing_family = rules.get("missing_actor_family")
        if missing_family == "T":
            return ActorClassification(
                family="T",
                label=rules.get("missing_actor_label") or "T_ActeurIndéterminé",
                actor_type_internal=None,
                actor_id=actor_id,
                actor_number=actor_number,
                user_id=user_id,
                confidence="medium",
                reason="missing actor_type_internal -> T by profile rule",
            )

    family = families_by_type.get(actor_type_internal)

    if family == "T":
        return ActorClassification(
            family="T",
            label=_technical_label(actor_type_internal, actor_number),
            actor_type_internal=actor_type_internal,
            actor_id=actor_id,
            actor_number=actor_number,
            user_id=user_id,
            confidence="high",
            reason="profile.actor_type_internal -> T",
        )

    if family == "P":
        return ActorClassification(
            family="P",
            label=_professional_label(
                mlc_id=mlc_id,
                actor=actor,
                actor_number=actor_number,
                actor_id=actor_id,
                user_id=user_id,
                user_display=user_display,
                rules=rules,
            ),
            actor_type_internal=actor_type_internal,
            actor_id=actor_id,
            actor_number=actor_number,
            user_id=user_id,
            confidence="high",
            reason="profile.actor_type_internal -> P",
        )

    if family == "U":
        return ActorClassification(
            family="U",
            label=_private_label(
                mlc_id=mlc_id,
                actor_id=actor_id,
                user_id=user_id,
                actor_number=actor_number,
            ),
            actor_type_internal=actor_type_internal,
            actor_id=actor_id,
            actor_number=actor_number,
            user_id=user_id,
            confidence="high",
            reason="profile.actor_type_internal -> U",
        )

    if family == "UD":
        private = _private_label(
            mlc_id=mlc_id,
            actor_id=actor_id,
            user_id=user_id,
            actor_number=actor_number,
            prefix="UD",
        )
        return ActorClassification(
            family="UD",
            label=private,
            actor_type_internal=actor_type_internal,
            actor_id=actor_id,
            actor_number=actor_number,
            user_id=user_id,
            confidence="high",
            reason="profile.actor_type_internal -> UD",
        )

    return ActorClassification(
        family="X",
        label="X_" + _safe_slug(actor_type_internal or actor_id or user_id or actor_number),
        actor_type_internal=actor_type_internal,
        actor_id=actor_id,
        actor_number=actor_number,
        user_id=user_id,
        confidence="low",
        reason="unmapped actor_type_internal",
    )


def classify_cyclos_transaction(
    transaction: dict[str, Any],
    *,
    mlc_id: str,
) -> dict[str, Any]:
    source = classify_cyclos_actor(transaction.get("from"), mlc_id=mlc_id)
    target = classify_cyclos_actor(transaction.get("to"), mlc_id=mlc_id)

    tx_type = transaction.get("type") if isinstance(transaction.get("type"), dict) else {}

    return {
        "cyclos_id": transaction.get("id"),
        "transaction_number": transaction.get("transactionNumber"),
        "date": transaction.get("date"),
        "amount": transaction.get("amount"),
        "type_label": tx_type.get("name") or tx_type.get("internalName"),
        "type_internal": tx_type.get("internalName"),
        "from_label": source.label,
        "from_family": source.family,
        "from_reason": source.reason,
        "from_actor_type_internal": source.actor_type_internal,
        "to_label": target.label,
        "to_family": target.family,
        "to_reason": target.reason,
        "to_actor_type_internal": target.actor_type_internal,
    }
