from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence


ACCOUNT_RESOLVER_ALLOWED_FACT_FIELDS = frozenset({
    "source_system",
    "native_account_type",
    "native_account_kind",
    "native_status",
})


class ResolverConfigurationError(ValueError):
    """La configuration du resolver métier est invalide."""


class ResolverInputError(ValueError):
    """Les faits INPUT001 fournis au resolver sont invalides."""


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None

    if not isinstance(value, str):
        raise ResolverInputError(
            "Les faits utilisés par le resolver doivent être textuels ou nuls."
        )

    cleaned = value.strip()
    return cleaned or None


@dataclass(frozen=True)
class AccountFactCondition:
    """Condition exacte sur un fait natif INPUT001 explicitement autorisé."""

    field: str
    values: tuple[str, ...]

    def __post_init__(self) -> None:
        field = str(self.field or "").strip()

        if field not in ACCOUNT_RESOLVER_ALLOWED_FACT_FIELDS:
            raise ResolverConfigurationError(
                "Champ de résolution non autorisé : "
                f"{field!r}. Champs autorisés : "
                + ", ".join(sorted(ACCOUNT_RESOLVER_ALLOWED_FACT_FIELDS))
            )

        if not self.values:
            raise ResolverConfigurationError(
                f"La condition {field!r} doit déclarer au moins une valeur."
            )

        cleaned_values = tuple(
            value.strip()
            for value in self.values
            if isinstance(value, str) and value.strip()
        )

        if len(cleaned_values) != len(self.values):
            raise ResolverConfigurationError(
                f"La condition {field!r} contient une valeur vide ou non textuelle."
            )

        if len(set(cleaned_values)) != len(cleaned_values):
            raise ResolverConfigurationError(
                f"La condition {field!r} contient des valeurs dupliquées."
            )

        object.__setattr__(self, "field", field)
        object.__setattr__(self, "values", cleaned_values)


@dataclass(frozen=True)
class AccountResolutionRule:
    """Règle déclarative : toutes les conditions doivent correspondre."""

    rule_id: str
    family: str
    conditions: tuple[AccountFactCondition, ...]
    reason: str | None = None

    def __post_init__(self) -> None:
        rule_id = str(self.rule_id or "").strip()
        family = str(self.family or "").strip()

        if not rule_id:
            raise ResolverConfigurationError("rule_id doit être renseigné.")

        if not family:
            raise ResolverConfigurationError(
                f"La règle {rule_id!r} doit déclarer une family."
            )

        if family in {"unknown", "conflict"}:
            raise ResolverConfigurationError(
                f"La règle {rule_id!r} utilise une family réservée : {family!r}."
            )

        if not self.conditions:
            raise ResolverConfigurationError(
                f"La règle {rule_id!r} doit contenir au moins une condition."
            )

        fields = [condition.field for condition in self.conditions]
        if len(set(fields)) != len(fields):
            raise ResolverConfigurationError(
                f"La règle {rule_id!r} teste plusieurs fois le même champ."
            )

        reason = self.reason.strip() if isinstance(self.reason, str) else None

        object.__setattr__(self, "rule_id", rule_id)
        object.__setattr__(self, "family", family)
        object.__setattr__(self, "reason", reason or None)


@dataclass(frozen=True)
class AccountResolverRuleset:
    version: str
    rules: tuple[AccountResolutionRule, ...]

    def __post_init__(self) -> None:
        version = str(self.version or "").strip()

        if not version:
            raise ResolverConfigurationError(
                "Le ruleset du resolver doit avoir une version explicite."
            )

        rule_ids = [rule.rule_id for rule in self.rules]
        duplicates = sorted({rule_id for rule_id in rule_ids if rule_ids.count(rule_id) > 1})

        if duplicates:
            raise ResolverConfigurationError(
                "rule_id dupliqué(s) dans le ruleset : "
                + ", ".join(duplicates)
            )

        object.__setattr__(self, "version", version)


@dataclass(frozen=True)
class AccountResolutionEvidence:
    rule_id: str
    family: str
    reason: str | None
    matched_facts: tuple[tuple[str, str], ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "family": self.family,
            "reason": self.reason,
            "matched_facts": {
                field: value
                for field, value in self.matched_facts
            },
        }


@dataclass(frozen=True)
class AccountResolution:
    account_id: str
    family: str | None
    status: str
    rule: str | None
    matched_rules: tuple[str, ...]
    evidence: tuple[AccountResolutionEvidence, ...]
    ruleset_version: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "account_id": self.account_id,
            "family": self.family,
            "status": self.status,
            "rule": self.rule,
            "matched_rules": list(self.matched_rules),
            "evidence": [item.as_dict() for item in self.evidence],
            "ruleset_version": self.ruleset_version,
        }


def _account_id(account: Mapping[str, Any]) -> str:
    value = account.get("account_id")

    if not isinstance(value, str) or not value.strip():
        raise ResolverInputError(
            "accounts.account_id doit être un identifiant textuel non vide."
        )

    return value.strip()


def _condition_match(
    account: Mapping[str, Any],
    condition: AccountFactCondition,
) -> tuple[bool, str | None]:
    observed = _clean_text(account.get(condition.field))

    if observed is None:
        return False, None

    return observed in condition.values, observed


def _match_rule(
    account: Mapping[str, Any],
    rule: AccountResolutionRule,
) -> AccountResolutionEvidence | None:
    matched_facts: list[tuple[str, str]] = []

    for condition in rule.conditions:
        matches, observed = _condition_match(account, condition)

        if not matches or observed is None:
            return None

        matched_facts.append((condition.field, observed))

    return AccountResolutionEvidence(
        rule_id=rule.rule_id,
        family=rule.family,
        reason=rule.reason,
        matched_facts=tuple(matched_facts),
    )


def resolve_account(
    account: Mapping[str, Any],
    *,
    ruleset: AccountResolverRuleset,
) -> AccountResolution:
    """
    Résout une identité financière INPUT001 sans accès DB ni heuristique de label.

    Seuls les faits natifs explicitement autorisés dans les conditions du
    ruleset peuvent contribuer à la décision. `display_label`, `account_id`,
    `native_account_number` et `native_owner_id` ne sont jamais des critères
    de classification dans RESOLVER001.
    """
    if not isinstance(account, Mapping):
        raise ResolverInputError("Le compte à résoudre doit être un mapping.")

    account_id = _account_id(account)
    evidence = tuple(
        match
        for rule in ruleset.rules
        if (match := _match_rule(account, rule)) is not None
    )

    if not evidence:
        return AccountResolution(
            account_id=account_id,
            family=None,
            status="unknown",
            rule=None,
            matched_rules=(),
            evidence=(),
            ruleset_version=ruleset.version,
        )

    families = {item.family for item in evidence}
    matched_rules = tuple(item.rule_id for item in evidence)

    if len(families) > 1:
        return AccountResolution(
            account_id=account_id,
            family=None,
            status="conflict",
            rule=None,
            matched_rules=matched_rules,
            evidence=evidence,
            ruleset_version=ruleset.version,
        )

    family = next(iter(families))

    return AccountResolution(
        account_id=account_id,
        family=family,
        status="resolved",
        rule=matched_rules[0] if len(matched_rules) == 1 else None,
        matched_rules=matched_rules,
        evidence=evidence,
        ruleset_version=ruleset.version,
    )


def resolve_accounts(
    accounts: Sequence[Mapping[str, Any]],
    *,
    ruleset: AccountResolverRuleset,
) -> list[AccountResolution]:
    """Résout un lot en conservant exactement l'ordre fourni par INPUT001."""
    return [
        resolve_account(account, ruleset=ruleset)
        for account in accounts
    ]
