from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping

from server.resolver.account_resolver import (
    AccountFactCondition,
    AccountResolutionRule,
    AccountResolverRuleset,
    ResolverConfigurationError,
)


RULESET_DIR = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "resolver_rulesets"
)

_RULESET_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def _condition_values(value: Any, *, field: str) -> tuple[str, ...]:
    if isinstance(value, str):
        values = (value,)
    elif isinstance(value, list):
        values = tuple(value)
    else:
        raise ResolverConfigurationError(
            f"La condition {field!r} doit être une chaîne ou une liste de chaînes."
        )

    return tuple(str(item) for item in values)


def account_ruleset_from_mapping(payload: Mapping[str, Any]) -> AccountResolverRuleset:
    if not isinstance(payload, Mapping):
        raise ResolverConfigurationError(
            "Le document de ruleset doit être un objet JSON."
        )

    version = payload.get("version")
    raw_rules = payload.get("rules")

    if not isinstance(raw_rules, list):
        raise ResolverConfigurationError(
            "Le document de ruleset doit contenir une liste 'rules'."
        )

    rules: list[AccountResolutionRule] = []

    for index, raw_rule in enumerate(raw_rules):
        if not isinstance(raw_rule, Mapping):
            raise ResolverConfigurationError(
                f"rules[{index}] doit être un objet."
            )

        raw_conditions = raw_rule.get("conditions")
        if not isinstance(raw_conditions, Mapping):
            raise ResolverConfigurationError(
                f"rules[{index}].conditions doit être un objet."
            )

        conditions = tuple(
            AccountFactCondition(
                field=str(field),
                values=_condition_values(value, field=str(field)),
            )
            for field, value in raw_conditions.items()
        )

        rules.append(
            AccountResolutionRule(
                rule_id=str(raw_rule.get("rule_id") or ""),
                family=str(raw_rule.get("family") or ""),
                conditions=conditions,
                reason=(
                    str(raw_rule["reason"])
                    if raw_rule.get("reason") is not None
                    else None
                ),
            )
        )

    return AccountResolverRuleset(
        version=str(version or ""),
        rules=tuple(rules),
    )


def load_account_ruleset(name: str) -> AccountResolverRuleset:
    resolved_name = str(name or "").strip()

    if not resolved_name or not _RULESET_NAME_RE.fullmatch(resolved_name):
        raise ResolverConfigurationError(
            f"Nom de ruleset invalide : {resolved_name!r}."
        )

    path = RULESET_DIR / f"{resolved_name}.json"

    if not path.exists():
        raise ResolverConfigurationError(
            f"Ruleset introuvable : {resolved_name!r}."
        )

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ResolverConfigurationError(
            f"Impossible de charger le ruleset {resolved_name!r}."
        ) from exc

    return account_ruleset_from_mapping(payload)
